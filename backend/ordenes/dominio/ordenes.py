"""Reglas de órdenes, sin acceso a AWS."""
import time
import uuid

TIPOS_SERVICIO = {"INSTALACION", "MANTENIMIENTO", "REPARACION"}
PRIORIDADES = {"BAJA", "MEDIA", "ALTA"}
ABIERTA = "ABIERTA"
ESTADOS = {
    ABIERTA, "PROGRAMADA", "EN_ATENCION", "REQUIERE_REVISITA",
    "PENDIENTE_DE_CIERRE", "CIERRE_EN_PROCESO", "CERRADA", "CANCELADA",
}
TERMINALES = {"CERRADA", "CANCELADA"}


def nuevo_id():
    """Empieza por el tiempo: el listado queda en orden cronológico sin otro índice."""
    return f"OT-{int(time.time() * 1000):013d}-{uuid.uuid4().hex[:8]}"


def sk_orden(orden_id):
    return f"ORDEN#{orden_id}"


def sk_historial(orden_id, instante, sufijo):
    return f"HIST#{orden_id}#{instante}#{sufijo}"


def particion_estado(tenant_id, estado):
    return f"TENANT#{tenant_id}#ESTADO#{estado}"


def particion_cliente(tenant_id, cliente_id):
    return f"TENANT#{tenant_id}#CLIENTE#{cliente_id}"
