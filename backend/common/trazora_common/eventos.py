"""Eventos de negocio: outbox sin Streams.

1. El cambio de negocio y el ítem OUTBOX se guardan en la misma transacción.
2. publicar_y_borrar() publica en SNS (taller 10) y borra el ítem.
3. Si la Lambda falla entre ambos pasos, barrer() reenvía lo pendiente (EventBridge, taller 13).
Los consumidores toleran duplicados con INBOX: la entrega es al menos una vez.
"""
import json
import os
import uuid
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

from . import dynamo, logs

PREFIJO_OUTBOX = "OUTBOX#"
PREFIJO_INBOX = "INBOX#"
_sns = None


def cliente_sns():
    global _sns
    if _sns is None:
        _sns = boto3.client("sns")
    return _sns


def reiniciar():
    """Solo para pruebas: descarta el cliente guardado."""
    global _sns
    _sns = None


def crear_evento(event_type, tenant_id, aggregate_type, aggregate_id, aggregate_version, data,
                 correlation_id=None, event_id=None):
    return {
        "event_id": event_id or str(uuid.uuid4()),
        "event_type": event_type,
        "schema_version": 1,
        "tenant_id": tenant_id,
        "aggregate_type": aggregate_type,
        "aggregate_id": aggregate_id,
        "aggregate_version": aggregate_version,
        "occurred_at": dynamo.ahora_iso(),
        "correlation_id": correlation_id or aggregate_id,
        "data": data,
    }


def _clave_outbox(evento):
    return {"PK": f"TENANT#{evento['tenant_id']}", "SK": f"{PREFIJO_OUTBOX}{evento['event_id']}"}


def operacion_outbox(evento, nombre_tabla=None):
    """Operación para incluir en la misma transacción que el cambio de negocio."""
    return {
        "Put": {
            "TableName": nombre_tabla or os.environ["TABLE_NAME"],
            "Item": {**_clave_outbox(evento), "entity_type": "OUTBOX", "evento": evento},
        }
    }


def operacion_inbox(event_id, tenant_id, nombre_tabla=None):
    """Falla si el evento ya se aplicó, y con ello cancela toda la transacción del consumidor."""
    return {
        "Put": {
            "TableName": nombre_tabla or os.environ["TABLE_NAME"],
            "Item": {
                "PK": f"TENANT#{tenant_id}",
                "SK": f"{PREFIJO_INBOX}{event_id}",
                "entity_type": "INBOX",
                "procesado_en": dynamo.ahora_iso(),
            },
            "ConditionExpression": "attribute_not_exists(PK)",
        }
    }


def publicar(evento):
    """El cuerpo es Message y los atributos permiten filtrar por suscripción (talleres 10 y 13)."""
    cliente_sns().publish(
        TopicArn=os.environ["TOPIC_ARN"],
        Subject=evento["event_type"][:100],
        Message=json.dumps(evento, default=dynamo_a_json, ensure_ascii=False),
        MessageAttributes={
            "event_type": {"DataType": "String", "StringValue": evento["event_type"]},
            "tenant_id": {"DataType": "String", "StringValue": evento["tenant_id"]},
        },
    )


def dynamo_a_json(valor):
    if isinstance(valor, Decimal):
        return int(valor) if valor == valor.to_integral_value() else float(valor)
    raise TypeError(f"No serializable: {type(valor).__name__}")


def publicar_y_borrar(evento, tabla_ddb=None):
    """Tras confirmar la transacción. Un fallo no se propaga: el cambio ya se guardó,
    el ítem sigue pendiente y el barrido lo reenviará."""
    try:
        publicar(evento)
        (tabla_ddb or dynamo.tabla()).delete_item(Key=_clave_outbox(evento))
        return True
    except Exception as error:
        logs.error(
            "publicar_evento",
            tenant_id=evento.get("tenant_id"),
            correlation_id=evento.get("correlation_id"),
            event_id=evento.get("event_id"),
            event_type=evento.get("event_type"),
            tipo_error=type(error).__name__,
        )
        return False


def barrer(tenants, tabla_ddb=None):
    """Reenvía con el mismo event_id lo que quedó pendiente. Devuelve cuántos reenvió."""
    tabla_ddb = tabla_ddb or dynamo.tabla()
    reenviados = 0
    for tenant_id in tenants:
        condicion = Key("PK").eq(f"TENANT#{tenant_id}") & Key("SK").begins_with(PREFIJO_OUTBOX)
        inicio = None
        while True:
            parametros = {"KeyConditionExpression": condicion}
            if inicio:
                parametros["ExclusiveStartKey"] = inicio
            resultado = tabla_ddb.query(**parametros)
            for item in resultado.get("Items", []):
                if publicar_y_borrar(item["evento"], tabla_ddb):
                    reenviados += 1
            inicio = resultado.get("LastEvaluatedKey")
            if not inicio:
                break
    return reenviados


def manejador_barrido(event, context):
    """Handler reutilizable para la Lambda programada de cada servicio productor."""
    tenants = [t for t in os.environ.get("TENANTS", "").split(",") if t]
    reenviados = barrer(tenants)
    if reenviados:
        logs.info("barrido_outbox", reenviados=reenviados)
    return {"reenviados": reenviados}


def leer_mensaje_sqs(event):
    """Evento de negocio en un lote de 1 mensaje, como en el taller 13."""
    cuerpo = json.loads(event["Records"][0]["body"])
    return json.loads(cuerpo["Message"])
