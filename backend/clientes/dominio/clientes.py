"""Reglas de clientes y ubicaciones, sin acceso a AWS."""
import re
import unicodedata


def normalizar_nombre(nombre):
    """Búsqueda sin distinguir mayúsculas ni tildes."""
    sin_tildes = unicodedata.normalize("NFKD", nombre)
    limpio = "".join(c for c in sin_tildes if not unicodedata.combining(c)).lower()
    return re.sub(r"\s+", " ", limpio).strip()


LIMITES_COORDENADAS = {"lat": (-90, 90), "lng": (-180, 180)}


def coordenadas(datos):
    """Opcionales, pero juntas: el punto se elige en el mapa al registrar la ubicación."""
    from decimal import Decimal

    from trazora_common.http import entrada_invalida

    presentes = {k: datos.get(k) for k in LIMITES_COORDENADAS if datos.get(k) is not None}
    if not presentes:
        return {}
    if len(presentes) != 2:
        raise entrada_invalida("Indica latitud y longitud juntas", campo="lat")
    resultado = {}
    for campo, valor in presentes.items():
        minimo, maximo = LIMITES_COORDENADAS[campo]
        if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not minimo <= valor <= maximo:
            raise entrada_invalida(f"El campo {campo} no es válido", campo=campo)
        resultado[campo] = Decimal(str(round(valor, 6)))
    return resultado


def sk_cliente(cliente_id):
    return f"CLIENTE#{cliente_id}"


def sk_ubicacion(cliente_id, ubicacion_id):
    return f"UBICACION#{cliente_id}#{ubicacion_id}"


def particion_nombres(tenant_id):
    return f"TENANT#{tenant_id}#CLIENTE"


def orden_nombre(nombre, cliente_id):
    return f"{normalizar_nombre(nombre)}#{cliente_id}"
