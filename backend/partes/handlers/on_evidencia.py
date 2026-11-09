"""Notificación del bucket: confirma la evidencia en cuanto el archivo llega a S3 (taller 11)."""
from urllib.parse import unquote_plus

from trazora_common import dynamo, logs

from dominio import almacen
from dominio.partes import leer_clave_objeto, sk_evidencia


def lambda_handler(event, context):
    tabla_ddb = dynamo.tabla()
    for registro in event["Records"]:
        clave = unquote_plus(registro["s3"]["object"]["key"])  # S3 envía la clave codificada (H19).
        leida = leer_clave_objeto(clave)
        if not leida:
            logs.error("evidencia_clave_invalida", clave=clave)
            continue
        tenant_id, evidencia_id = leida
        pk = f"TENANT#{tenant_id}"
        evidencia = tabla_ddb.get_item(Key={"PK": pk, "SK": sk_evidencia(evidencia_id)}, ConsistentRead=True).get("Item")
        if not evidencia or evidencia["object_key"] != clave:
            logs.error("evidencia_desconocida", tenant_id=tenant_id, clave=clave)
            continue
        estado = almacen.revisar_y_marcar(tabla_ddb, pk, evidencia)
        logs.info("evidencia_revisada", tenant_id=tenant_id, evidencia_id=evidencia_id, estado=estado)
