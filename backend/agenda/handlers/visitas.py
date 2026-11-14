import os
import uuid
from datetime import datetime, timezone

from botocore.exceptions import ClientError

from trazora_common import dynamo, eventos, idempotencia, interno, logs
from trazora_common.auth import ADMIN, COORDINADOR, TECNICO, obtener_contexto, requiere_rol, token_de_peticion
from trazora_common.http import (
    api_handler, conflicto, cuerpo_json, entrada_invalida, no_encontrado, parametro_query, parametro_ruta,
    prohibido, respuesta, texto,
)

from dominio.agenda import (
    CANCELADA, EN_ATENCION, PROGRAMADA, a_utc, bloques, claves_indices, datos_evento, dentro_de_jornada, exigir_futuro,
    fecha_lima, hora_lima, iso, leer_instante, sk_alerta, sk_bloque, sk_control, sk_visita, validar_fecha, validar_horario,
)

GESTION = (ADMIN, COORDINADOR)
ESTADOS_ORDEN_SIN_VISITAS = {"CERRADA", "CANCELADA", "CIERRE_EN_PROCESO"}
INTENTOS = 3


def ahora_utc():
    return datetime.now(timezone.utc)


def _nombre_tabla():
    return os.environ["TABLE_NAME"]


def _validar_orden(event, orden_id):
    orden = interno.llamar(os.environ["ORDENES_URL"], f"/ordenes/{orden_id}", token_de_peticion(event))
    if orden["estado"] in ESTADOS_ORDEN_SIN_VISITAS:
        raise conflicto("ORDEN_NO_ADMITE_VISITAS", "La orden ya no admite visitas")
    return orden


def _validar_tecnico(event, tecnico_id, tipo_servicio, inicio, fin):
    """Se vuelve a validar al confirmar: lo que se mostró al usuario pudo cambiar."""
    token = token_de_peticion(event)
    base = os.environ["TECNICOS_URL"]
    tecnico = interno.llamar(base, f"/tecnicos/{tecnico_id}", token)
    if not tecnico.get("activo"):
        raise conflicto("TECNICO_INACTIVO", "El técnico está desactivado")
    if tipo_servicio not in tecnico.get("especialidades", []):
        raise conflicto("ESPECIALIDAD_INCOMPATIBLE", "El técnico no tiene la especialidad requerida")
    fecha = fecha_lima(inicio)
    agenda = interno.llamar(base, f"/tecnicos/{tecnico_id}/jornadas?desde={fecha}&hasta={fecha}", token)
    if agenda["ausencias"]:
        raise conflicto("TECNICO_AUSENTE", "El técnico está ausente ese día")
    if not agenda["jornadas"] or not dentro_de_jornada(agenda["jornadas"][0]["intervalos"], inicio, fin):
        raise conflicto("FUERA_DE_JORNADA", "El horario está fuera de la jornada del técnico")
    return tecnico


def _asegurar_control(tabla_ddb, contexto, orden_id):
    """Una creación repetida no sobrescribe ni reabre un control existente."""
    clave = {"PK": contexto.pk, "SK": sk_control(orden_id)}
    try:
        tabla_ddb.put_item(
            Item={**clave, "entity_type": "CONTROL_ORDEN", "tenant_id": contexto.tenant_id, "orden_id": orden_id,
                  "acepta_programaciones": True, "visitas_activas": 0, "visitas_total": 0},
            ConditionExpression="attribute_not_exists(PK)",
        )
    except ClientError as error:
        if error.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
    return tabla_ddb.get_item(Key=clave, ConsistentRead=True)["Item"]


def _put_bloque(contexto, tecnico_id, instante, visita_id):
    return {"Put": {
        "TableName": _nombre_tabla(),
        "Item": {
            "PK": contexto.pk, "SK": sk_bloque(tecnico_id, instante), "entity_type": "BLOQUE",
            "tecnico_id": tecnico_id, "visita_id": visita_id, "hora": hora_lima(instante),
        },
        "ConditionExpression": "attribute_not_exists(PK)",
    }}


