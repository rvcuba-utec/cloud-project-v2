import os
import time
import uuid

from trazora_common import dynamo, logs, seguridad
from trazora_common.http import ApiError, api_handler, cuerpo_json, entrada_invalida, respuesta

from dominio.usuarios import (
    ACTIVO, DURACION_SESION_SEGUNDOS, normalizar_email, normalizar_tenant, pk, sk_email, sk_usuario,
)

_hash_ficticio = None


def _credenciales_invalidas():
    # Mismo error para cualquier causa: no revela qué cuentas o empresas existen.
    return ApiError(401, "CREDENCIALES_INVALIDAS", "Empresa, correo o contraseña incorrectos")


def _gastar_tiempo(password):
    """Iguala el tiempo de respuesta cuando la cuenta no existe."""
    global _hash_ficticio
    if _hash_ficticio is None:
        _hash_ficticio = seguridad.hash_password("sin-cuenta")
    seguridad.verificar_password(password, _hash_ficticio)


@api_handler
def lambda_handler(event, context):
    datos = cuerpo_json(event)
    tenant_id = normalizar_tenant(datos.get("tenant_id"))  # Único punto donde el cliente lo indica.
    password = datos.get("password")
    if not tenant_id or not isinstance(password, str) or not password:
        raise entrada_invalida("Empresa, correo y contraseña son obligatorios")
    email = normalizar_email(datos.get("email"))

    tabla = dynamo.tabla()
    marcador = tabla.get_item(Key={"PK": pk(tenant_id), "SK": sk_email(email)}).get("Item")
    usuario = None
    if marcador:
        usuario = tabla.get_item(
            Key={"PK": pk(tenant_id), "SK": sk_usuario(marcador["usuario_id"])}
        ).get("Item")

    almacenado = (usuario or {}).get("password_hash")
    if not almacenado:
        _gastar_tiempo(password)
        logs.info("login_rechazado", tenant_id=tenant_id, motivo="sin_credenciales")
        raise _credenciales_invalidas()
    if not seguridad.verificar_password(password, almacenado) or usuario.get("estado") != ACTIVO:
        logs.info("login_rechazado", tenant_id=tenant_id, usuario_id=usuario["usuario_id"])
        raise _credenciales_invalidas()

    token = str(uuid.uuid4())  # Token opaco con expiración, como en el taller 4.
    expira_en = int(time.time()) + DURACION_SESION_SEGUNDOS
    dynamo.tabla(os.environ["TABLA_SESIONES"]).put_item(Item={
        "token_hash": seguridad.hash_token(token),
        "usuario_id": usuario["usuario_id"],
        "tenant_id": tenant_id,
        "expira_en": expira_en,
    })
    logs.info("login", tenant_id=tenant_id, usuario_id=usuario["usuario_id"])
    return respuesta({"token": token, "expira_en": expira_en})
