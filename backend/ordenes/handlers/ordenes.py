import json
import os
import uuid

import boto3
from botocore.exceptions import ClientError

from trazora_common import dynamo, eventos, idempotencia, interno, logs
from trazora_common.auth import ADMIN, COORDINADOR, obtener_contexto, requiere_rol, token_de_peticion
from trazora_common.http import (
    ApiError, api_handler, conflicto, cuerpo_json, entrada_invalida, no_encontrado, opcion,
    parametro_query, parametro_ruta, respuesta, texto,
)

from dominio.ordenes import (
    ABIERTA, ESTADOS, PRIORIDADES, TERMINALES, TIPOS_SERVICIO,
    nuevo_id, particion_cliente, particion_estado, sk_historial, sk_orden,
)

GESTION = (ADMIN, COORDINADOR)


def _validar_ubicacion(event, cliente_id, ubicacion_id):
    """Con el token del usuario: otra empresa recibe 404, igual que un ID inexistente."""
    ubicacion = interno.llamar(
        os.environ["CLIENTES_URL"],
        f"/clientes/{cliente_id}/ubicaciones/{ubicacion_id}",
        token_de_peticion(event),
    )
    if not ubicacion.get("cliente_activo"):
        raise conflicto("CLIENTE_INACTIVO", "El cliente está desactivado")
    return ubicacion


@api_handler
def crear(event, context):
    contexto = obtener_contexto(event)
    requiere_rol(contexto, *GESTION)
    datos = cuerpo_json(event)
    cliente_id = texto(datos, "cliente_id", 100)
    ubicacion_id = texto(datos, "ubicacion_id", 100)
    descripcion = texto(datos, "descripcion", 2000)
    tipo = opcion(datos, "tipo_servicio", TIPOS_SERVICIO)
    prioridad = opcion(datos, "prioridad", PRIORIDADES)
    pendientes = []  # Evento de este intento; solo se publica si su transacción fue la que ganó.

    def construir():
        ubicacion = _validar_ubicacion(event, cliente_id, ubicacion_id)
        orden_id = nuevo_id()
        ahora = dynamo.ahora_iso()
        item = {
            "PK": contexto.pk, "SK": sk_orden(orden_id), "entity_type": "ORDEN",
            "tenant_id": contexto.tenant_id, "orden_id": orden_id,
            "cliente_id": cliente_id, "ubicacion_id": ubicacion_id,
            # Copias (H17): las listas no consultan otro servicio por cada fila.
            "cliente_nombre": ubicacion["cliente_nombre"],
            "direccion": ubicacion["direccion"], "distrito": ubicacion["distrito"],
            "tipo_servicio": tipo, "descripcion": descripcion, "prioridad": prioridad,
            "estado": ABIERTA, "version": 1, "creada_en": ahora,
            "GSI1PK": particion_estado(contexto.tenant_id, ABIERTA), "GSI1SK": f"{ahora}#{orden_id}",
            "GSI2PK": particion_cliente(contexto.tenant_id, cliente_id), "GSI2SK": f"{ahora}#{orden_id}",
        }
        historial = {
            "PK": contexto.pk, "SK": sk_historial(orden_id, ahora, uuid.uuid4().hex[:8]), "entity_type": "HISTORIAL",
            "orden_id": orden_id, "tipo": "ORDEN_CREADA", "detalle": "Orden registrada",
            "usuario_id": contexto.usuario_id, "ocurrido_en": ahora,
        }
        tabla = os.environ["TABLE_NAME"]
        evento = eventos.crear_evento(
            "OrdenCreada", contexto.tenant_id, "ORDEN", orden_id, 1,
            {"orden_id": orden_id, "cliente_id": cliente_id, "creada_en": ahora}, correlation_id=orden_id,
        )
        pendientes[:] = [evento]
        return [
            {"Put": {"TableName": tabla, "Item": item}},
            {"Put": {"TableName": tabla, "Item": historial}},
            eventos.operacion_outbox(evento),
        ], dynamo.vista(item)

    resultado = idempotencia.crear(event, contexto.pk, datos, construir)
    if pendientes and resultado["orden_id"] == pendientes[0]["aggregate_id"]:
        eventos.publicar_y_borrar(pendientes[0])
    logs.info("orden_creada", tenant_id=contexto.tenant_id, correlation_id=resultado["orden_id"])
    return respuesta(resultado, 201)


