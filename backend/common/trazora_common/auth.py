"""Identidad de la petición. Sale solo del contexto que entrega el autorizador:
nunca del body, la ruta ni la query."""
from dataclasses import dataclass

from .http import cabecera, no_autenticado, prohibido

ADMIN = "ADMIN"
COORDINADOR = "COORDINADOR"
TECNICO = "TECNICO"


@dataclass(frozen=True)
class Contexto:
    usuario_id: str
    tenant_id: str
    rol: str
    tecnico_id: str | None = None

    @property
    def pk(self):
        return f"TENANT#{self.tenant_id}"


def obtener_contexto(event):
    datos = (event.get("requestContext") or {}).get("authorizer") or {}
    usuario_id, tenant_id, rol = datos.get("usuario_id"), datos.get("tenant_id"), datos.get("rol")
    if not (usuario_id and tenant_id and rol):
        raise no_autenticado()
    # El autorizador solo puede devolver texto, así que la ausencia llega como cadena vacía.
    return Contexto(usuario_id, tenant_id, rol, datos.get("tecnico_id") or None)


def requiere_rol(contexto, *roles):
    if contexto.rol not in roles:
        raise prohibido()


def token_de_peticion(event):
    """Token del usuario, para reenviarlo en llamadas a otros servicios."""
    valor = cabecera(event, "Authorization") or ""
    return valor[7:] if valor.startswith("Bearer ") else valor
