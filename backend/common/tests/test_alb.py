"""Contrato ALB con cabeceras multivalor y parámetros codificados en la URL."""
import base64

import pytest

from apoyo_pruebas import ctx, cuerpo, evento_alb
from trazora_common import alb, auth, http


@http.api_handler
def eco(event, context):
    identidad = auth.obtener_contexto(event)
    return http.respuesta({
        "tenant": identidad.tenant_id, "tecnico": identidad.tecnico_id,
        "id": http.parametro_ruta(event, "id"), "q": http.parametro_query(event, "q"),
        "clave": http.cabecera(event, "Idempotency-Key"), "token": auth.token_de_peticion(event),
        "body": http.cuerpo_json(event),
    }, 201)


@pytest.fixture(autouse=True)
def entorno(monkeypatch):
    monkeypatch.setenv("STAGE", "test")
    monkeypatch.setenv("ALB_RUTA", "PUT /recursos/{id}")


@pytest.mark.parametrize("prefijo", ["", "/test"])
def test_adapta_con_y_sin_stage(prefijo):
    identidad = ctx(rol="TECNICO", tecnico="TEC-1")
    event = evento_alb("PUT", prefijo + "/recursos/T%20Uno", alb.codificar_identidad(identidad),
                       query={"q": ["anterior", "d%C3%ADa+1%2B2"]},
                       headers={"Authorization": ["Bearer token-local"], "Idempotency-Key": ["ref-1"]})
    event.update(body=base64.b64encode(b'{"valor":42}').decode(), isBase64Encoded=True)
    r = eco(event, None)
    assert r["statusCode"] == 201 and r["statusDescription"] == "201 Created" and not r["isBase64Encoded"]
    assert cuerpo(r) == {"tenant": "CLIMALIMA", "tecnico": "TEC-1", "id": "T Uno", "q": "día 1+2",
                         "clave": "ref-1", "token": "token-local", "body": {"valor": 42}}
    assert r["multiValueHeaders"]["Access-Control-Allow-Origin"] == ["*"]


@pytest.mark.parametrize("headers", [{}, {alb.IDENTIDAD: ["invalida"]}, {alb.IDENTIDAD: ["e30="]},
                                      {alb.IDENTIDAD: ["a", "b"]}, {alb.IDENTIDAD: ["a,b"]},
                                      {alb.IDENTIDAD: ["a"], alb.IDENTIDAD.upper(): ["b"]}])
def test_falta_identidad_valida(headers):
    event = evento_alb("PUT", "/test/recursos/1", headers=headers)
    event["requestContext"]["authorizer"] = ctx("FRIOSUR")
    r = eco(event, None)
    assert r["statusCode"] == 401 and cuerpo(r)["error"]["codigo"] == "NO_AUTENTICADO"
    assert len(r["multiValueHeaders"]["X-Request-Id"]) == 1


@pytest.mark.parametrize(("metodo", "ruta"), [("POST", "/recursos/1"), ("PUT", "/dev/recursos/1"),
                                             ("PUT", "/recursos/1/2"), ("PUT", "/recursos/%2F")])
def test_fuera_de_la_regla(metodo, ruta):
    r = eco(evento_alb(metodo, ruta, alb.codificar_identidad(ctx())), None)
    assert r["statusCode"] == 404


def test_error_de_cuerpo_codificado():
    event = evento_alb("PUT", "/recursos/1", alb.codificar_identidad(ctx()))
    event.update(isBase64Encoded=True, body="inválido")
    r = eco(event, None)
    assert r["statusCode"] == 400 and "request_id" in cuerpo(r)["error"]


def test_funcion_configurada_requiere_ingreso_alb():
    r = eco({"requestContext": {"authorizer": ctx()}}, None)
    assert r["statusCode"] == 401
