"""ParteFinalizado termina la visita y anuncia VisitaCompletada; TecnicoAusente reasigna sus visitas."""
import os

from trazora_common import dynamo, eventos, logs

from dominio.agenda import EN_ATENCION, FINALIZADA, datos_evento, duracion_minutos, sk_control, sk_visita


def lambda_handler(event, context):
    """Una excepción devuelve el mensaje a la cola; agotados los intentos, pasa a la DLQ."""
    evento = eventos.leer_mensaje_sqs(event)
    if evento["event_type"] == "TecnicoAusente":
        from handlers.reasignacion import lambda_handler_ausencia
        return lambda_handler_ausencia(evento)
    if evento["event_type"] != "ParteFinalizado":
        raise ValueError(f"Evento no esperado: {evento['event_type']}")
    tenant, datos = evento["tenant_id"], evento["data"]
    pk = f"TENANT#{tenant}"
    visita_id = datos["visita_id"]
    tabla_ddb = dynamo.tabla()
    visita = tabla_ddb.get_item(Key={"PK": pk, "SK": sk_visita(visita_id)}, ConsistentRead=True).get("Item")
    if not visita:
        raise ValueError(f"Evento {evento['event_id']}: la visita no existe")

    if visita["estado"] == FINALIZADA:
        return  # Repetido: el efecto ya se aplicó.
    if visita["estado"] != EN_ATENCION:
        # No se reintenta: repetirlo no cambiaría el estado. Queda en los logs para revisarlo.
        logs.error("conflicto_parte_visita", tenant_id=tenant, correlation_id=datos["orden_id"],
                   visita_id=visita_id, estado=visita["estado"], event_id=evento["event_id"])
        return

    duracion = duracion_minutos(visita["iniciada_en"], datos["finalizado_en"])
    version = visita["version"] + 1
    completada = eventos.crear_evento(
        "VisitaCompletada", tenant, "VISITA", visita_id, int(version),
        datos_evento(visita, resultado=datos["resultado"], parte_id=datos["parte_id"],
                     duracion_min=duracion, finalizada_en=datos["finalizado_en"]),
        correlation_id=datos["orden_id"],
    )
    tabla = os.environ["TABLE_NAME"]
    try:
        dynamo.transaccion([
            eventos.operacion_inbox(evento["event_id"], tenant),
            {"Update": {
                "TableName": tabla,
                "Key": {"PK": pk, "SK": sk_visita(visita_id)},
                "UpdateExpression": "SET estado = :final, resultado = :resultado, finalizada_en = :fin, duracion_min = :dur, #v = :nueva",
                "ConditionExpression": "estado = :atencion AND #v = :version",
                "ExpressionAttributeNames": {"#v": "version"},
                "ExpressionAttributeValues": {
                    ":final": FINALIZADA, ":resultado": datos["resultado"], ":fin": datos["finalizado_en"], ":dur": duracion,
                    ":atencion": EN_ATENCION, ":version": visita["version"], ":nueva": version,
                },
            }},
            {"Update": {
                "TableName": tabla,
                "Key": {"PK": pk, "SK": sk_control(datos["orden_id"])},
                "UpdateExpression": "ADD visitas_activas :menos",
                "ExpressionAttributeValues": {":menos": -1},
            }},
            eventos.operacion_outbox(completada),
        ])
    except dynamo.TransaccionCancelada as error:
        if error.fallo_condicion(0):
            logs.info("evento_repetido", tenant_id=tenant, event_id=evento["event_id"])
            return
        raise RuntimeError(f"Evento {evento['event_id']}: la visita cambió")  # Se reintenta y se relee.
    eventos.publicar_y_borrar(completada)
    logs.info("visita_completada", tenant_id=tenant, correlation_id=datos["orden_id"], visita_id=visita_id)
