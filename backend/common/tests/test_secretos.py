import base64
import json
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError

from trazora_common import http, secretos, seguridad


@pytest.fixture
def manager(monkeypatch):
    cuenta = Mock()
    monkeypatch.setattr(secretos, "_cliente", cuenta)
    monkeypatch.setattr(secretos, "_cache", {})
    monkeypatch.setenv("STAGE", "test")
    monkeypatch.setenv("PASSWORD_PEPPER_SECRET", secretos.nombre("test"))
    return cuenta


def anillo(activa, versiones):
    return {"SecretString": json.dumps({"activa": activa, "claves": {
        v: base64.b64encode(bytes([i]) * 32).decode() for v, i in versiones.items()}})}


def test_rotacion_cache_y_contrasenas_previas(manager, monkeypatch):
    reloj = [1000]
    monkeypatch.setattr(secretos.time, "monotonic", lambda: reloj[0])
    manager.get_secret_value.return_value = anillo("v1", {"v1": 1})
    anterior = seguridad.hash_password("prueba", 1000)
    assert seguridad.verificar_password("prueba", anterior)
    assert manager.get_secret_value.call_count == 1
    reloj[0] += secretos.TTL + 1
    manager.get_secret_value.return_value = anillo("v2", {"v1": 1, "v2": 2})
    nuevo = seguridad.hash_password("prueba", 1000)
    assert "pepper:v2$" in nuevo and "pepper:v1$" in anterior
    assert seguridad.verificar_password("prueba", anterior)
    assert not seguridad.verificar_password("distinta", nuevo)
    assert manager.get_secret_value.call_count == 2


def test_un_secreto_de_otro_stage_no_se_lee(manager, monkeypatch):
    monkeypatch.setenv("PASSWORD_PEPPER_SECRET", secretos.nombre("prod"))
    with pytest.raises(http.ApiError) as fallo:
        seguridad.hash_password("nueva")
    assert fallo.value.status == 503
    manager.get_secret_value.assert_not_called()


@pytest.mark.parametrize("codigo", ["AccessDeniedException", "ResourceNotFoundException", "InvalidRequestException", "ThrottlingException"])
def test_error_de_secrets_no_filtra_el_valor_ni_se_cachea(manager, codigo, capsys):
    manager.get_secret_value.side_effect = ClientError({"Error": {"Code": codigo, "Message": "marcador-privado"}}, "GetSecretValue")

    @http.api_handler
    def crear(event, context):
        return seguridad.hash_password("prueba")

    respuesta = crear({}, None)
    assert respuesta["statusCode"] == 503 and "SECRETO_NO_DISPONIBLE" in respuesta["body"]
    salida = capsys.readouterr().out
    registro = json.loads(salida)
    assert registro["log_datos"]["aws_code"] == codigo
    assert "marcador-privado" not in salida + respuesta["body"]
    assert not secretos._cache


@pytest.mark.parametrize("valor", ["{", "null", "[]", '{"activa":"v","claves":{"v":"MA=="}}'])
def test_secreto_invalido_no_crea_hash(manager, valor):
    manager.get_secret_value.return_value = {"SecretString": valor}
    with pytest.raises(http.ApiError) as fallo:
        seguridad.hash_password("prueba", 1000)
    assert fallo.value.status == 503


def test_prod_sin_config_no_crea_password_y_lee_hash_anterior(manager, monkeypatch):
    monkeypatch.delenv("PASSWORD_PEPPER_SECRET")
    monkeypatch.setenv("STAGE", "dev")
    anterior = seguridad.hash_password("anterior", 1000)
    monkeypatch.setenv("STAGE", "prod")
    assert seguridad.verificar_password("anterior", anterior)
    with pytest.raises(http.ApiError):
        seguridad.hash_password("nueva", 1000)
    manager.get_secret_value.assert_not_called()
