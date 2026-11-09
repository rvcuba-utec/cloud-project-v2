import json
import os
from decimal import Decimal
from unittest import mock

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from trazora_common import auth, dynamo, eventos, http, logs, seguridad

TABLA = "dev-t_prueba"


@pytest.fixture
def aws(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "prueba")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "prueba")
    monkeypatch.setenv("TABLE_NAME", TABLA)
    with mock_aws():
        dynamo.reiniciar()
        eventos.reiniciar()
        boto3.client("dynamodb").create_table(
            TableName=TABLA,
            BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
        )
        tema = boto3.client("sns").create_topic(Name="eventos")["TopicArn"]
        monkeypatch.setenv("TOPIC_ARN", tema)
        yield
        dynamo.reiniciar()
        eventos.reiniciar()


def evento_api(body=None, autorizador=None, headers=None):
    return {
        "body": body,
        "headers": headers or {},
        "requestContext": {"authorizer": autorizador} if autorizador else {},
    }


AUTORIZADOR = {"usuario_id": "U1", "tenant_id": "CLIMALIMA", "rol": "COORDINADOR", "tecnico_id": ""}


# ---- Identidad
def test_contexto_sale_solo_del_autorizador():
    event = evento_api(body=json.dumps({"tenant_id": "FRIOSUR"}), autorizador=AUTORIZADOR)
    event["queryStringParameters"] = {"tenant_id": "FRIOSUR"}
    contexto = auth.obtener_contexto(event)
    assert contexto.tenant_id == "CLIMALIMA"
    assert contexto.pk == "TENANT#CLIMALIMA"
    assert contexto.tecnico_id is None


def test_sin_autorizador_es_401():
    with pytest.raises(http.ApiError) as error:
        auth.obtener_contexto(evento_api())
    assert error.value.status == 401


def test_requiere_rol():
    contexto = auth.Contexto("U1", "CLIMALIMA", auth.TECNICO)
    auth.requiere_rol(contexto, auth.TECNICO)
    with pytest.raises(http.ApiError) as error:
        auth.requiere_rol(contexto, auth.ADMIN, auth.COORDINADOR)
    assert error.value.status == 403


def test_token_de_peticion_ignora_mayusculas_de_cabecera():
    assert auth.token_de_peticion(evento_api(headers={"authorization": "Bearer abc"})) == "abc"


# ---- Respuestas
def test_respuesta_serializa_decimal_y_lleva_cors():
    r = http.respuesta({"entero": Decimal("3"), "real": Decimal("0.95")})
    assert json.loads(r["body"]) == {"entero": 3, "real": 0.95}
    assert r["headers"]["Access-Control-Allow-Origin"] == "*"
    assert "Idempotency-Key" in r["headers"]["Access-Control-Allow-Headers"]


def test_api_handler_traduce_errores():
    @http.api_handler
    def conflicto(event, context):
        raise http.conflicto("HORARIO_OCUPADO", "Ese horario ya se ocupó")

    r = conflicto({}, None)
    assert r["statusCode"] == 409
    assert json.loads(r["body"])["error"]["codigo"] == "HORARIO_OCUPADO"


def test_api_handler_no_filtra_errores_internos(capsys):
    @http.api_handler
    def roto(event, context):
        raise ValueError("detalle interno")

    r = roto({}, None)
    assert r["statusCode"] == 500
    assert "detalle interno" not in r["body"]
    assert "detalle interno" in capsys.readouterr().out


@pytest.mark.parametrize("cuerpo", ["no es json", "[1, 2]"])
def test_cuerpo_invalido_es_400(cuerpo):
    with pytest.raises(http.ApiError) as error:
        http.cuerpo_json({"body": cuerpo})
    assert error.value.status == 400


@pytest.mark.parametrize("valor", [["ALTA"], {"a": 1}, 1, None])
def test_opcion_con_tipo_incorrecto_es_400(valor):
    with pytest.raises(http.ApiError) as error:
        http.opcion({"campo": valor}, "campo", {"ALTA"})
    assert error.value.status == 400