def _delete_bloque(contexto, tecnico_id, instante, visita_id):
    return {"Delete": {
        "TableName": _nombre_tabla(),
        "Key": {"PK": contexto.pk, "SK": sk_bloque(tecnico_id, instante)},
        "ConditionExpression": "visita_id = :v",
        "ExpressionAttributeValues": {":v": visita_id},
    }}


def _visita(tabla_ddb, contexto, visita_id):
    item = tabla_ddb.get_item(Key={"PK": contexto.pk, "SK": sk_visita(visita_id)}, ConsistentRead=True).get("Item")
    if not item:
        raise no_encontrado("Visita")
    return item


def _exigir_acceso(contexto, visita):
    if contexto.rol == TECNICO and visita["tecnico_id"] != contexto.tecnico_id:
        raise no_encontrado("Visita")  # Un técnico no descubre visitas ajenas.


def _version(datos):
    version = datos.get("version")
    if not isinstance(version, int) or isinstance(version, bool):
        raise entrada_invalida("El campo version es obligatorio", campo="version")
    return version


@api_handler
def crear(event, context):
    contexto = obtener_contexto(event)
    requiere_rol(contexto, *GESTION)
    datos = cuerpo_json(event)
    orden_id = texto(datos, "orden_id", 100)
    tecnico_id = texto(datos, "tecnico_id", 100)
    inicio, fin = validar_horario(datos.get("inicio"), datos.get("fin"))
    exigir_futuro(inicio, ahora_utc())
    pendientes = []  # Evento de este intento; solo se publica si su transacción fue la que ganó.

    def construir():
        orden = _validar_orden(event, orden_id)
        tecnico = _validar_tecnico(event, tecnico_id, orden["tipo_servicio"], inicio, fin)
        tabla_ddb = dynamo.tabla()
        control = _asegurar_control(tabla_ddb, contexto, orden_id)
        if not control["acepta_programaciones"]:
            raise conflicto("ORDEN_NO_ADMITE_VISITAS", "La orden ya no admite visitas")

        visita_id = f"VIS-{uuid.uuid4()}"
        numero = int(control["visitas_total"]) + 1
        visita = {
            "PK": contexto.pk, "SK": sk_visita(visita_id), "entity_type": "VISITA",
            "tenant_id": contexto.tenant_id, "visita_id": visita_id, "orden_id": orden_id, "tecnico_id": tecnico_id,
            # Copias (H17): el técnico ve el destino sin consultar otros servicios.
            "tecnico_nombre": tecnico["nombre"], "orden_descripcion": orden["descripcion"],
            "cliente_nombre": orden["cliente_nombre"], "direccion": orden["direccion"], "distrito": orden["distrito"],
            "tipo_servicio": orden["tipo_servicio"],
            "inicio": iso(inicio), "fin": iso(fin), "fecha": fecha_lima(inicio), "estado": PROGRAMADA,
            "numero_visita_orden": numero, "version": 1, "creada_en": dynamo.ahora_iso(),
            **claves_indices(contexto.tenant_id, tecnico_id, orden_id, inicio, visita_id),
        }
        evento = eventos.crear_evento(
            "VisitaProgramada", contexto.tenant_id, "VISITA", visita_id, 1, datos_evento(visita),
            correlation_id=orden_id,
        )
        pendientes[:] = [evento]
        operaciones = [
            {"Update": {
                # La misma transacción exige el control abierto: un cierre en curso y esta
                # reserva no pueden ignorarse entre sí.
                "TableName": _nombre_tabla(),
                "Key": {"PK": contexto.pk, "SK": sk_control(orden_id)},
                "UpdateExpression": "ADD visitas_activas :uno, visitas_total :uno",
                "ConditionExpression": "acepta_programaciones = :si AND visitas_total = :total",
                "ExpressionAttributeValues": {":uno": 1, ":si": True, ":total": numero - 1},
            }},
            {"Put": {"TableName": _nombre_tabla(), "Item": visita}},
            eventos.operacion_outbox(evento),
            *[_put_bloque(contexto, tecnico_id, b, visita_id) for b in bloques(inicio, fin)],
        ]
        return operaciones, dynamo.vista(visita)

    for intento in range(INTENTOS):
        try:
            resultado = idempotencia.crear(event, contexto.pk, datos, construir)
            break
        except dynamo.TransaccionCancelada as error:
            if error.fallo_condicion(0) and intento < INTENTOS - 1:
                continue  # Otra visita de la orden avanzó el contador: se vuelve a leer.
            if error.fallo_condicion(0):
                raise conflicto("ORDEN_NO_ADMITE_VISITAS", "La orden no admite visitas en este momento")
            raise conflicto("HORARIO_OCUPADO", "Ese horario acaba de ocuparse. Elige otra opción.")

    if pendientes and resultado["visita_id"] == pendientes[0]["aggregate_id"]:
        eventos.publicar_y_borrar(pendientes[0])
        logs.info("visita_programada", tenant_id=contexto.tenant_id, correlation_id=orden_id, visita_id=resultado["visita_id"])
    return respuesta(resultado, 201)


