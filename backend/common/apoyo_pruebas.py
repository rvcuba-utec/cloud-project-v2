"""Utilidades de las pruebas. No se despliega: sync solo copia trazora_common."""
import json

import boto3


def entorno_aws(monkeypatch, tabla):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "x")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "x")
    monkeypatch.setenv("TABLE_NAME", tabla)


def crear_tabla(nombre, *gsis):
    atributos = {"PK", "SK"} | {a for g in gsis for a in (f"{g}PK", f"{g}SK")}
    parametros = {}
    if gsis:
        parametros["GlobalSecondaryIndexes"] = [{
            "IndexName": g,
            "KeySchema": [{"AttributeName": f"{g}PK", "KeyType": "HASH"}, {"AttributeName": f"{g}SK", "KeyType": "RANGE"}],
            "Projection": {"ProjectionType": "ALL"},
        } for g in gsis]
    boto3.client("dynamodb").create_table(
        TableName=nombre, BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[{"AttributeName": a, "AttributeType": "S"} for a in sorted(atributos)],
        KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}],
        **parametros,
    )


def ctx(tenant="CLIMALIMA", rol="COORDINADOR", usuario="U1", tecnico=""):
    return {"usuario_id": usuario, "tenant_id": tenant, "rol": rol, "tecnico_id": tecnico}


def peticion(autorizador=None, body=None, ruta=None, query=None, headers=None):
    return {
        "body": json.dumps(body) if body is not None else None,
        "pathParameters": ruta,
        "queryStringParameters": query,
        "headers": headers or {},
        "requestContext": {"authorizer": autorizador} if autorizador else {},
    }


def cuerpo(respuesta):
    return json.loads(respuesta["body"])
