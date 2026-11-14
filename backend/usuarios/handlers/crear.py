import os
import uuid

from trazora_common import dynamo, logs, seguridad
from trazora_common.auth import ADMIN, obtener_contexto, requiere_rol
from trazora_common.http import api_handler, conflicto, cuerpo_json, respuesta, texto

from dominio.usuarios import (
    ACTIVO, LARGO_MAXIMO_ID, LARGO_MAXIMO_NOMBRE, normalizar_email, sk_email, sk_usuario, texto_busqueda,
    validar_password, validar_rol, vista_publica,
)
from handlers.vinculo import exigir_tecnico


@api_handler
def lambda_handler(event, context):
    contexto = obtener_contexto(event)
    requiere_rol(contexto, ADMIN)
    datos = cuerpo_json(event)

    email = normalizar_email(datos.get("email"))
    nombre = texto(datos, "nombre", LARGO_MAXIMO_NOMBRE)
    password = datos.get("password")
    validar_password(password)
    rol = datos.get("rol")
    tecnico_id = texto(datos, "tecnico_id", LARGO_MAXIMO_ID, obligatorio=False)
    validar_rol(rol, tecnico_id)
    if tecnico_id:
        exigir_tecnico(contexto.tenant_id, tecnico_id)

    usuario_id = str(uuid.uuid4())
    usuario = {
        "PK": contexto.pk,
        "SK": sk_usuario(usuario_id),
        "entity_type": "USUARIO",
        "tenant_id": contexto.tenant_id,  # Siempre el del autorizador.
        "usuario_id": usuario_id,
        "email": email,
        "nombre": nombre,
        "busqueda": texto_busqueda(nombre, email),
        "rol": rol,
        "estado": ACTIVO,
        "password_hash": seguridad.hash_password(password),
        "creado_en": dynamo.ahora_iso(),
    }
    if tecnico_id:
        usuario["tecnico_id"] = tecnico_id

    tabla = os.environ["TABLE_NAME"]
    try:
        # H10: el marcador garantiza un correo único por empresa, incluso en concurrencia.
        dynamo.transaccion([
            {"Put": {
                "TableName": tabla,
                "Item": {"PK": contexto.pk, "SK": sk_email(email), "entity_type": "EMAIL", "usuario_id": usuario_id},
                "ConditionExpression": "attribute_not_exists(PK)",
            }},
            {"Put": {"TableName": tabla, "Item": usuario}},
        ])
    except dynamo.TransaccionCancelada:
        raise conflicto("CORREO_EN_USO", "Ya existe un usuario con ese correo en la empresa")

    logs.info("usuario_creado", tenant_id=contexto.tenant_id, usuario_id=usuario_id, rol=rol)
    return respuesta(vista_publica(usuario), 201)
