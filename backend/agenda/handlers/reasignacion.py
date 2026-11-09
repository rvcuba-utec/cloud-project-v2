"""TecnicoAusente: las visitas programadas de ese técnico ese día pasan solas al mejor reemplazo.

El reemplazo sale de las mismas reglas que la sugerencia (menos carga del día y más resolución
sin revisita, según Analítica). Si nadie puede tomar una visita a esa hora, queda marcada y aparece
como alerta de reprogramación urgente. Un mensaje repetido no repite nada: cada visita lleva su
propio INBOX dentro de su transacción."""
import os
from types import SimpleNamespace

from boto3.dynamodb.conditions import Key

from trazora_common import dynamo, eventos, interno, logs

from dominio.agenda import (
    PROGRAMADA, a_utc, bloques, claves_indices, datos_evento, elegir_reemplazo, hora_lima, iso, leer_instante,
    prefijo_bloques_dia, sk_alerta, sk_aviso, sk_visita,
)
from handlers.visitas import _actualizar_visita, _delete_bloque, _put_bloque


def _visitas_del_dia(tabla_ddb, tenant, tecnico_id, fecha):
    desde, hasta = iso(a_utc(fecha, "00:00")), iso(a_utc(fecha, "23:59")) + "~"
    visitas, inicio = [], None
    while True:
        parametros = {
            "IndexName": "GSI1",
            "KeyConditionExpression": Key("GSI1PK").eq(f"TENANT#{tenant}#TEC#{tecnico_id}") & Key("GSI1SK").between(desde, hasta),
        }
        if inicio:
            parametros["ExclusiveStartKey"] = inicio
        pagina = tabla_ddb.query(**parametros)
        visitas += pagina.get("Items", [])
        inicio = pagina.get("LastEvaluatedKey")
        if not inicio:
            break
    # El índice es eventual: se relee cada visita para decidir sobre su estado real.
    leidas = [tabla_ddb.get_item(Key={"PK": f"TENANT#{tenant}", "SK": sk_visita(v["visita_id"])}, ConsistentRead=True).get("Item") for v in visitas]
    return sorted([v for v in leidas if v and v["estado"] == PROGRAMADA], key=lambda v: v["inicio"])


def _metricas(tenant, fecha):
    """Analítica es opcional, como en la sugerencia: sin ella se reasigna igual, por orden alfabético."""
    try:
        datos = interno.invocar(os.environ["ANALITICA_FN"], {"tenant_id": tenant, "fecha": fecha})
        return {m["tecnico_id"]: m for m in datos["items"]}
    except Exception as error:
        logs.error("analitica_no_disponible", tenant_id=tenant, tipo_error=type(error).__name__)
        return {}


def _inbox(evento, visita_id):
    return eventos.operacion_inbox(f"{evento['event_id']}#{visita_id}", evento["tenant_id"])


def _aviso(pk, visita, tipo, detalle, ahora, **extra):
    return {"Put": {"TableName": os.environ["TABLE_NAME"], "Item": {
        "PK": pk, "SK": sk_aviso(ahora, visita["visita_id"]), "entity_type": "AVISO", "tipo": tipo,
        "visita_id": visita["visita_id"], "orden_id": visita["orden_id"], "cliente_nombre": visita["cliente_nombre"],
        "fecha": visita["fecha"], "inicio": visita["inicio"], "detalle": detalle, "creado_en": ahora, **extra,
    }}}