# ---- Logs
def test_logs_ocultan_secretos(capsys):
    logs.info("login", tenant_id="T", datos={"password": "x1", "token": "x2", "email": "a@b"})
    salida = capsys.readouterr().out
    registro = json.loads(salida)
    assert registro["tipo"] == "INFO" and registro["tenant_id"] == "T"
    assert "x1" not in salida and "x2" not in salida and "a@b" in salida


# ---- Seguridad
def test_password():
    almacenado = seguridad.hash_password("clave segura", iteraciones=1000)
    assert "clave segura" not in almacenado
    assert seguridad.verificar_password("clave segura", almacenado)
    assert not seguridad.verificar_password("otra", almacenado)
    assert not seguridad.verificar_password("clave segura", "formato invalido")
    assert not seguridad.verificar_password("clave segura", None)


def test_hash_password_usa_sal_distinta():
    assert seguridad.hash_password("a", 1000) != seguridad.hash_password("a", 1000)


# ---- Paginación
def test_paginacion_recorre_todo_y_no_mezcla_tenants(aws):
    t = dynamo.tabla()
    for i in range(5):
        t.put_item(Item={"PK": "TENANT#A", "SK": f"CLIENTE#{i}"})
    t.put_item(Item={"PK": "TENANT#B", "SK": "CLIENTE#X"})
    t.put_item(Item={"PK": "TENANT#A", "SK": "UBICACION#1"})

    primera = dynamo.consultar_pagina(t, "TENANT#A", "CLIENTE#", limite=3)
    assert len(primera["items"]) == 3 and primera["next_cursor"]
    segunda = dynamo.consultar_pagina(t, "TENANT#A", "CLIENTE#", limite=3, cursor=primera["next_cursor"])
    claves = [i["SK"] for i in primera["items"] + segunda["items"]]
    assert claves == [f"CLIENTE#{i}" for i in range(5)]
    assert segunda["next_cursor"] is None


def test_cursor_de_otro_tenant_se_rechaza(aws):
    cursor = dynamo.codificar_cursor({"PK": "TENANT#B", "SK": "CLIENTE#X"})
    with pytest.raises(http.ApiError) as error:
        dynamo.consultar_pagina(dynamo.tabla(), "TENANT#A", cursor=cursor)
    assert error.value.status == 400


@pytest.mark.parametrize("valor", ["0", "101", "abc"])
def test_limite_invalido(valor):
    with pytest.raises(http.ApiError):
        dynamo.limite_valido(valor)


# ---- Transacciones
def _put(sk, condicion=None, **extra):
    operacion = {"Put": {"TableName": TABLA, "Item": {"PK": "TENANT#A", "SK": sk, **extra}}}
    if condicion:
        operacion["Put"]["ConditionExpression"] = condicion
    return operacion


def test_transaccion_es_todo_o_nada(aws):
    dynamo.transaccion([_put("BLOQUE#1", "attribute_not_exists(PK)", dueno="V1")])
    with pytest.raises(dynamo.TransaccionCancelada) as error:
        dynamo.transaccion([
            _put("VISITA#2"),
            _put("BLOQUE#1", "attribute_not_exists(PK)", dueno="V2"),
        ])
    assert error.value.fallo_condicion(1)
    t = dynamo.tabla()
    assert "Item" not in t.get_item(Key={"PK": "TENANT#A", "SK": "VISITA#2"})
    assert t.get_item(Key={"PK": "TENANT#A", "SK": "BLOQUE#1"})["Item"]["dueno"] == "V1"


def test_transaccion_agota_reintentos_con_409(aws):
    error = ClientError(
        {"Error": {"Code": "TransactionCanceledException"},
         "CancellationReasons": [{"Code": "TransactionConflict"}]},
        "TransactWriteItems",
    )
    with mock.patch.object(dynamo.recurso().meta.client, "transact_write_items", side_effect=error) as llamada, \
            mock.patch("time.sleep"):
        with pytest.raises(http.ApiError) as resultado:
            dynamo.transaccion([_put("X")], intentos=3)
    assert resultado.value.status == 409
    assert llamada.call_count == 3