@api_handler
def listar(event, context):
    contexto = obtener_contexto(event)
    tecnico_id = parametro_query(event, "tecnico_id")
    orden_id = parametro_query(event, "orden_id")
    fecha = parametro_query(event, "fecha")
    desde = parametro_query(event, "desde")
    if contexto.rol == TECNICO:
        tecnico_id, orden_id = contexto.tecnico_id, None  # Siempre sus propias visitas (H16).
        if not tecnico_id:
            raise prohibido("Tu cuenta no está asociada a un técnico")

    comunes = {"limite": parametro_query(event, "limit"), "cursor": parametro_query(event, "cursor")}
    tenant = contexto.tenant_id
    if tecnico_id:
        entre = None
        if fecha:
            f = validar_fecha(fecha)
            entre = (iso(a_utc(f, "00:00")), iso(a_utc(f, "23:59")) + "~")
        elif desde:
            entre = (iso(a_utc(validar_fecha(desde, "desde"), "00:00")), "~")
        pagina = dynamo.consultar_pagina(dynamo.tabla(), f"TENANT#{tenant}#TEC#{tecnico_id}", indice="GSI1",
                                         atributo_pk="GSI1PK", atributo_sk="GSI1SK", entre=entre, **comunes)
    elif orden_id:
        pagina = dynamo.consultar_pagina(dynamo.tabla(), f"TENANT#{tenant}#ORDEN#{orden_id}", indice="GSI2",
                                         atributo_pk="GSI2PK", atributo_sk="GSI2SK", **comunes)
    elif fecha:
        pagina = dynamo.consultar_pagina(dynamo.tabla(), f"TENANT#{tenant}#FECHA#{validar_fecha(fecha)}", indice="GSI3",
                                         atributo_pk="GSI3PK", atributo_sk="GSI3SK", **comunes)
    else:
        raise entrada_invalida("Indica tecnico_id, orden_id o fecha")
    return respuesta({"items": [dynamo.vista(i) for i in pagina["items"]], "next_cursor": pagina["next_cursor"]})


@api_handler
def detalle(event, context):
    contexto = obtener_contexto(event)
    visita = _visita(dynamo.tabla(), contexto, parametro_ruta(event, "visita_id"))
    _exigir_acceso(contexto, visita)
    return respuesta(dynamo.vista(visita))


