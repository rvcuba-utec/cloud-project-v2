"""Contra AWS real, en secuencia y con pocas peticiones."""
import uuid

import pytest

from apoyo import http

ORIGEN = {"Origin": "https://main.ejemplo.amplifyapp.com"}


def test_sin_token_401_con_cors(api_usuarios):
    estado, cab, _ = http(f"{api_usuarios}/usuarios/me", cabeceras=ORIGEN)
    assert estado == 401
    assert cab.get("access-control-allow-origin") == "*"


def test_token_invalido_401_con_cors(api_usuarios):
    estado, cab, _ = http(f"{api_usuarios}/usuarios/me", token="no-existe", cabeceras=ORIGEN)
    assert estado == 401
    assert cab.get("access-control-allow-origin") == "*"


def test_login_incorrecto(api_usuarios, cuentas):
    c = cuentas[("CLIMALIMA", "ADMIN")]
    estado, cab, datos = http(f"{api_usuarios}/auth/login", "POST", cuerpo={**c, "password": "incorrecta"})
    assert estado == 401 and datos["error"]["codigo"] == "CREDENCIALES_INVALIDAS"
    assert cab.get("access-control-allow-origin") == "*"


def test_credenciales_de_una_empresa_no_sirven_en_otra(api_usuarios, cuentas):
    c = cuentas[("CLIMALIMA", "ADMIN")]
    estado, _, _ = http(f"{api_usuarios}/auth/login", "POST", cuerpo={**c, "tenant_id": "FRIOSUR"})
    assert estado == 401


def test_perfil_muestra_empresa_y_rol_sin_datos_privados(api_usuarios, token_de):
    estado, _, datos = http(f"{api_usuarios}/usuarios/me", token=token_de("FRIOSUR", "COORDINADOR"))
    assert estado == 200
    assert datos["tenant_nombre"] == "FríoSur" and datos["rol"] == "COORDINADOR"
    assert "password_hash" not in datos


def test_caché_del_autorizador_sirve_para_otras_rutas(api_usuarios, token_de):
    token = token_de("CLIMALIMA")
    assert http(f"{api_usuarios}/usuarios/me", token=token)[0] == 200
    assert http(f"{api_usuarios}/usuarios?limit=1", token=token)[0] == 200


def test_lista_de_usuarios_aislada_aunque_se_pida_otra_empresa(api_usuarios, token_de):
    estado, _, datos = http(f"{api_usuarios}/usuarios?tenant_id=FRIOSUR", token=token_de("CLIMALIMA"))
    assert estado == 200 and datos["items"]
    assert {u["tenant_id"] for u in datos["items"]} == {"CLIMALIMA"}


def test_coordinador_no_administra_usuarios(api_usuarios, token_de):
    assert http(f"{api_usuarios}/usuarios", token=token_de("CLIMALIMA", "COORDINADOR"))[0] == 403


def test_no_modifica_usuario_de_otra_empresa(api_usuarios, token_de):
    _, _, propios = http(f"{api_usuarios}/usuarios", token=token_de("FRIOSUR"))
    ajeno = propios["items"][0]["usuario_id"]
    estado, _, _ = http(f"{api_usuarios}/usuarios/{ajeno}", "PATCH", token_de("CLIMALIMA"), {"nombre": "Intruso"})
    assert estado == 404


def test_verificacion_previa_permite_idempotency_key(api_usuarios):
    estado, cab, _ = http(f"{api_usuarios}/usuarios", "OPTIONS", cabeceras={
        **ORIGEN, "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,idempotency-key,content-type",
    })
    assert estado == 200
    assert "idempotency-key" in cab.get("access-control-allow-headers", "").lower()


@pytest.mark.muta
def test_alta_login_y_desactivacion(api_usuarios, token_de):
    admin = token_de("CLIMALIMA")
    email = f"prueba-{uuid.uuid4().hex[:8]}@climalima.example.com"
    password = uuid.uuid4().hex
    estado, _, usuario = http(f"{api_usuarios}/usuarios", "POST", admin, {
        "email": email, "nombre": "Prueba", "password": password, "rol": "COORDINADOR",
    })
    assert estado == 201 and "password_hash" not in usuario

    credenciales = {"tenant_id": "CLIMALIMA", "email": email, "password": password}
    estado, _, sesion = http(f"{api_usuarios}/auth/login", "POST", cuerpo=credenciales)
    assert estado == 200
    assert http(f"{api_usuarios}/usuarios/me", token=sesion["token"])[0] == 200

    estado, _, _ = http(f"{api_usuarios}/usuarios/{usuario['usuario_id']}", "PATCH", admin, {"estado": "INACTIVO"})
    assert estado == 200
    assert http(f"{api_usuarios}/auth/login", "POST", cuerpo=credenciales)[0] == 401