@api_handler
def listar(event, context):
    contexto = obtener_contexto(event)
    requiere_rol(contexto, *GESTION)
    estado = parametro_query(event, "estado")
    cliente_id = parametro_query(event, "cliente_id")
    if estado and cliente_id:
        raise entrada_invalida("Filtra por estado o por cliente, no por ambos")
    if estado and estado not in ESTADOS:
        raise entrada_invalida("Estado no válido", permitidas=sorted(ESTADOS))

    comunes = {"limite": parametro_query(event, "limit"), "cursor": parametro_query(event, "cursor"), "descendente": True}
    tabla_ddb = dynamo.tabla()
    if estado:
        pagina = dynamo.consultar_pagina(
            tabla_ddb, particion_estado(contexto.tenant_id, estado),
            indice="GSI1", atributo_pk="GSI1PK", atributo_sk="GSI1SK", **comunes,
        )
    elif cliente_id:
        pagina = dynamo.consultar_pagina(
            tabla_ddb, particion_cliente(contexto.tenant_id, cliente_id),
            indice="GSI2", atributo_pk="GSI2PK", atributo_sk="GSI2SK", **comunes,
        )
    else:
        pagina = dynamo.consultar_pagina(tabla_ddb, contexto.pk, "ORDEN#", **comunes)
    return respuesta({"items": [dynamo.vista(i) for i in pagina["items"]], "next_cursor": pagina["next_cursor"]})


def _orden(tabla_ddb, contexto, orden_id):
    item = tabla_ddb.get_item(Key={"PK": contexto.pk, "SK": sk_orden(orden_id)}).get("Item")
    if not item:
        raise no_encontrado("Orden")
    return item


@api_handler
def detalle(event, context):
    contexto = obtener_contexto(event)
    requiere_rol(contexto, *GESTION)
    return respuesta(dynamo.vista(_orden(dynamo.tabla(), contexto, parametro_ruta(event, "orden_id"))))


@api_handler
def actualizar(event, context):
    """Cambia la prioridad. La versión evita pisar un cambio que el usuario no vio."""
    contexto = obtener_contexto(event)
    requiere_rol(contexto, *GESTION)
    orden_id = parametro_ruta(event, "orden_id")
    datos = cuerpo_json(event)
    prioridad = opcion(datos, "prioridad", PRIORIDADES)
    version = datos.get("version")
    if not isinstance(version, int) or isinstance(version, bool):
        raise entrada_invalida("El campo version es obligatorio", campo="version")

    tabla_ddb = dynamo.tabla()
    actual = _orden(tabla_ddb, contexto, orden_id)
    if actual["estado"] in TERMINALES:
        raise conflicto("ORDEN_TERMINADA", "La orden ya está cerrada o cancelada")
    try:
        resultado = tabla_ddb.update_item(
            Key={"PK": contexto.pk, "SK": sk_orden(orden_id)},
            UpdateExpression="SET prioridad = :p ADD #v :uno",
            ConditionExpression="#v = :version",
            ExpressionAttributeNames={"#v": "version"},
            ExpressionAttributeValues={":p": prioridad, ":uno": 1, ":version": version},
            ReturnValues="ALL_NEW",
        )
    except ClientError as error:
        if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise conflicto("VERSION_DESACTUALIZADA", "La orden cambió. Actualiza e intenta de nuevo.", version=int(actual["version"]))
        raise
    return respuesta(dynamo.vista(resultado["Attributes"]))


