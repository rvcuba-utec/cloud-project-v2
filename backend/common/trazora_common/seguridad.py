"""Contraseñas PBKDF2 y tokens opacos. MS0 admite hashes anteriores al pepper."""
import base64
import hashlib
import hmac
import os
import secrets

from . import secretos

ALGORITMO = "pbkdf2_sha256"
ITERACIONES = 120_000  # Se ajusta midiendo el login con Logs Insights (talleres 6 y 8).


def _material(password, clave):
    return hmac.digest(clave, password.encode("utf-8"), "sha256")


def hash_password(password, iteraciones=ITERACIONES):
    sal = secrets.token_bytes(16)
    algoritmo = ALGORITMO
    material = password.encode("utf-8")
    if os.environ.get("PASSWORD_PEPPER_SECRET") or os.environ.get("STAGE") in {"test", "prod"}:
        version, claves = secretos.cargar()
        algoritmo = f"{ALGORITMO}_pepper:{version}"
        material = _material(password, claves[version])
    derivada = hashlib.pbkdf2_hmac("sha256", material, sal, iteraciones)
    partes = (base64.b64encode(sal).decode(), base64.b64encode(derivada).decode())
    return f"{algoritmo}${iteraciones}${partes[0]}${partes[1]}"


def verificar_password(password, almacenado):
    try:
        algoritmo, iteraciones, sal, esperado = almacenado.split("$")
        if algoritmo == ALGORITMO:
            material = password.encode("utf-8")
        elif algoritmo.startswith(ALGORITMO + "_pepper:"):
            material = _material(password, secretos.para_verificar(algoritmo.split(":", 1)[1]))
        else:
            return False
        derivada = hashlib.pbkdf2_hmac("sha256", material, base64.b64decode(sal), int(iteraciones))
        return hmac.compare_digest(derivada, base64.b64decode(esperado))
    except (AttributeError, TypeError, ValueError):
        return False


def hash_token(token):
    """Lo que se guarda en la tabla de sesiones: una filtración no entrega tokens usables."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def password_aleatoria():
    return base64.urlsafe_b64encode(os.urandom(15)).decode()