def _actualizar_visita(contexto, visita, condicion_estado, asignaciones, valores, nombres=None):
    return {"Update": {
        "TableName": _nombre_tabla(),
        "Key": {"PK": contexto.pk, "SK": sk_visita(visita["visita_id"])},
        "UpdateExpression": "SET " + ", ".join(asignaciones) + ", #v = :nueva_version",
        "ConditionExpression": "estado = :estado_esperado AND #v = :version_esperada",
        "ExpressionAttributeNames": {"#v": "version", **(nombres or {})},
        "ExpressionAttributeValues": {
            ":estado_esperado": condicion_estado, ":version_esperada": visita["version"],
            ":nueva_version": visita["version"] + 1, **valores,
        },
    }}


@api_handler
def reprogramar(event, context):
    contexto = obtener_contexto(event)
    requiere_rol(contexto, *GESTION)
    visita_id = parametro_ruta(event, "visita_id")
    datos = cuerpo_json(event)
    version = _version(datos)
    inicio, fin = validar_horario(datos.get("inicio"), datos.get("fin"))
    exigir_futuro(inicio, ahora_utc())
    tabla_ddb = dynamo.tabla()
    visita = _visita(tabla_ddb, contexto, visita_id)
    if visita["estado"] != PROGRAMADA:
        raise conflicto("ESTADO_NO_PERMITE", "Solo se puede reprogramar una visita programada")
    if int(visita["version"]) != version:
        raise conflicto("VERSION_DESACTUALIZADA", "La visita cambió. Actualiza e intenta de nuevo.", version=int(visita["version"]))
    tecnico_id = texto(datos, "tecnico_id", 100, obligatorio=False) or visita["tecnico_id"]
    tecnico = _validar_tecnico(event, tecnico_id, visita["tipo_servicio"], inicio, fin)

    actuales = {(visita["tecnico_id"], b) for b in bloques(leer_instante(visita["inicio"], "inicio"), leer_instante(visita["fin"], "fin"))}
    nuevos = {(tecnico_id, b) for b in bloques(inicio, fin)}
    indices = claves_indices(contexto.tenant_id, tecnico_id, visita["orden_id"], inicio, visita_id)
    cambios = {
        "inicio": iso(inicio), "fin": iso(fin), "fecha": fecha_lima(inicio),
        "tecnico_id": tecnico_id, "tecnico_nombre": tecnico["nombre"], "requiere_reprogramacion": False, **indices,
    }
    nueva = {**visita, **cambios, "version": visita["version"] + 1}
    evento = eventos.crear_evento(
        "VisitaReprogramada", contexto.tenant_id, "VISITA", visita_id, int(nueva["version"]),
        datos_evento(nueva, tecnico_anterior=visita["tecnico_id"], fecha_anterior=visita["fecha"]),
        correlation_id=visita["orden_id"],
    )
    # Una sola transacción: si algo falla, la reserva anterior sigue intacta.
    operaciones = [
        _actualizar_visita(
            contexto, visita, PROGRAMADA,
            [f"#c_{k} = :c_{k}" for k in cambios],
            {f":c_{k}": v for k, v in cambios.items()},
            {f"#c_{k}": k for k in cambios},
        ),
        eventos.operacion_outbox(evento),
        *[_put_bloque(contexto, t, b, visita_id) for t, b in nuevos - actuales],
        *[_delete_bloque(contexto, t, b, visita_id) for t, b in actuales - nuevos],
        _borrar_alerta(contexto, visita_id),
    ]
    try:
        dynamo.transaccion(operaciones)
    except dynamo.TransaccionCancelada as error:
        if error.fallo_condicion(0):
            raise conflicto("VERSION_DESACTUALIZADA", "La visita cambió. Actualiza e intenta de nuevo.")
        raise conflicto("HORARIO_OCUPADO", "Ese horario está ocupado. La reserva anterior se conserva.")
    eventos.publicar_y_borrar(evento)
    return respuesta(dynamo.vista(nueva))