@api_handler
def historial(event, context):
    contexto = obtener_contexto(event)
    requiere_rol(contexto, *GESTION)
    orden_id = parametro_ruta(event, "orden_id")
    tabla_ddb = dynamo.tabla()
    _orden(tabla_ddb, contexto, orden_id)
    pagina = dynamo.consultar_pagina(
        tabla_ddb, contexto.pk, f"HIST#{orden_id}#", descendente=True,
        limite=parametro_query(event, "limit"), cursor=parametro_query(event, "cursor"),
    )
    return respuesta({"items": [dynamo.vista(i) for i in pagina["items"]], "next_cursor": pagina["next_cursor"]})


def _cambiar_estado(contexto, orden, nuevo, extra_set=None, extra_valores=None, quitar=None):
    """Operación que cambia el estado y mueve la orden en el índice por estado."""
    asignaciones = ["estado = :nuevo", "GSI1PK = :gsi", "#v = :siguiente"] + list(extra_set or [])
    expresion = "SET " + ", ".join(asignaciones)
    if quitar:
        expresion += " REMOVE " + ", ".join(quitar)
    return {"Update": {
        "TableName": os.environ["TABLE_NAME"],
        "Key": {"PK": contexto.pk, "SK": sk_orden(orden["orden_id"])},
        "UpdateExpression": expresion,
        "ConditionExpression": "#v = :version",
        "ExpressionAttributeNames": {"#v": "version"},
        "ExpressionAttributeValues": {
            ":nuevo": nuevo, ":gsi": particion_estado(contexto.tenant_id, nuevo),
            ":version": orden["version"], ":siguiente": orden["version"] + 1, **(extra_valores or {}),
        },
    }}


def _historial(contexto, orden_id, tipo, detalle):
    ahora = dynamo.ahora_iso()
    return {"Put": {"TableName": os.environ["TABLE_NAME"], "Item": {
        "PK": contexto.pk, "SK": sk_historial(orden_id, ahora, uuid.uuid4().hex[:8]), "entity_type": "HISTORIAL",
        "orden_id": orden_id, "tipo": tipo, "detalle": detalle, "usuario_id": contexto.usuario_id, "ocurrido_en": ahora,
    }}}


def _pedir_bloqueo(contexto, orden_id, operacion_id):
    """H1: invocación directa, sin ruta pública ni dependencia circular de despliegue."""
    respuesta_lambda = boto3.client("lambda").invoke(
        FunctionName=os.environ["AGENDA_BLOQUEO_FN"],
        Payload=json.dumps({"tenant_id": contexto.tenant_id, "orden_id": orden_id, "operacion_id": operacion_id}).encode(),
    )
    if respuesta_lambda.get("FunctionError"):
        raise RuntimeError("Falló el bloqueo en Agenda")
    return json.loads(respuesta_lambda["Payload"].read())


