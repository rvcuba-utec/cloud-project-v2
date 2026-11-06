"""Reglas de clientes y ubicaciones, sin acceso a AWS."""
import re
import unicodedata


def normalizar_nombre(nombre):
    """Búsqueda sin distinguir mayúsculas ni tildes."""
    sin_tildes = unicodedata.normalize("NFKD", nombre)
    limpio = "".join(c for c in sin_tildes if not unicodedata.combining(c)).lower()
    return re.sub(r"\s+", " ", limpio).strip()


def sk_cliente(cliente_id):
    return f"CLIENTE#{cliente_id}"


def sk_ubicacion(cliente_id, ubicacion_id):
    return f"UBICACION#{cliente_id}#{ubicacion_id}"


def particion_nombres(tenant_id):
    return f"TENANT#{tenant_id}#CLIENTE"


def orden_nombre(nombre, cliente_id):
    return f"{normalizar_nombre(nombre)}#{cliente_id}"
