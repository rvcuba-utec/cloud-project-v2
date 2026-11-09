"""Creaciones repetibles: la misma Idempotency-Key devuelve el mismo resultado."""
import hashlib
import json
import os

from . import dynamo
from .http import cabecera, conflicto, entrada_invalida

LARGO_MAXIMO = 100


def _sk(clave):
    return f"IDEMP#{clave}"


def _huella(datos):
    return hashlib.sha256(json.dumps(datos, sort_keys=True, default=str).encode()).hexdigest()


def _previo(tabla_ddb, pk, clave, huella):
    item = tabla_ddb.get_item(Key={"PK": pk, "SK": _sk(clave)}).get("Item")
    if not item:
        return None
    if item["huella"] != huella:
        raise conflicto("CLAVE_REUTILIZADA", "Esa clave de solicitud ya se usó con otros datos")
    return item["resultado"]


def crear(event, pk, datos, construir):
    """construir() devuelve (operaciones, resultado) y solo corre si no hay un resultado previo.
    Las llamadas a otros servicios van dentro de construir, para no repetirlas."""
    clave = cabecera(event, "Idempotency-Key")
    if clave and len(clave) > LARGO_MAXIMO:
        raise entrada_invalida("Idempotency-Key no es válida")
    tabla_ddb = dynamo.tabla()
    huella = _huella(datos)
    if clave:
        previo = _previo(tabla_ddb, pk, clave, huella)
        if previo is not None:
            return previo

    operaciones, resultado = construir()
    if clave:
        operaciones = operaciones + [{"Put": {
            "TableName": os.environ["TABLE_NAME"],
            "Item": {"PK": pk, "SK": _sk(clave), "entity_type": "IDEMP", "huella": huella, "resultado": resultado},
            "ConditionExpression": "attribute_not_exists(PK)",
        }}]
    try:
        dynamo.transaccion(operaciones)
    except dynamo.TransaccionCancelada:
        previo = _previo(tabla_ddb, pk, clave, huella) if clave else None
        if previo is None:
            raise
        return previo  # Dos envíos simultáneos: gana uno y el otro recibe su resultado.
    return resultado
