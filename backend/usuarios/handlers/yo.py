from trazora_common import dynamo
from trazora_common.auth import obtener_contexto
from trazora_common.http import api_handler, no_encontrado, respuesta

from dominio.usuarios import SK_EMPRESA, sk_usuario, vista_publica


@api_handler
def lambda_handler(event, context):
    contexto = obtener_contexto(event)
    tabla = dynamo.tabla()
    usuario = tabla.get_item(Key={"PK": contexto.pk, "SK": sk_usuario(contexto.usuario_id)}).get("Item")
    if not usuario:
        raise no_encontrado("Usuario")
    empresa = tabla.get_item(Key={"PK": contexto.pk, "SK": SK_EMPRESA}).get("Item") or {}
    return respuesta({**vista_publica(usuario), "tenant_nombre": empresa.get("nombre", contexto.tenant_id)})
