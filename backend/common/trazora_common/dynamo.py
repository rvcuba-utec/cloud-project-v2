"""Acceso a DynamoDB: paginación con cursor y transacciones."""
import base64
import json
import os
import time
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from .http import conflicto, entrada_invalida

LIMITE_MAXIMO = 100
LIMITE_DEFECTO = 25
_recurso = None


def recurso():
    global _recurso
    if _recurso is None:  # Se reutiliza entre invocaciones de la misma Lambda.
        _recurso = boto3.resource("dynamodb")
    return _recurso


def reiniciar():
    """Solo para pruebas: descarta el cliente guardado."""
    global _recurso
    _recurso = None


def tabla(nombre=None):
    return recurso().Table(nombre or os.environ["TABLE_NAME"])


def ahora_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def codificar_cursor(clave):
    if not clave:
        return None
    return base64.urlsafe_b64encode(json.dumps(clave).encode()).decode()


def decodificar_cursor(cursor, particion_esperada, atributo="PK"):
    """Rechaza cursores de otra partición: el cursor viene del cliente y no es confiable."""
    if not cursor:
        return None
    try:
        clave = json.loads(base64.urlsafe_b64decode(cursor.encode()))
    except (ValueError, TypeError):
        raise entrada_invalida("Cursor no válido")
    if not isinstance(clave, dict) or clave.get(atributo) != particion_esperada:
        raise entrada_invalida("Cursor no válido")
    return clave


def limite_valido(valor):
    try:
        limite = int(valor) if valor is not None else LIMITE_DEFECTO
    except (TypeError, ValueError):
        raise entrada_invalida("limit debe ser un número")
    if not 1 <= limite <= LIMITE_MAXIMO:
        raise entrada_invalida(f"limit debe estar entre 1 y {LIMITE_MAXIMO}")
    return limite


def consultar_pagina(tabla_ddb, pk, prefijo=None, limite=None, cursor=None, indice=None,
                     atributo_pk="PK", atributo_sk="SK", descendente=False, entre=None):
    """Una página de resultados dentro de una partición, por prefijo o por rango de SK."""
    condicion = Key(atributo_pk).eq(pk)
    if prefijo:
        condicion &= Key(atributo_sk).begins_with(prefijo)
    elif entre:
        condicion &= Key(atributo_sk).between(*entre)
    parametros = {
        "KeyConditionExpression": condicion,
        "Limit": limite_valido(limite),
        "ScanIndexForward": not descendente,
    }
    if indice:
        parametros["IndexName"] = indice
    inicio = decodificar_cursor(cursor, pk, atributo_pk)
    if inicio:
        parametros["ExclusiveStartKey"] = inicio
    resultado = tabla_ddb.query(**parametros)
    return {
        "items": resultado.get("Items", []),
        "next_cursor": codificar_cursor(resultado.get("LastEvaluatedKey")),
    }


def consultar_todo(tabla_ddb, pk, prefijo=None):
    """Recorre todas las páginas. Solo para conjuntos acotados, como los bloques de un día."""
    condicion = Key("PK").eq(pk)
    if prefijo:
        condicion &= Key("SK").begins_with(prefijo)
    items, inicio = [], None
    while True:
        parametros = {"KeyConditionExpression": condicion}
        if inicio:
            parametros["ExclusiveStartKey"] = inicio
        resultado = tabla_ddb.query(**parametros)
        items.extend(resultado.get("Items", []))
        inicio = resultado.get("LastEvaluatedKey")
        if not inicio:
            return items


def consultar_rango(tabla_ddb, pk, desde, hasta):
    """Todos los ítems con SK entre desde y hasta, incluidos ambos."""
    condicion = Key("PK").eq(pk) & Key("SK").between(desde, hasta)
    items, inicio = [], None
    while True:
        parametros = {"KeyConditionExpression": condicion}
        if inicio:
            parametros["ExclusiveStartKey"] = inicio
        resultado = tabla_ddb.query(**parametros)
        items.extend(resultado.get("Items", []))
        inicio = resultado.get("LastEvaluatedKey")
        if not inicio:
            return items


def vista(item):
    """Lo que sale hacia el cliente: sin claves ni atributos internos."""
    return {
        k: v for k, v in item.items()
        if k not in ("PK", "SK", "entity_type") and not k.startswith("GSI")
    }


class TransaccionCancelada(Exception):
    """Una condición de la transacción no se cumplió. `motivos` conserva el orden de los ítems."""

    def __init__(self, motivos):
        super().__init__(",".join(motivos))
        self.motivos = motivos

    def fallo_condicion(self, indice):
        return indice < len(self.motivos) and self.motivos[indice] == "ConditionalCheckFailed"


def transaccion(operaciones, intentos=3):
    """Aplica todas las operaciones o ninguna. Reintenta solo los conflictos entre transacciones;
    si se agotan, responde 409 para que el cliente o SQS vuelvan a intentar."""
    cliente = recurso().meta.client  # Admite tipos nativos de Python, igual que Table.
    for intento in range(intentos):
        try:
            cliente.transact_write_items(TransactItems=operaciones)
            return
        except ClientError as error:
            codigo = error.response["Error"]["Code"]
            if codigo == "TransactionConflictException":
                motivos = ["TransactionConflict"]
            elif codigo == "TransactionCanceledException":
                motivos = [r.get("Code", "None") for r in error.response.get("CancellationReasons", [])]
            else:
                raise
            if "ConditionalCheckFailed" in motivos:
                raise TransaccionCancelada(motivos)
            if "TransactionConflict" not in motivos:
                raise
            if intento == intentos - 1:
                raise conflicto("CONFLICTO_CONCURRENTE", "Otra operación está en curso. Intenta de nuevo.")
            time.sleep(0.05 * (2 ** intento))
