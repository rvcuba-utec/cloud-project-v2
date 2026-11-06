"""Lo invoca Órdenes con lambda.invoke antes de cerrar o cancelar. No tiene ruta pública."""
import os

from botocore.exceptions import ClientError

from trazora_common import dynamo, logs

from dominio.agenda import sk_control


def bloquear(event, context):
    """Deja de aceptar visitas solo si no hay activas. Repetir con el mismo operacion_id es seguro."""
    tenant_id, orden_id, operacion_id = event["tenant_id"], event["orden_id"], event["operacion_id"]
    pk = f"TENANT#{tenant_id}"
    clave = {"PK": pk, "SK": sk_control(orden_id)}
    tabla_ddb = dynamo.tabla()
    try:
        tabla_ddb.put_item(
            Item={**clave, "entity_type": "CONTROL_ORDEN", "tenant_id": tenant_id, "orden_id": orden_id,
                  "acepta_programaciones": True, "visitas_activas": 0, "visitas_total": 0},
            ConditionExpression="attribute_not_exists(PK)",
        )
    except ClientError as error:
        if error.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
    try:
        tabla_ddb.update_item(
            Key=clave,
            UpdateExpression="SET acepta_programaciones = :no, operacion_bloqueo = :op",
            ConditionExpression="visitas_activas = :cero AND (acepta_programaciones = :si OR operacion_bloqueo = :op)",
            ExpressionAttributeValues={":no": False, ":si": True, ":cero": 0, ":op": operacion_id},
        )
    except ClientError as error:
        if error.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
        control = tabla_ddb.get_item(Key=clave, ConsistentRead=True)["Item"]
        logs.info("bloqueo_rechazado", tenant_id=tenant_id, correlation_id=orden_id, visitas_activas=int(control["visitas_activas"]))
        return {"bloqueada": False, "visitas_activas": int(control["visitas_activas"])}
    logs.info("orden_bloqueada", tenant_id=tenant_id, correlation_id=orden_id, tabla=os.environ.get("TABLE_NAME"))
    return {"bloqueada": True, "visitas_activas": 0}
