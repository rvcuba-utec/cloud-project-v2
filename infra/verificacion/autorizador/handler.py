def lambda_handler(event, context):
    token = event.get("authorizationToken", "")
    token = token[7:] if token.startswith("Bearer ") else token
    if token != "token-de-verificacion":
        raise Exception("Unauthorized")  # API Gateway responde 401
    partes = event["methodArn"].split("/")
    recurso = "/".join(partes[:2]) + "/*/*"  # Comodín: la caché vale para todas las rutas
    return {
        "principalId": "U-VERIF",
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [{"Action": "execute-api:Invoke", "Effect": "Allow", "Resource": recurso}],
        },
        "context": {"usuario_id": "U-VERIF", "tenant_id": "VERIF", "rol": "ADMIN", "tecnico_id": ""},
    }
