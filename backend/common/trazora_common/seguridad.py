"""Contraseñas y tokens, solo con la librería estándar."""
import base64
import hashlib
import hmac
import os
import secrets

ALGORITMO = "pbkdf2_sha256"
ITERACIONES = 120_000  # Se ajusta midiendo el login con Logs Insights (talleres 6 y 8).


def _derivar(password, sal, iteraciones):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), sal, iteraciones)


def hash_password(password, iteraciones=ITERACIONES):
    sal = secrets.token_bytes(16)
    derivada = _derivar(password, sal, iteraciones)
    partes = (base64.b64encode(sal).decode(), base64.b64encode(derivada).decode())
    return f"{ALGORITMO}${iteraciones}${partes[0]}${partes[1]}"


def verificar_password(password, almacenado):
    try:
        algoritmo, iteraciones, sal, esperado = almacenado.split("$")
        if algoritmo != ALGORITMO:
            return False
        derivada = _derivar(password, base64.b64decode(sal), int(iteraciones))
        return hmac.compare_digest(derivada, base64.b64decode(esperado))
    except (AttributeError, TypeError, ValueError):
        return False


def hash_token(token):
    """Lo que se guarda en la tabla de sesiones: una filtración no entrega tokens usables."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def password_aleatoria():
    return base64.urlsafe_b64encode(os.urandom(15)).decode()