def _terminar(event, destino, estados_permitidos, evento_tipo, detalle):
    """Coordinación entre servicios, sin transacción compartida:
    1. Registrar CIERRE_EN_PROCESO con un ID de operación. 2. Bloquear en Agenda. 3. Confirmar.
    Si el resultado del paso 2 es desconocido, la orden sigue en proceso y se reintenta con el mismo ID."""
    contexto = obtener_contexto(event)
    requiere_rol(contexto, *GESTION)
    orden_id = parametro_ruta(event, "orden_id")
    tabla_ddb = dynamo.tabla()
    clave = {"PK": contexto.pk, "SK": sk_orden(orden_id)}
    orden = tabla_ddb.get_item(Key=clave, ConsistentRead=True).get("Item")
    if not orden:
        raise no_encontrado("Orden")
    if orden["estado"] == destino:
        return respuesta(dynamo.vista(orden))
    if orden["estado"] in TERMINALES:
        raise conflicto("ORDEN_TERMINADA", "La orden ya está cerrada o cancelada")

    try:
        if orden["estado"] == "CIERRE_EN_PROCESO":
            if orden.get("destino_cierre") != destino:
                raise conflicto("OPERACION_EN_CURSO", "Hay otra operación en curso sobre esta orden")
            operacion_id = orden["operacion_cierre"]
        else:
            if orden["estado"] not in estados_permitidos:
                raise conflicto("ESTADO_NO_PERMITE", "El estado de la orden no permite esta operación")
            operacion_id = str(uuid.uuid4())
            dynamo.transaccion([
                _cambiar_estado(contexto, orden, "CIERRE_EN_PROCESO",
                                ["operacion_cierre = :op", "destino_cierre = :d", "estado_previo = :p"],
                                {":op": operacion_id, ":d": destino, ":p": orden["estado"]}),
                _historial(contexto, orden_id, "CIERRE_SOLICITADO", detalle["solicitud"]),
            ])
            orden = tabla_ddb.get_item(Key=clave, ConsistentRead=True)["Item"]
    except dynamo.TransaccionCancelada:
        raise conflicto("VERSION_DESACTUALIZADA", "La orden cambió. Actualiza e intenta de nuevo.")

    try:
        resultado = _pedir_bloqueo(contexto, orden_id, operacion_id)
    except Exception as error:
        logs.error("bloqueo_desconocido", tenant_id=contexto.tenant_id, correlation_id=orden_id, tipo_error=type(error).__name__)
        raise ApiError(503, "CIERRE_PENDIENTE", "No se pudo confirmar con Agenda. Intenta de nuevo.")

    try:
        if not resultado["bloqueada"]:
            dynamo.transaccion([
                _cambiar_estado(contexto, orden, orden["estado_previo"], quitar=["operacion_cierre", "destino_cierre", "estado_previo"]),
                _historial(contexto, orden_id, "CIERRE_RECHAZADO", "Rechazado: quedan visitas activas"),
            ])
            raise conflicto("VISITAS_ACTIVAS", "Aún hay visitas programadas o en atención", visitas_activas=resultado["visitas_activas"])

        ahora = dynamo.ahora_iso()
        evento = eventos.crear_evento(
            evento_tipo, contexto.tenant_id, "ORDEN", orden_id, int(orden["version"]) + 1,
            {"orden_id": orden_id, "creada_en": orden["creada_en"], "terminada_en": ahora}, correlation_id=orden_id,
        )
        dynamo.transaccion([
            _cambiar_estado(contexto, orden, destino, ["terminada_en = :t"], {":t": ahora}, quitar=["operacion_cierre", "destino_cierre", "estado_previo"]),
            _historial(contexto, orden_id, evento_tipo.upper(), detalle["fin"]),
            eventos.operacion_outbox(evento),
        ])
    except dynamo.TransaccionCancelada:
        raise conflicto("VERSION_DESACTUALIZADA", "La orden cambió. Actualiza e intenta de nuevo.")
    eventos.publicar_y_borrar(evento)
    logs.info(evento_tipo, tenant_id=contexto.tenant_id, correlation_id=orden_id)
    return respuesta(dynamo.vista(tabla_ddb.get_item(Key=clave, ConsistentRead=True)["Item"]))


@api_handler
def cerrar(event, context):
    return _terminar(event, "CERRADA", {"PENDIENTE_DE_CIERRE"}, "OrdenCerrada",
                     {"solicitud": "Cierre solicitado", "fin": "Orden cerrada"})


@api_handler
def cancelar(event, context):
    permitidos = {"ABIERTA", "PROGRAMADA", "REQUIERE_REVISITA", "PENDIENTE_DE_CIERRE"}
    return _terminar(event, "CANCELADA", permitidos, "OrdenCancelada",
                     {"solicitud": "Cancelación solicitada", "fin": "Orden cancelada"})
