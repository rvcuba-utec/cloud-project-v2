"""Contexto de invocación y registros JSON que CloudWatch puede indexar."""
import functools
import json
import logging
import os
import re
import traceback
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import PurePath

from botocore.exceptions import ClientError

_contexto = ContextVar("invocacion", default={})
# Solo estos campos operativos llegan al log. Los valores libres (body, URL, mensajes
# de excepciones, cabeceras o datos de personas) nunca se serializan.
_CAMPOS = {
    "codigo", "tipo_error", "motivo", "usuario_id", "tecnico_id", "cliente_id",
    "visita_id", "parte_id", "evidencia_id", "estado", "event_id", "event_type",
    "rol", "fecha", "tabla", "visitas_activas", "reasignadas", "alertas", "reenviados",
    "aws_code", "aws_operation", "intento", "clasificacion", "message_id",
}
_IDENTIFICADOR = re.compile(r"[A-Za-z0-9_.:#/-]{1,128}\Z")


def identificador(valor):
    return valor if isinstance(valor, str) and _IDENTIFICADOR.fullmatch(valor) else None


@contextmanager
def invocacion(funcion, event, context):
    gateway = (event.get("requestContext") or {}) if isinstance(event, dict) else {}
    identidad = gateway.get("authorizer") or {}
    rid = identificador(getattr(context, "aws_request_id", None)) or identificador(gateway.get("requestId")) or str(uuid.uuid4())
    campos = {
        "service": os.getenv("SERVICE_NAME", "local"), "stage": os.getenv("STAGE", "local"),
        "function": getattr(context, "function_name", None) or os.getenv("AWS_LAMBDA_FUNCTION_NAME") or funcion.__name__,
        "request_id": rid, "correlation_id": identificador(gateway.get("requestId")) or rid,
        "tenant_id": identificador(identidad.get("tenant_id")),
    }
    marca = _contexto.set(campos)
    try:
        yield rid
    finally:
        _contexto.reset(marca)


def contexto_http(peticion):
    actual = _contexto.get()
    _contexto.set({**actual, "correlation_id": identificador(peticion.get("requestId")) or actual["request_id"],
                   "tenant_id": identificador((peticion.get("authorizer") or {}).get("tenant_id"))})


def _registro(nivel, operacion, tenant_id=None, correlation_id=None, **datos):
    campos = {}
    for clave, valor in datos.items():
        if clave in _CAMPOS:
            if isinstance(valor, (int, bool)) or identificador(valor):
                campos[clave] = valor
    registro = {
        **_contexto.get(), "severity": nivel, "tipo": nivel, "event_type": operacion,
        "operation": operacion, "operacion": operacion, "log_datos": campos,
    }
    if identificador(tenant_id):
        registro["tenant_id"] = tenant_id
    if identificador(correlation_id):
        registro["correlation_id"] = correlation_id
    return registro


class _SalidaJson(logging.Handler):
    def emit(self, record):
        print(record.getMessage())


_logger = logging.getLogger(__name__)
_logger.propagate = False
_logger.setLevel(logging.INFO)
if not _logger.handlers:
    _logger.addHandler(_SalidaJson())


def _emitir(registro):
    _logger.log(logging.getLevelName(registro["severity"]), json.dumps(registro, ensure_ascii=False))


def info(operacion, tenant_id=None, correlation_id=None, **datos):
    _emitir(_registro("INFO", operacion, tenant_id, correlation_id, **datos))


def error(operacion, tenant_id=None, correlation_id=None, **datos):
    _emitir(_registro("ERROR", operacion, tenant_id, correlation_id, **datos))


def fallo(operacion, exc, codigo, *, nivel="ERROR", **datos):
    causa = exc
    # Los adaptadores de dominio pueden traducir una excepción del SDK a ApiError.
    for _ in range(5):
        anterior = causa.__cause__ or (None if causa.__suppress_context__ else causa.__context__)
        if anterior is None:
            break
        causa = anterior
    if isinstance(causa, ClientError):
        datos["aws_code"] = causa.response.get("Error", {}).get("Code")
        datos["aws_operation"] = causa.operation_name
    r = _registro(nivel, operacion, **datos)
    r.update(error_code=codigo, exception_type=type(causa).__name__)
    if nivel == "ERROR":
        # El traceback estándar incluye str(exc) y líneas de código. Conservamos
        # archivo, función y línea, suficientes para localizar la causa sin datos.
        r["stacktrace"] = [
            f"{PurePath(f.filename).name}:{f.lineno}:{f.name}"
            for f in traceback.extract_tb(causa.__traceback__)[-16:]
        ]
        _logger.exception(json.dumps(r, ensure_ascii=False), exc_info=False)
    else:
        _emitir(r)


class SinSesion(Exception):
    """API Gateway reconoce exactamente el texto Unauthorized."""


def lambda_evento(funcion):
    @functools.wraps(funcion)
    def recibir(event, context):
        with invocacion(funcion, event, context) as rid:
            try:
                return funcion(event, context)
            except SinSesion as exc:
                fallo(funcion.__name__, exc, "NO_AUTENTICADO", nivel="WARNING")
                raise
            except ValueError as exc:
                fallo(funcion.__name__, exc, "ENTRADA_EVENTO_INVALIDA")
                raise ValueError(f"ENTRADA_EVENTO_INVALIDA {rid}") from None
            except Exception as exc:
                fallo(funcion.__name__, exc, "FALLO_LAMBDA")
                raise RuntimeError(f"FALLO_LAMBDA {rid}") from None
    return recibir
