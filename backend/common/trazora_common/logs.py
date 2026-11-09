"""Logs JSON para CloudWatch con el formato del taller 8: tipo y log_datos."""
import json

CAMPOS_SENSIBLES = {"password", "password_hash", "token", "token_hash", "authorization"}


def _limpiar(valor):
    if isinstance(valor, dict):
        return {
            k: "***" if str(k).lower() in CAMPOS_SENSIBLES else _limpiar(v) for k, v in valor.items()
        }
    if isinstance(valor, (list, tuple)):
        return [_limpiar(v) for v in valor]
    return valor


def _escribir(tipo, operacion, tenant_id, correlation_id, datos):
    registro = {"tipo": tipo, "operacion": operacion, "log_datos": _limpiar(datos)}
    if tenant_id:
        registro["tenant_id"] = tenant_id
    if correlation_id:
        registro["correlation_id"] = correlation_id
    print(json.dumps(registro, default=str, ensure_ascii=False))


def info(operacion, tenant_id=None, correlation_id=None, **datos):
    _escribir("INFO", operacion, tenant_id, correlation_id, datos)


def error(operacion, tenant_id=None, correlation_id=None, **datos):
    _escribir("ERROR", operacion, tenant_id, correlation_id, datos)
