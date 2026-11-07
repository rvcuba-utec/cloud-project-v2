from botocore.exceptions import ClientError

from trazora_common import dynamo, logs
from trazora_common.auth import ADMIN, TECNICO, obtener_contexto, requiere_rol
from trazora_common.http import (
    api_handler, cuerpo_json, entrada_invalida, no_encontrado, parametro_ruta, prohibido, respuesta,
)

from dominio.usuarios import ROLES, sk_usuario, texto_busqueda, validar_estado, vista_publica

CAMPOS = ("nombre", "rol", "estado", "tecnico_id")


@api_handler
def lambda_handler(event, context):
    contexto = obtener_contexto(event)
    requiere_rol(contexto, ADMIN)
    usuario_id = parametro_ruta(event, "usuario_id")
    datos = cuerpo_json(event)

    # Solo campos permitidos: tenant_id o password_hash en el cuerpo se ignoran.
    cambios = {c: datos[c] for c in CAMPOS if c in datos}
    if not cambios:
        raise entrada_invalida("No hay campos para actualizar")
    if usuario_id == contexto.usuario_id and ({"rol", "estado"} & cambios.keys()):
        raise prohibido("No puedes cambiar tu propio rol o estado")
    if "rol" in cambios and cambios["rol"] not in ROLES:
        raise entrada_invalida("Rol no válido")
    if "estado" in cambios:
        validar_estado(cambios["estado"])

    tabla = dynamo.tabla()
    clave = {"PK": contexto.pk, "SK": sk_usuario(usuario_id)}
    if cambios.get("rol") == TECNICO and not cambios.get("tecnico_id"):
        actual = tabla.get_item(Key=clave).get("Item") or {}
        if not actual.get("tecnico_id"):
            raise entrada_invalida("Una cuenta de técnico requiere tecnico_id")

    if "nombre" in cambios:
        actual = tabla.get_item(Key=clave).get("Item") or {}
        cambios["busqueda"] = texto_busqueda(cambios["nombre"], actual.get("email", ""))
    nombres = {f"#{c}": c for c in cambios}
    valores = {f":{c}": v for c, v in cambios.items()}
    try:
        resultado = tabla.update_item(
            Key=clave,  # La clave incluye el tenant del autorizador: otra empresa da 404.
            UpdateExpression="SET " + ", ".join(f"#{c} = :{c}" for c in cambios),
            ConditionExpression="attribute_exists(PK)",
            ExpressionAttributeNames=nombres,
            ExpressionAttributeValues=valores,
            ReturnValues="ALL_NEW",
        )
    except ClientError as error:
        if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise no_encontrado("Usuario")
        raise
    logs.info("usuario_actualizado", tenant_id=contexto.tenant_id, usuario_id=usuario_id, campos=list(cambios))
    return respuesta(vista_publica(resultado["Attributes"]))
