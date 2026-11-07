"""Acceso a S3 y a las evidencias, compartido por la API y por la notificación del bucket."""
import os

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from dominio.partes import (
    CONFIRMADA, MAX_BYTES, PENDIENTE, RECHAZADA, VALIDEZ_FIRMA_SEGUNDOS, archivo_valido, sk_evidencia,
)

_s3 = None


def s3():
    global _s3
    if _s3 is None:
        _s3 = boto3.client("s3", config=Config(signature_version="s3v4"))
    return _s3


def reiniciar():
    """Solo para pruebas: descarta el cliente guardado."""
    global _s3
    _s3 = None


def firmar_subida(clave, tipo):
    """El límite de tamaño y el tipo los aplica S3: un PUT prefirmado no permitiría limitar el tamaño (H6)."""
    return s3().generate_presigned_post(
        os.environ["BUCKET"], clave,
        Fields={"Content-Type": tipo},
        Conditions=[{"Content-Type": tipo}, ["content-length-range", 1, MAX_BYTES]],
        ExpiresIn=VALIDEZ_FIRMA_SEGUNDOS,
    )


def firmar_lectura(clave):
    return s3().generate_presigned_url(
        "get_object", Params={"Bucket": os.environ["BUCKET"], "Key": clave}, ExpiresIn=VALIDEZ_FIRMA_SEGUNDOS,
    )


def revisar_y_marcar(tabla_ddb, pk, evidencia):
    """Comprueba el archivo real y deja la evidencia en su estado final. Repetirlo no cambia nada.
    Devuelve el estado resultante, o PENDIENTE si el archivo todavía no está en S3."""
    if evidencia["estado"] != PENDIENTE:
        return evidencia["estado"]
    try:
        cabecera = s3().head_object(Bucket=os.environ["BUCKET"], Key=evidencia["object_key"])
    except ClientError as error:
        if error.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
            return PENDIENTE
        raise
    nuevo = CONFIRMADA if archivo_valido(cabecera["ContentLength"], cabecera.get("ContentType")) else RECHAZADA
    try:
        tabla_ddb.update_item(
            Key={"PK": pk, "SK": sk_evidencia(evidencia["evidencia_id"])},
            UpdateExpression="SET estado = :nuevo, tamano_bytes = :tamano",
            ConditionExpression="estado = :pendiente",
            ExpressionAttributeValues={":nuevo": nuevo, ":pendiente": PENDIENTE, ":tamano": cabecera["ContentLength"]},
        )
    except ClientError as error:
        if error.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
        # La notificación y la confirmación manual coincidieron: vale lo que guardó la primera.
        actual = tabla_ddb.get_item(Key={"PK": pk, "SK": sk_evidencia(evidencia["evidencia_id"])}, ConsistentRead=True)
        return actual["Item"]["estado"]
    return nuevo
