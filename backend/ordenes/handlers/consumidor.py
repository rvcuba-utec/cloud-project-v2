"""Eventos de Agenda y Partes. SQS estándar puede repetirlos o desordenarlos:
INBOX absorbe los repetidos y la versión de cada visita descarta los atrasados."""
import os
import uuid

from trazora_common import dynamo, eventos, logs

from dominio.ordenes import (
    DETALLE_HISTORIAL, ESTADO_DE_VISITA, RESULTADOS_TEXTO, TERMINALES,
    derivar_estado, particion_estado, resumen_con_evento, sk_historial, sk_orden,
)

INTENTOS = 4  # Dos visitas de una orden pueden coincidir; solo se relee el estado.
EN_PROCESO = "CIERRE_EN_PROCESO"


class _OrdenCambio(Exception):
    pass


def _historial(evento, tipo, detalle):
    orden_id = evento["data"]["orden_id"]
    return {"Put": {"TableName": os.environ["TABLE_NAME"], "Item": {
        "PK": f"TENANT#{evento['tenant_id']}", "SK": sk_historial(orden_id, evento["occurred_at"], uuid.uuid4().hex[:8]),
        "entity_type": "HISTORIAL", "orden_id": orden_id, "tipo": tipo, "detalle": detalle,
        "usuario_id": "sistema", "ocurrido_en": evento["occurred_at"],
    }}}


def _detalle(evento):
    datos = evento["data"]
    if datos.get("automatica"):
        return f"Visita {datos['numero_visita_orden']} reasignada sola: {datos.get('motivo', 'ausencia del técnico')}"
    if evento["event_type"] == "VisitaCancelada" and datos.get("motivo"):
        return f"Visita {datos['numero_visita_orden']} cancelada: {datos['motivo'].lower()}"
    return DETALLE_HISTORIAL[evento["event_type"]].format(n=datos["numero_visita_orden"])


def _aplicar_parte(evento):
    detalle = f"Parte finalizado: {RESULTADOS_TEXTO.get(evento['data']['resultado'], evento['data']['resultado'])}"
    try:
        dynamo.transaccion([
            eventos.operacion_inbox(evento["event_id"], evento["tenant_id"]),
            _historial(evento, "PARTE_FINALIZADO", detalle),
        ])
    except dynamo.TransaccionCancelada:
        logs.info("evento_repetido", tenant_id=evento["tenant_id"], event_id=evento["event_id"])


def _aplicar_visita(evento, tabla_ddb):
    tenant, datos = evento["tenant_id"], evento["data"]
    pk = f"TENANT#{tenant}"
    orden = tabla_ddb.get_item(Key={"PK": pk, "SK": sk_orden(datos["orden_id"])}, ConsistentRead=True).get("Item")
    if not orden:
        raise ValueError(f"Evento {evento['event_id']}: la orden no existe")  # Termina en la DLQ.

    inbox = eventos.operacion_inbox(evento["event_id"], tenant)
    resumen = {
        k: {**v, "version": int(v["version"]), "numero": int(v["numero"])}
        for k, v in orden.get("resumen_visitas", {}).items()
    }
    nuevo = resumen_con_evento(resumen, evento)
    if nuevo is None:
        operaciones = [inbox]  # Atrasado: solo se registra que ya se vio.
    else:
        asignaciones = ["resumen_visitas = :r", "#v = :siguiente"]
        valores = {":r": nuevo, ":version": orden["version"], ":siguiente": orden["version"] + 1}
        derivado = derivar_estado(nuevo)
        if orden["estado"] == EN_PROCESO:
            # Si el cierre se rechaza, la orden debe volver a su estado real, no al de antes.
            asignaciones.append("estado_previo = :e")
            valores[":e"] = derivado
        elif orden["estado"] not in TERMINALES and orden["estado"] != derivado:
            asignaciones += ["estado = :e", "GSI1PK = :gsi"]
            valores.update({":e": derivado, ":gsi": particion_estado(tenant, derivado)})
        operaciones = [
            inbox,
            {"Update": {
                "TableName": os.environ["TABLE_NAME"],
                "Key": {"PK": pk, "SK": sk_orden(datos["orden_id"])},
                "UpdateExpression": "SET " + ", ".join(asignaciones),
                "ConditionExpression": "#v = :version",
                "ExpressionAttributeNames": {"#v": "version"},
                "ExpressionAttributeValues": valores,
            }},
            _historial(evento, evento["event_type"], _detalle(evento)),
        ]
    try:
        dynamo.transaccion(operaciones)
    except dynamo.TransaccionCancelada as error:
        if error.fallo_condicion(0):
            logs.info("evento_repetido", tenant_id=tenant, event_id=evento["event_id"])
            return
        raise _OrdenCambio()


def lambda_handler(event, context):
    """Una excepción devuelve el mensaje a la cola; agotados los intentos, pasa a la DLQ."""
    evento = eventos.leer_mensaje_sqs(event)
    if evento["event_type"] == "ParteFinalizado":
        _aplicar_parte(evento)
        return
    if evento["event_type"] not in ESTADO_DE_VISITA:
        raise ValueError(f"Evento no esperado: {evento['event_type']}")
    tabla_ddb = dynamo.tabla()
    for _ in range(INTENTOS):
        try:
            _aplicar_visita(evento, tabla_ddb)
            return
        except _OrdenCambio:
            continue
    raise RuntimeError(f"Evento {evento['event_id']}: la orden siguió cambiando")