@api_handler
def cancelar(event, context):
    contexto = obtener_contexto(event)
    requiere_rol(contexto, *GESTION)
    visita_id = parametro_ruta(event, "visita_id")
    tabla_ddb = dynamo.tabla()
    visita = _visita(tabla_ddb, contexto, visita_id)
    if visita["estado"] == CANCELADA:
        return respuesta(dynamo.vista(visita))  # Repetir no vuelve a restar del contador.
    if visita["estado"] != PROGRAMADA:
        raise conflicto("ESTADO_NO_PERMITE", "Solo se puede cancelar una visita programada")

    operaciones, evento, nueva = operaciones_cancelar(contexto, visita)
    try:
        dynamo.transaccion(operaciones)
    except dynamo.TransaccionCancelada:
        raise conflicto("VERSION_DESACTUALIZADA", "La visita cambió. Actualiza e intenta de nuevo.")
    eventos.publicar_y_borrar(evento)
    return respuesta(dynamo.vista(nueva))


def _borrar_alerta(contexto, visita_id):
    return {"Delete": {"TableName": _nombre_tabla(), "Key": {"PK": contexto.pk, "SK": sk_alerta(visita_id)}}}


def operaciones_cancelar(contexto, visita, motivo=None):
    """También las usa el cierre en cascada de una orden. contexto solo necesita pk y tenant_id."""
    visita_id = visita["visita_id"]
    nueva = {**visita, "estado": CANCELADA, "version": visita["version"] + 1}
    evento = eventos.crear_evento(
        "VisitaCancelada", contexto.tenant_id, "VISITA", visita_id, int(nueva["version"]),
        datos_evento(nueva, **({"motivo": motivo} if motivo else {})), correlation_id=visita["orden_id"],
    )
    operaciones = [
        _actualizar_visita(contexto, visita, PROGRAMADA, ["estado = :nuevo"], {":nuevo": CANCELADA}),
        {"Update": {
            "TableName": _nombre_tabla(),
            "Key": {"PK": contexto.pk, "SK": sk_control(visita["orden_id"])},
            "UpdateExpression": "ADD visitas_activas :menos",
            "ExpressionAttributeValues": {":menos": -1},
        }},
        eventos.operacion_outbox(evento),
        *[_delete_bloque(contexto, visita["tecnico_id"], b, visita_id)
          for b in bloques(leer_instante(visita["inicio"], "inicio"), leer_instante(visita["fin"], "fin"))],
        _borrar_alerta(contexto, visita_id),
    ]
    return operaciones, evento, nueva


@api_handler
def iniciar(event, context):
    contexto = obtener_contexto(event)
    visita_id = parametro_ruta(event, "visita_id")
    tabla_ddb = dynamo.tabla()
    visita = _visita(tabla_ddb, contexto, visita_id)
    _exigir_acceso(contexto, visita)
    requiere_rol(contexto, TECNICO, ADMIN)
    if visita["estado"] == EN_ATENCION:
        return respuesta(dynamo.vista(visita))
    if visita["estado"] != PROGRAMADA:
        raise conflicto("ESTADO_NO_PERMITE", "Solo se puede iniciar una visita programada")

    ahora = dynamo.ahora_iso()
    nueva = {**visita, "estado": EN_ATENCION, "iniciada_en": ahora, "version": visita["version"] + 1}
    evento = eventos.crear_evento(
        "VisitaIniciada", contexto.tenant_id, "VISITA", visita_id, int(nueva["version"]),
        datos_evento(nueva), correlation_id=visita["orden_id"],
    )
    try:
        dynamo.transaccion([
            _actualizar_visita(contexto, visita, PROGRAMADA, ["estado = :nuevo", "iniciada_en = :ahora"], {":nuevo": EN_ATENCION, ":ahora": ahora}),
            eventos.operacion_outbox(evento),
        ])
    except dynamo.TransaccionCancelada:
        raise conflicto("VERSION_DESACTUALIZADA", "La visita cambió. Actualiza e intenta de nuevo.")
    eventos.publicar_y_borrar(evento)
    return respuesta(dynamo.vista(nueva))


