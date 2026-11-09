"""Entrada y salida de las Lambdas de API (integración proxy de API Gateway)."""
import functools
import json
from decimal import Decimal

from . import logs

CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization,Idempotency-Key",
}


class ApiError(Exception):
    def __init__(self, status, codigo, mensaje, detalle=None):
        super().__init__(mensaje)
        self.status = status
        self.codigo = codigo
        self.mensaje = mensaje
        self.detalle = detalle or {}


def entrada_invalida(mensaje, **detalle):
    return ApiError(400, "ENTRADA_INVALIDA", mensaje, detalle)


def no_autenticado():
    return ApiError(401, "NO_AUTENTICADO", "Sesión no válida o vencida")


def prohibido(mensaje="No tienes permiso para esta operación"):
    return ApiError(403, "PROHIBIDO", mensaje)


def no_encontrado(recurso="Recurso"):
    # También se usa ante recursos de otro tenant, para no revelar que existen.
    return ApiError(404, "NO_ENCONTRADO", f"{recurso} no encontrado")


def conflicto(codigo, mensaje, **detalle):
    return ApiError(409, codigo, mensaje, detalle)


def _a_json(valor):
    if isinstance(valor, Decimal):
        return int(valor) if valor == valor.to_integral_value() else float(valor)
    if isinstance(valor, (set, frozenset)):
        return sorted(valor)
    raise TypeError(f"No serializable: {type(valor).__name__}")


def respuesta(cuerpo=None, status=200):
    return {
        "statusCode": status,
        "headers": {**CORS, "Content-Type": "application/json"},
        "body": "" if cuerpo is None else json.dumps(cuerpo, default=_a_json, ensure_ascii=False),
    }


def respuesta_error(error):
    return respuesta(
        {"error": {"codigo": error.codigo, "mensaje": error.mensaje, "detalle": error.detalle}},
        error.status,
    )


def cuerpo_json(event):
    bruto = event.get("body")
    if not bruto:
        return {}
    try:
        datos = json.loads(bruto)
    except (TypeError, ValueError):
        raise entrada_invalida("El cuerpo no es JSON válido")
    if not isinstance(datos, dict):
        raise entrada_invalida("El cuerpo debe ser un objeto JSON")
    return datos


def parametro_ruta(event, nombre):
    valor = (event.get("pathParameters") or {}).get(nombre)
    if not valor:
        raise entrada_invalida(f"Falta el parámetro {nombre}")
    return valor


def parametro_query(event, nombre, defecto=None):
    return (event.get("queryStringParameters") or {}).get(nombre, defecto)


def cabecera(event, nombre):
    buscada = nombre.lower()
    for clave, valor in (event.get("headers") or {}).items():
        if clave.lower() == buscada:
            return valor
    return None


def texto(datos, campo, maximo=500, obligatorio=True):
    valor = datos.get(campo)
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        if obligatorio:
            raise entrada_invalida(f"El campo {campo} es obligatorio", campo=campo)
        return None
    if not isinstance(valor, str) or len(valor) > maximo:
        raise entrada_invalida(f"El campo {campo} no es válido", campo=campo)
    return valor.strip()


def opcion(datos, campo, permitidas):
    valor = datos.get(campo)
    if not isinstance(valor, str) or valor not in permitidas:
        raise entrada_invalida(f"El campo {campo} no es válido", campo=campo, permitidas=sorted(permitidas))
    return valor


def api_handler(funcion):
    """Convierte excepciones en respuestas uniformes. Nunca registra el evento completo:
    contiene el token de Authorization."""

    @functools.wraps(funcion)
    def envoltura(event, context):
        try:
            return funcion(event, context)
        except ApiError as error:
            if error.status >= 500:
                logs.error("api", codigo=error.codigo, mensaje=error.mensaje)
            return respuesta_error(error)
        except Exception as error:  # Última barrera: sin detalles internos hacia el cliente.
            logs.error("api", tipo_error=type(error).__name__, mensaje=str(error))
            return respuesta_error(ApiError(500, "ERROR_INTERNO", "Ocurrió un error inesperado"))

    return envoltura
