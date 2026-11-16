"""Pepper de contraseñas de MS0. El valor permanece en la memoria de la Lambda."""
import base64
import binascii
import json
import os
import re
import time

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from .http import ApiError
from .sdk import LECTURA

TTL = 300
_cliente = None
_cache = {}


def nombre(stage):
    return f"trazora/{stage}/usuarios/password-pepper"


def _no_disponible():
    return ApiError(503, "SECRETO_NO_DISPONIBLE", "El servicio de acceso está temporalmente indisponible")


def _validar(valor):
    datos = json.loads(valor)
    if not isinstance(datos, dict) or set(datos) != {"activa", "claves"}:
        raise ValueError("Formato de configuración inválido")
    claves = datos["claves"]
    if not isinstance(claves, dict) or not isinstance(datos["activa"], str) or datos["activa"] not in claves:
        raise ValueError("Versión activa inválida")
    decodificadas = {}
    for version, texto in claves.items():
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", version) or not isinstance(texto, str):
            raise ValueError("Versión de clave inválida")
        clave = base64.b64decode(texto, validate=True)
        if len(clave) < 32:
            raise ValueError("Clave inválida")
        decodificadas[version] = clave
    return datos["activa"], decodificadas


def cargar():
    global _cliente
    stage = os.getenv("STAGE")
    secreto = os.getenv("PASSWORD_PEPPER_SECRET")
    if not stage or secreto != nombre(stage):
        raise _no_disponible()
    ahora = time.monotonic()
    previo = _cache.get(secreto)
    if previo and ahora < previo[0]:
        return previo[1]
    try:
        if _cliente is None:
            _cliente = boto3.client("secretsmanager", config=LECTURA)
        respuesta = _cliente.get_secret_value(SecretId=secreto, VersionStage="AWSCURRENT")
        anillo = _validar(respuesta["SecretString"])
    except (ClientError, BotoCoreError, KeyError, ValueError, TypeError, binascii.Error) as exc:
        raise _no_disponible() from exc
    _cache[secreto] = (ahora + TTL, anillo)
    return anillo


def para_verificar(version):
    _, claves = cargar()
    if version not in claves:
        # Durante una rotación un contenedor caliente puede conservar el anillo anterior.
        # Solo las versiones de hashes persistidos llegan aquí.
        _cache.pop(os.environ["PASSWORD_PEPPER_SECRET"], None)
        _, claves = cargar()
    if version not in claves:
        raise _no_disponible()
    return claves[version]
