"""Llamadas síncronas entre microservicios, reenviando el token del usuario."""
import json
import urllib.error
import urllib.request

from .http import ApiError

TIMEOUT_SEGUNDOS = 8


def llamar(base_url, ruta, token, metodo="GET", cuerpo=None, timeout=TIMEOUT_SEGUNDOS):
    """Devuelve el JSON de la respuesta. Un 4xx del otro servicio se propaga con su código;
    un fallo de red o un 5xx se traducen en 503, para que quien llama pueda decidir."""
    datos = None if cuerpo is None else json.dumps(cuerpo).encode("utf-8")
    peticion = urllib.request.Request(
        f"{base_url.rstrip('/')}{ruta}",
        data=datos,
        method=metodo,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:
            contenido = respuesta.read()
            return json.loads(contenido) if contenido else None
    except urllib.error.HTTPError as error:
        if error.code >= 500:
            raise ApiError(503, "SERVICIO_NO_DISPONIBLE", "Un servicio relacionado no respondió")
        try:
            detalle = json.loads(error.read()).get("error", {})
        except ValueError:
            detalle = {}
        raise ApiError(
            error.code,
            detalle.get("codigo", "ERROR_SERVICIO"),
            detalle.get("mensaje", "Error en un servicio relacionado"),
            detalle.get("detalle"),
        )
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ApiError(503, "SERVICIO_NO_DISPONIBLE", "Un servicio relacionado no respondió")


_lambda = None


def invocar(nombre_funcion, carga):
    """Invocación directa de una función sin ruta (H1). Un fallo de la otra función es una excepción."""
    import boto3

    global _lambda
    if _lambda is None:
        _lambda = boto3.client("lambda")
    resultado = _lambda.invoke(FunctionName=nombre_funcion, Payload=json.dumps(carga).encode())
    if resultado.get("FunctionError"):
        raise RuntimeError(f"Falló la función {nombre_funcion}")
    return json.loads(resultado["Payload"].read())


def serializable(valor):
    """Lo que devuelve una función invocada debe ser JSON: DynamoDB entrega Decimal."""
    from .http import _a_json

    return json.loads(json.dumps(valor, default=_a_json))