# ---- Eventos
def _evento():
    return eventos.crear_evento("ParteFinalizado", "CLIMALIMA", "PARTE", "P1", 1, {"visita_id": "V1"})


def _guardar_con_outbox(evento):
    dynamo.transaccion([_put("PARTE#P1"), eventos.operacion_outbox(evento)])


def _pendientes():
    return dynamo.consultar_todo(dynamo.tabla(), "TENANT#CLIMALIMA", eventos.PREFIJO_OUTBOX)


def _cola_suscrita():
    sqs, sns = boto3.client("sqs"), boto3.client("sns")
    url = sqs.create_queue(QueueName="q")["QueueUrl"]
    arn = sqs.get_queue_attributes(QueueUrl=url, AttributeNames=["QueueArn"])["Attributes"]["QueueArn"]
    sns.subscribe(TopicArn=os.environ["TOPIC_ARN"], Protocol="sqs", Endpoint=arn)
    return sqs, url


def test_publicar_y_borrar_entrega_con_atributos_y_limpia(aws):
    sqs, url = _cola_suscrita()
    evento = _evento()
    _guardar_con_outbox(evento)
    assert len(_pendientes()) == 1

    assert eventos.publicar_y_borrar(evento) is True
    assert _pendientes() == []

    mensaje = sqs.receive_message(QueueUrl=url)["Messages"][0]
    sobre = json.loads(mensaje["Body"])
    assert sobre["MessageAttributes"]["event_type"]["Value"] == "ParteFinalizado"
    leido = eventos.leer_mensaje_sqs({"Records": [{"body": mensaje["Body"]}]})
    assert leido["event_id"] == evento["event_id"]


def test_fallo_al_publicar_deja_pendiente_y_el_barrido_recupera_sin_cambiar_id(aws, monkeypatch, capsys):
    sqs, url = _cola_suscrita()
    evento = _evento()
    _guardar_con_outbox(evento)

    tema = os.environ["TOPIC_ARN"]
    monkeypatch.setenv("TOPIC_ARN", tema + "-inexistente")
    assert eventos.publicar_y_borrar(evento) is False
    assert len(_pendientes()) == 1
    assert '"tipo": "ERROR"' in capsys.readouterr().out

    monkeypatch.setenv("TOPIC_ARN", tema)
    monkeypatch.setenv("TENANTS", "CLIMALIMA,FRIOSUR")
    assert eventos.manejador_barrido({}, None) == {"reenviados": 1}
    assert _pendientes() == []
    mensaje = sqs.receive_message(QueueUrl=url)["Messages"][0]
    assert eventos.leer_mensaje_sqs({"Records": [{"body": mensaje["Body"]}]})["event_id"] == evento["event_id"]


def test_barrido_sin_pendientes_no_publica(aws, monkeypatch):
    monkeypatch.setenv("TENANTS", "CLIMALIMA")
    assert eventos.manejador_barrido({}, None) == {"reenviados": 0}


def test_inbox_impide_aplicar_dos_veces(aws):
    def aplicar():
        dynamo.transaccion([
            eventos.operacion_inbox("E1", "A"),
            {"Update": {
                "TableName": TABLA,
                "Key": {"PK": "TENANT#A", "SK": "METRICAS#T1"},
                "UpdateExpression": "ADD visitas :uno",
                "ExpressionAttributeValues": {":uno": 1},
            }},
        ])

    aplicar()
    with pytest.raises(dynamo.TransaccionCancelada) as error:
        aplicar()
    assert error.value.fallo_condicion(0)
    item = dynamo.tabla().get_item(Key={"PK": "TENANT#A", "SK": "METRICAS#T1"})["Item"]
    assert item["visitas"] == 1
