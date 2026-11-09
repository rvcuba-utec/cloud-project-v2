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


ESTADO_DE_VISITA = {
    "VisitaProgramada": "PROGRAMADA",
    "VisitaReprogramada": "PROGRAMADA",
    "VisitaIniciada": "EN_ATENCION",
    "VisitaCancelada": "CANCELADA",
    "VisitaCompletada": "FINALIZADA",
}


def derivar_estado(resumen):
    """El estado sale de las visitas vigentes, no del último evento recibido.
    Una atención resuelta deja la orden lista para revisar: no la cierra por sí sola."""
    vigentes = [v for v in resumen.values() if v["estado"] != "CANCELADA"]
    if not vigentes:
        return ABIERTA
    estados = {v["estado"] for v in vigentes}
    if "EN_ATENCION" in estados:
        return "EN_ATENCION"
    if "PROGRAMADA" in estados:
        return "PROGRAMADA"
    ultima = max(vigentes, key=lambda v: v["numero"])
    return "PENDIENTE_DE_CIERRE" if ultima.get("resultado") == "RESUELTO" else "REQUIERE_REVISITA"


def resumen_con_evento(resumen, evento):
    """Devuelve el resumen actualizado, o None si el evento es atrasado para esa visita."""
    datos = evento["data"]
    actual = resumen.get(datos["visita_id"])
    if actual and actual["version"] >= evento["aggregate_version"]:
        return None
    entrada = {
        "estado": ESTADO_DE_VISITA[evento["event_type"]],
        "version": evento["aggregate_version"],
        "numero": datos["numero_visita_orden"],
    }
    if "resultado" in datos:
        entrada["resultado"] = datos["resultado"]
    return {**resumen, datos["visita_id"]: entrada}


DETALLE_HISTORIAL = {
    "VisitaProgramada": "Visita {n} programada",
    "VisitaReprogramada": "Visita {n} reprogramada",
    "VisitaIniciada": "Visita {n} iniciada",
    "VisitaCancelada": "Visita {n} cancelada",
    "VisitaCompletada": "Visita {n} completada",
}
RESULTADOS_TEXTO = {"RESUELTO": "resuelto", "REQUIERE_REVISITA": "requiere otra visita", "NO_ATENDIDO": "no atendido"}
