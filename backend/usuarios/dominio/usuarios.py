"""Reglas de usuarios, sin acceso a AWS."""
import re

from trazora_common.auth import ADMIN, COORDINADOR, TECNICO
from trazora_common.http import entrada_invalida

ROLES = {ADMIN, COORDINADOR, TECNICO}
ACTIVO = "ACTIVO"
INACTIVO = "INACTIVO"
ESTADOS = {ACTIVO, INACTIVO}
DURACION_SESION_SEGUNDOS = 8 * 3600
LARGO_MINIMO_PASSWORD = 8
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PRIVADOS = {"PK", "SK", "password_hash", "entity_type"}


def pk(tenant_id):
    return f"TENANT#{tenant_id}"


def sk_usuario(usuario_id):
    return f"USUARIO#{usuario_id}"


def sk_email(email):
    return f"EMAIL#{email}"


SK_EMPRESA = "EMPRESA"


def normalizar_email(valor):
    email = str(valor or "").strip().lower()
    if not _EMAIL.match(email):
        raise entrada_invalida("El correo no es válido")
    return email


def normalizar_tenant(valor):
    return str(valor or "").strip().upper()


def validar_rol(rol, tecnico_id):
    if rol not in ROLES:
        raise entrada_invalida("Rol no válido")
    if rol == TECNICO and not tecnico_id:
        raise entrada_invalida("Una cuenta de técnico requiere tecnico_id")


def validar_estado(estado):
    if estado not in ESTADOS:
        raise entrada_invalida("Estado no válido")


def validar_password(password):
    if not isinstance(password, str) or len(password) < LARGO_MINIMO_PASSWORD:
        raise entrada_invalida(f"La contraseña debe tener al menos {LARGO_MINIMO_PASSWORD} caracteres")


def vista_publica(item):
    """Lo único que sale hacia el cliente: nunca el hash ni las claves internas."""
    return {k: v for k, v in item.items() if k not in PRIVADOS}
