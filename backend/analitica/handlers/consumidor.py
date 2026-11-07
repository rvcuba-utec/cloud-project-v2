"""Actualiza contadores con ADD. INBOX impide contar dos veces un evento repetido."""
import os

from trazora_common import dynamo, eventos, logs

from dominio.analitica import efectos


def _operacion(pk, sk, cambio, tenant_id, ahora):
    nombres = {f"#s_{k}": k for k in cambio["sumas"]}
    valores = {f":s_{k}": v for k, v in cambio["sumas"].items()}
    asignaciones = []
    for nombre, valor in {**cambio["atributos"], "tenant_id": tenant_id, "ultima_actualizacion": ahora}.items():
        nombres[f"#a_{nombre}"] = nombre
        valores[f":a_{nombre}"] = valor
        asignaciones.append(f"#a_{nombre} = :a_{nombre}")
    sumas = ", ".join(f"#s_{k} :s_{k}" for k in cambio["sumas"])
    return {"Update": {
        "TableName": os.environ["TABLE_NAME"],
        "Key": {"PK": pk, "SK": sk},
        "UpdateExpression": f"SET {', '.join(asignaciones)} ADD {sumas}",
        "ExpressionAttributeNames": nombres,
        "ExpressionAttributeValues": valores,
    }}


def lambda_handler(event, context):
    """Una excepción devuelve el mensaje a la cola; agotados los intentos, pasa a la DLQ."""
    evento = eventos.leer_mensaje_sqs(event)
    tenant = evento["tenant_id"]
    pk = f"TENANT#{tenant}"
    ahora = dynamo.ahora_iso()
    try:
        dynamo.transaccion([
            eventos.operacion_inbox(evento["event_id"], tenant),
            *[_operacion(pk, sk, cambio, tenant, ahora) for sk, cambio in efectos(evento).items()],
        ])
    except dynamo.TransaccionCancelada:
        logs.info("evento_repetido", tenant_id=tenant, event_id=evento["event_id"])
