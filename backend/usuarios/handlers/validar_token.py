"""Lambda Authorizer. Devuelve el contexto confiable: usuario, tenant, rol y técnico."""
import os
import time

from trazora_common import dynamo, seguridad

from dominio.usuarios import ACTIVO, pk, sk_usuario


def _politica(method_arn, contexto):
    # Comodín sobre toda la API: la caché guarda esta política por token, y una política
    # limitada a la ruta actual rechazaría las demás (H11). Los roles se validan en cada Lambda.
    api_y_stage = "/".join(method_arn.split("/")[:2])
    return {
        "principalId": contexto["usuario_id"],
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [{
                "Action": "execute-api:Invoke",
                "Effect": "Allow",
                "Resource": f"{api_y_stage}/*/*",
            }],
        },
        "context": contexto,
    }


def lambda_handler(event, context):
    token = event.get("authorizationToken", "")
    if token.startswith("Bearer "):
        token = token[7:]
    if not token:
        raise Exception("Unauthorized")  # API Gateway lo convierte en 401; un Deny sería 403.

    sesion = dynamo.tabla(os.environ["TABLA_SESIONES"]).get_item(
        Key={"token_hash": seguridad.hash_token(token)}
    ).get("Item")
    if not sesion or int(sesion["expira_en"]) <= int(time.time()):
        raise Exception("Unauthorized")

    usuario = dynamo.tabla().get_item(
        Key={"PK": pk(sesion["tenant_id"]), "SK": sk_usuario(sesion["usuario_id"])}
    ).get("Item")
    if not usuario or usuario.get("estado") != ACTIVO:
        raise Exception("Unauthorized")

    return _politica(event["methodArn"], {
        "usuario_id": usuario["usuario_id"],
        "tenant_id": usuario["tenant_id"],
        "rol": usuario["rol"],
        "tecnico_id": usuario.get("tecnico_id") or "",  # El contexto solo admite texto.
    })
