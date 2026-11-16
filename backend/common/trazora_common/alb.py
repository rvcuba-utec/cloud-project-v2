"""Contrato entre API Gateway REST, el listener privado y los handlers HTTP."""
import base64
import binascii
import json
import os
from http.client import responses
from urllib.parse import unquote, unquote_plus

from .http import entrada_invalida, no_autenticado, no_encontrado

IDENTIDAD = "x-trazora-identity"
SOLICITUD = "x-trazora-request-id"
CAMPOS = ("usuario_id", "tenant_id", "rol", "tecnico_id")


def codificar_identidad(contexto):
    contenido = json.dumps({k: contexto[k] for k in CAMPOS}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(contenido).decode("ascii")


def _identidad(valor):
    try:
        datos = json.loads(base64.b64decode(valor, altchars=b"-_", validate=True))
        if (not isinstance(datos, dict) or set(datos) != set(CAMPOS)
                or not all(isinstance(datos[k], str) for k in CAMPOS)
                or not all(datos[k] for k in CAMPOS[:3])
                or datos["rol"] not in {"ADMIN", "COORDINADOR", "TECNICO"}):
            raise ValueError
    except (TypeError, ValueError, binascii.Error):
        raise no_autenticado() from None
    return datos


def token_autorizador(event):
    # Un REQUEST authorizer inspecciona lo que mandó el cliente antes del mapeo.
    # La caché del autorizador debe permanecer en cero para comprobar cada petición.
    simples = event.get("headers") or {}
    multiples = event.get("multiValueHeaders") or {}
    for nombre in (*simples, *multiples):
        clave = nombre.lower().removeprefix("x-amzn-remapped-")
        if clave in (IDENTIDAD, SOLICITUD) or nombre.lower() == "x-amzn-remapped-authorization":
            return ""
    if event.get("type") != "REQUEST":
        # Permite actualizar MS0 mientras el gateway anterior aún envía TOKEN.
        return event.get("authorizationToken", "")
    valores = [v for k, lista in multiples.items() if k.lower() == "authorization" for v in lista]
    if not valores:
        valores = [v for k, v in simples.items() if k.lower() == "authorization"]
    return valores[0] if len(valores) == 1 and "," not in valores[0] else ""


def _parametros(event, plantilla):
    segmentos = (event.get("path") or "").removeprefix("/").removesuffix("/").split("/")
    if segmentos[0] == os.environ["STAGE"]:
        segmentos = segmentos[1:]
    piezas = plantilla.strip("/").split("/")
    if len(piezas) != len(segmentos):
        raise no_encontrado("Ruta")
    parametros = {}
    for pieza, valor in zip(piezas, segmentos):
        if pieza.startswith("{"):
            valor = unquote(valor, errors="strict")
            if not valor or "/" in valor:
                raise no_encontrado("Ruta")
            parametros[pieza[1:-1]] = valor
        elif pieza != valor:
            raise no_encontrado("Ruta")
    return parametros


def peticion(event):
    metodo, plantilla = os.environ["ALB_RUTA"].split(" ", 1)
    if event.get("httpMethod") != metodo:
        raise no_encontrado("Ruta")
    protegida = (metodo, plantilla) != ("POST", "/auth/login")
    headers = {}
    for nombre, lista in (event.get("multiValueHeaders") or {}).items():
        clave = nombre.lower()
        if clave in {IDENTIDAD, "authorization"} and protegida:
            if clave in headers or len(lista) != 1 or "," in lista[0]:
                raise no_autenticado()
        if lista:
            headers[clave] = lista[-1]
    contexto = {"requestId": headers.pop(SOLICITUD, None)}
    proyectada = headers.pop(IDENTIDAD, None)
    if protegida:
        contexto["authorizer"] = _identidad(proyectada)
    try:
        parametros = _parametros(event, plantilla)
        query = {unquote_plus(k, errors="strict"): unquote_plus(v[-1], errors="strict")
                 for k, v in (event.get("multiValueQueryStringParameters") or {}).items() if v}
    except UnicodeError:
        raise entrada_invalida("La URL contiene una codificación inválida") from None
    return {"requestContext": contexto, "pathParameters": parametros, "queryStringParameters": query,
            "headers": headers, "body": event.get("body"), "isBase64Encoded": event.get("isBase64Encoded", False)}


def respuesta(resultado):
    codigo = resultado["statusCode"]
    return {"statusCode": codigo, "statusDescription": f"{codigo} {responses.get(codigo, 'Response')}",
            "isBase64Encoded": False, "body": resultado["body"],
            "multiValueHeaders": {k: [v] for k, v in resultado["headers"].items()}}