def lambda_handler_ausencia(evento):
    tenant, datos = evento["tenant_id"], evento["data"]
    tecnico_id, fecha = datos["tecnico_id"], datos["fecha"]
    pk = f"TENANT#{tenant}"
    contexto = SimpleNamespace(pk=pk, tenant_id=tenant)
    tabla_ddb = dynamo.tabla()
    afectadas = _visitas_del_dia(tabla_ddb, tenant, tecnico_id, fecha)
    if not afectadas:
        logs.info("ausencia_sin_visitas", tenant_id=tenant, tecnico_id=tecnico_id, fecha=fecha)
        return {"reasignadas": 0, "alertas": 0}

    candidatos = interno.invocar(os.environ["TECNICOS_FN"], {"tenant_id": tenant, "fecha": fecha})["items"]
    metricas = _metricas(tenant, fecha)
    ocupados = {}
    for bloque in dynamo.consultar_todo(tabla_ddb, pk, prefijo_bloques_dia(fecha)):
        ocupados.setdefault(bloque["tecnico_id"], set()).add(bloque["hora"])

    reasignadas = alertas = 0
    for visita in afectadas:
        ahora = dynamo.ahora_iso()
        elegido, justificacion = elegir_reemplazo(visita, candidatos, metricas, ocupados, tecnico_id)
        inicio, fin = leer_instante(visita["inicio"], "inicio"), leer_instante(visita["fin"], "fin")
        if elegido:
            indices = claves_indices(tenant, elegido["tecnico_id"], visita["orden_id"], inicio, visita["visita_id"])
            cambios = {"tecnico_id": elegido["tecnico_id"], "tecnico_nombre": elegido["nombre"],
                       "requiere_reprogramacion": False, "reasignada_automaticamente": True, **indices}
            nueva = {**visita, **cambios, "version": visita["version"] + 1}
            detalle = f"Pasó de {visita['tecnico_nombre']} a {elegido['nombre']}" + (f": {justificacion}" if justificacion else "")
            evento_visita = eventos.crear_evento(
                "VisitaReprogramada", tenant, "VISITA", visita["visita_id"], int(nueva["version"]),
                datos_evento(nueva, tecnico_anterior=tecnico_id, fecha_anterior=visita["fecha"], automatica=True,
                             motivo=f"Ausencia de {visita['tecnico_nombre']}"),
                correlation_id=visita["orden_id"],
            )
            operaciones = [
                _inbox(evento, visita["visita_id"]),
                _actualizar_visita(contexto, visita, PROGRAMADA, [f"#c_{k} = :c_{k}" for k in cambios],
                                   {f":c_{k}": v for k, v in cambios.items()}, {f"#c_{k}": k for k in cambios}),
                eventos.operacion_outbox(evento_visita),
                *[_put_bloque(contexto, elegido["tecnico_id"], b, visita["visita_id"]) for b in bloques(inicio, fin)],
                *[_delete_bloque(contexto, tecnico_id, b, visita["visita_id"]) for b in bloques(inicio, fin)],
                {"Delete": {"TableName": os.environ["TABLE_NAME"], "Key": {"PK": pk, "SK": sk_alerta(visita["visita_id"])}}},
                _aviso(pk, visita, "REASIGNADA", detalle, ahora, tecnico_nuevo=elegido["nombre"], tecnico_anterior=visita["tecnico_nombre"]),
            ]
        else:
            evento_visita = None
            motivo = f"{visita['tecnico_nombre']} no podrá asistir y nadie más está libre a esa hora"
            operaciones = [
                _inbox(evento, visita["visita_id"]),
                _actualizar_visita(contexto, visita, PROGRAMADA, ["requiere_reprogramacion = :si", "motivo_reprogramacion = :m"],
                                   {":si": True, ":m": motivo}),
                {"Put": {"TableName": os.environ["TABLE_NAME"], "Item": {
                    "PK": pk, "SK": sk_alerta(visita["visita_id"]), "entity_type": "ALERTA", "visita_id": visita["visita_id"],
                    "orden_id": visita["orden_id"], "cliente_nombre": visita["cliente_nombre"], "direccion": visita["direccion"],
                    "distrito": visita["distrito"], "tipo_servicio": visita["tipo_servicio"], "fecha": visita["fecha"],
                    "inicio": visita["inicio"], "fin": visita["fin"], "tecnico_id": tecnico_id,
                    "tecnico_nombre": visita["tecnico_nombre"], "motivo": motivo, "creada_en": ahora,
                }}},
                _aviso(pk, visita, "SIN_TECNICO", motivo, ahora),
            ]
        try:
            dynamo.transaccion(operaciones)
        except dynamo.TransaccionCancelada as error:
            if error.fallo_condicion(0):
                continue  # Ya se aplicó en un intento anterior de este mismo mensaje.
            raise RuntimeError(f"La visita {visita['visita_id']} cambió durante la reasignación")  # SQS reintenta.
        if evento_visita:
            eventos.publicar_y_borrar(evento_visita)
            for b in bloques(inicio, fin):
                ocupados.setdefault(elegido["tecnico_id"], set()).add(hora_lima(b))  # Otra visita no lo toma.
            reasignadas += 1
        else:
            alertas += 1
    logs.info("ausencia_procesada", tenant_id=tenant, tecnico_id=tecnico_id, fecha=fecha, reasignadas=reasignadas, alertas=alertas)
    return {"reasignadas": reasignadas, "alertas": alertas}
