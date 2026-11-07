"""Traduce eventos a incrementos y contadores a métricas, sin acceso a AWS.

Solo hay sumas (H4): dan lo mismo en cualquier orden de llegada, así que no hace falta
comparar versiones. Las tasas no se guardan: se calculan al leer."""
from datetime import datetime, timedelta, timezone

LIMA = timezone(timedelta(hours=-5))
FORMATO = "%Y-%m-%dT%H:%M:%SZ"
RESUELTO = "RESUELTO"
REQUIERE_REVISITA = "REQUIERE_REVISITA"
SEGUNDOS_POR_DIA = 86400


def sk_metricas(tecnico_id):
    return f"METRICAS#{tecnico_id}"


def sk_dia(fecha, tecnico_id):
    return f"DIA#{fecha}#{tecnico_id}"


def sk_dashboard(periodo):
    return f"DASHBOARD#{periodo}"


def _instante(valor):
    return datetime.strptime(valor, FORMATO).replace(tzinfo=timezone.utc)


def periodo_de_instante(valor):
    return _instante(valor).astimezone(LIMA).strftime("%Y-%m")


def hoy_lima():
    return datetime.now(LIMA).date().isoformat()


def periodo_actual():
    return hoy_lima()[:7]


class _Cambios:
    """Reúne por ítem: una transacción no admite dos operaciones sobre el mismo ítem."""

    def __init__(self):
        self.items = {}

    def sumar(self, sk, atributos, **incrementos):
        item = self.items.setdefault(sk, {"atributos": atributos, "sumas": {}})
        for nombre, valor in incrementos.items():
            item["sumas"][nombre] = item["sumas"].get(nombre, 0) + valor

    def dia(self, fecha, tecnico_id, **incrementos):
        self.sumar(sk_dia(fecha, tecnico_id), {"entity_type": "SNAPSHOT_TECNICO_DIA", "tecnico_id": tecnico_id, "fecha": fecha}, **incrementos)

    def tecnico(self, tecnico_id, **incrementos):
        self.sumar(sk_metricas(tecnico_id), {"entity_type": "METRICAS_TECNICO", "tecnico_id": tecnico_id}, **incrementos)

    def mes(self, periodo, **incrementos):
        self.sumar(sk_dashboard(periodo), {"entity_type": "SNAPSHOT_TENANT", "periodo": periodo}, **incrementos)

    def resultado(self):
        """Los que quedan en cero no se escriben: reprogramar dentro del mismo día no cambia nada."""
        finales = {}
        for sk, item in self.items.items():
            sumas = {k: v for k, v in item["sumas"].items() if v}
            if sumas:
                finales[sk] = {"atributos": item["atributos"], "sumas": sumas}
        return finales


def efectos(evento):
    """{sk: {atributos, sumas}} para aplicar. Un evento desconocido o incompleto lanza excepción y va a la DLQ."""
    tipo, datos = evento["event_type"], evento["data"]
    cambios = _Cambios()
    if tipo == "VisitaProgramada":
        cambios.dia(datos["fecha"], datos["tecnico_id"], visitas_asignadas=1)
        cambios.mes(datos["fecha"][:7], visitas_programadas=1)
    elif tipo == "VisitaReprogramada":
        cambios.dia(datos["fecha_anterior"], datos["tecnico_anterior"], visitas_asignadas=-1)
        cambios.dia(datos["fecha"], datos["tecnico_id"], visitas_asignadas=1)
        cambios.mes(datos["fecha_anterior"][:7], visitas_programadas=-1)
        cambios.mes(datos["fecha"][:7], visitas_programadas=1)
    elif tipo == "VisitaCancelada":
        cambios.dia(datos["fecha"], datos["tecnico_id"], visitas_asignadas=-1)
        cambios.mes(datos["fecha"][:7], visitas_programadas=-1)
    elif tipo == "VisitaCompletada":
        resultado = datos["resultado"]
        revisita = 1 if resultado == REQUIERE_REVISITA else 0
        primera = datos["numero_visita_orden"] == 1
        cambios.tecnico(
            datos["tecnico_id"],
            visitas_completadas_total=1, suma_minutos=datos["duracion_min"], revisitas_generadas=revisita,
            primer_intento_total=1 if primera else 0,
            primer_intento_resueltos=1 if primera and resultado == RESUELTO else 0,
        )
        cambios.dia(datos["fecha"], datos["tecnico_id"], visitas_completadas=1, revisitas_generadas=revisita)
        cambios.mes(datos["fecha"][:7], visitas_programadas=-1, visitas_completadas=1)
    elif tipo == "OrdenCreada":
        cambios.mes(periodo_de_instante(datos["creada_en"]), ordenes_creadas=1, ordenes_abiertas=1)
    elif tipo in ("OrdenCerrada", "OrdenCancelada"):
        cambios.mes(periodo_de_instante(datos["creada_en"]), ordenes_abiertas=-1)
        periodo_fin = periodo_de_instante(datos["terminada_en"])
        if tipo == "OrdenCerrada":
            segundos = int((_instante(datos["terminada_en"]) - _instante(datos["creada_en"])).total_seconds())
            cambios.mes(periodo_fin, ordenes_cerradas=1, suma_segundos_cierre=max(0, segundos))
        else:
            cambios.mes(periodo_fin, ordenes_canceladas=1)
    else:
        raise ValueError(f"Evento no esperado: {tipo}")
    return cambios.resultado()


def _entero(item, campo):
    return int(item.get(campo, 0)) if item else 0


def _no_negativo(item, campo):
    """Un evento anterior a esta tabla puede dejar un contador en negativo: no se muestra así."""
    return max(0, _entero(item, campo))


def metricas_de_tecnico(tecnico_id, acumulado, dia):
    completadas = _entero(acumulado, "visitas_completadas_total")
    primer_total = _entero(acumulado, "primer_intento_total")
    salida = {
        "tecnico_id": tecnico_id,
        "carga_dia": _no_negativo(dia, "visitas_asignadas"),
        "completadas_dia": _entero(dia, "visitas_completadas"),
        "visitas_completadas_total": completadas,
        "revisitas_generadas": _entero(acumulado, "revisitas_generadas"),
    }
    # Sin historial no se inventa un 0 %: el campo simplemente no aparece.
    if primer_total:
        salida["tasa_resolucion"] = round(_entero(acumulado, "primer_intento_resueltos") / primer_total, 4)
    if completadas:
        salida["tiempo_promedio_min"] = round(_entero(acumulado, "suma_minutos") / completadas, 1)
    return salida


def resumen_de_mes(periodo, item):
    cerradas = _entero(item, "ordenes_cerradas")
    salida = {
        "periodo": periodo,
        "ordenes_creadas": _entero(item, "ordenes_creadas"),
        "ordenes_abiertas": _no_negativo(item, "ordenes_abiertas"),
        "ordenes_cerradas": cerradas,
        "ordenes_canceladas": _entero(item, "ordenes_canceladas"),
        "visitas_programadas": _no_negativo(item, "visitas_programadas"),
        "visitas_completadas": _entero(item, "visitas_completadas"),
    }
    if cerradas:
        salida["tiempo_promedio_cierre_dias"] = round(_entero(item, "suma_segundos_cierre") / cerradas / SEGUNDOS_POR_DIA, 1)
    return salida
