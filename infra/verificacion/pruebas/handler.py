import json
import os
import urllib.parse

import boto3
from botocore.config import Config

dynamodb = boto3.resource("dynamodb")
tabla = dynamodb.Table(os.environ["TABLE_NAME"])


def _marcar(sk, **extra):
    tabla.put_item(Item={"PK": "VERIF", "SK": sk, **extra})


def protegido(event, context):
    # Comprueba en una sola ruta: contexto del autorizador, transacción y lambda.invoke
    contexto = event["requestContext"]["authorizer"]
    cliente = dynamodb.meta.client
    cliente.transact_write_items(TransactItems=[
        {"Put": {"TableName": os.environ["TABLE_NAME"], "Item": {"PK": "VERIF", "SK": "TX#1", "n": 1}}},
        {"Put": {"TableName": os.environ["TABLE_NAME"], "Item": {"PK": "VERIF", "SK": "TX#2", "n": 2}}},
    ])
    invocacion = boto3.client("lambda").invoke(
        FunctionName=os.environ["OBJETIVO"], Payload=json.dumps({"ping": "ok"}).encode()
    )
    return {
        "statusCode": 200,
        "headers": {"Access-Control-Allow-Origin": "*"},
        "body": json.dumps({
            "tenant_id": contexto["tenant_id"],
            "transaccion": True,
            "invocacion": json.loads(invocacion["Payload"].read()),
        }),
    }


def objetivo(event, context):
    return {"recibido": event.get("ping")}


def firmar(event, context):
    s3 = boto3.client("s3", config=Config(signature_version="s3v4"))
    firma = s3.generate_presigned_post(
        os.environ["BUCKET"],
        "tenants/VERIF/evidencia.jpg",
        Fields={"Content-Type": "image/jpeg"},
        Conditions=[{"Content-Type": "image/jpeg"}, ["content-length-range", 1, 1024 * 1024]],
        ExpiresIn=300,
    )
    return {"statusCode": 200, "headers": {"Access-Control-Allow-Origin": "*"}, "body": json.dumps(firma)}


def consumidor(event, context):
    cuerpo = json.loads(event["Records"][0]["body"])  # Sobre de SNS, como en el taller 13
    mensaje = json.loads(cuerpo["Message"])
    if mensaje["accion"] == "fallar":
        raise ValueError("Fallo simulado para comprobar la DLQ")
    _marcar(f"SQS#{mensaje['id']}")


def programado(event, context):
    _marcar("EVENTBRIDGE#1")


def on_s3(event, context):
    clave = urllib.parse.unquote_plus(event["Records"][0]["s3"]["object"]["key"])
    _marcar("S3#1", clave=clave, tenant=clave.split("/")[1])
