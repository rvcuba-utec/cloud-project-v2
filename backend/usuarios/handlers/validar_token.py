"""Lambda Authorizer. Devuelve el contexto confiable: usuario, tenant, rol y técnico."""
import os
import time

from trazora_common import dynamo, logs, seguridad

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


def _token(event):
    """Token del encabezado Authorization. Admite autorizadores REQUEST y TOKEN."""
    if event.get("type") != "REQUEST":
        return event.get("authorizationToken", "")
    valores = [v for k, vs in (event.get("multiValueHeaders") or {}).items()
               if k.lower() == "authorization" for v in vs]
    if not valores:
        valores = [v for k, v in (event.get("headers") or {}).items() if k.lower() == "authorization"]
    # Un encabezado repetido es ambiguo: se rechaza en vez de elegir uno.
    return valores[0] if len(valores) == 1 and "," not in valores[0] else ""


@logs.lambda_evento
def lambda_handler(event, context):
    token = _token(event)
    if token.startswith("Bearer "):
        token = token[7:]
    if not token:
        raise logs.SinSesion("Unauthorized")  # API Gateway lo convierte en 401; un Deny sería 403.

    sesion = dynamo.tabla(os.environ["TABLA_SESIONES"]).get_item(
        Key={"token_hash": seguridad.hash_token(token)}
    ).get("Item")
    if not sesion or int(sesion["expira_en"]) <= int(time.time()):
        raise logs.SinSesion("Unauthorized")

    usuario = dynamo.tabla().get_item(
        Key={"PK": pk(sesion["tenant_id"]), "SK": sk_usuario(sesion["usuario_id"])}
    ).get("Item")
    if not usuario or usuario.get("estado") != ACTIVO:
        raise logs.SinSesion("Unauthorized")

    return _politica(event["methodArn"], {
        "usuario_id": usuario["usuario_id"],
        "tenant_id": usuario["tenant_id"],
        "rol": usuario["rol"],
        "tecnico_id": usuario.get("tecnico_id") or "",  # El contexto solo admite texto.
    })
