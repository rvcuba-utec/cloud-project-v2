"""Reglas de horarios y visitas, sin acceso a AWS. Instantes en UTC; jornadas en hora de Lima."""
from datetime import date, datetime, timedelta, timezone

from trazora_common.http import entrada_invalida

LIMA = timezone(timedelta(hours=-5))  # Perú no aplica horario de verano.
BLOQUE_MIN = 30
DURACION_MAXIMA_MIN = 240
PROGRAMADA = "PROGRAMADA"
EN_ATENCION = "EN_ATENCION"
FINALIZADA = "FINALIZADA"
CANCELADA = "CANCELADA"
FORMATO = "%Y-%m-%dT%H:%M:%SZ"


def leer_instante(valor, campo):
    try:
        return datetime.strptime(valor, FORMATO).replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        raise entrada_invalida(f"{campo} debe tener el formato AAAA-MM-DDTHH:MM:SSZ", campo=campo)


def iso(instante):
    return instante.astimezone(timezone.utc).strftime(FORMATO)


def fecha_lima(instante):
    return instante.astimezone(LIMA).date().isoformat()


def hora_lima(instante):
    return instante.astimezone(LIMA).strftime("%H:%M")


def a_utc(fecha, hora):
    """De fecha y hora de Lima a un instante."""
    return datetime.fromisoformat(f"{fecha}T{hora}:00").replace(tzinfo=LIMA).astimezone(timezone.utc)


def validar_fecha(valor, campo="fecha"):
    try:
        return date.fromisoformat(valor).isoformat()
    except (TypeError, ValueError):
        raise entrada_invalida(f"{campo} debe tener el formato AAAA-MM-DD", campo=campo)


def validar_horario(inicio_txt, fin_txt):
    inicio, fin = leer_instante(inicio_txt, "inicio"), leer_instante(fin_txt, "fin")
    if inicio.second or fin.second or inicio.minute % BLOQUE_MIN or fin.minute % BLOQUE_MIN:
        raise entrada_invalida("Los horarios deben ser múltiplos de 30 minutos")
    minutos = (fin - inicio).total_seconds() / 60
    if minutos <= 0 or minutos > DURACION_MAXIMA_MIN:
        raise entrada_invalida("La visita debe durar entre 30 minutos y 4 horas")
    if fecha_lima(inicio) != fecha_lima(fin - timedelta(seconds=1)):
        raise entrada_invalida("La visita debe empezar y terminar el mismo día")
    return inicio, fin


def bloques(inicio, fin):
    """Instantes de inicio de cada bloque. El extremo final no se incluye:
    otra visita puede empezar justo cuando esta termina."""
    resultado, actual = [], inicio
    while actual < fin:
        resultado.append(actual)
        actual += timedelta(minutes=BLOQUE_MIN)
    return resultado


def sk_visita(visita_id):
    return f"VISITA#{visita_id}"


def sk_control(orden_id):
    return f"CONTROL_ORDEN#{orden_id}"


def sk_bloque(tecnico_id, instante):
    return f"BLOQUE#{fecha_lima(instante)}#{tecnico_id}#{iso(instante)}"


def prefijo_bloques_dia(fecha):
    return f"BLOQUE#{fecha}#"


def claves_indices(tenant_id, tecnico_id, orden_id, inicio, visita_id):
    orden = f"{iso(inicio)}#{visita_id}"
    return {
        "GSI1PK": f"TENANT#{tenant_id}#TEC#{tecnico_id}", "GSI1SK": orden,
        "GSI2PK": f"TENANT#{tenant_id}#ORDEN#{orden_id}", "GSI2SK": orden,
        "GSI3PK": f"TENANT#{tenant_id}#FECHA#{fecha_lima(inicio)}", "GSI3SK": orden,
    }


def _minutos(hora):
    return int(hora[:2]) * 60 + int(hora[3:])


def dentro_de_jornada(intervalos, inicio, fin):
    desde, hasta = _minutos(hora_lima(inicio)), _minutos(hora_lima(fin))
    if hora_lima(fin) == "00:00":
        hasta = 24 * 60
    return any(_minutos(i["inicio"]) <= desde and hasta <= _minutos(i["fin"]) for i in intervalos)


def horarios_libres(intervalos, ocupados, duracion_min):
    """Horas de inicio posibles: todos los bloques de la visita deben estar libres."""
    if duracion_min <= 0 or duracion_min % BLOQUE_MIN or duracion_min > DURACION_MAXIMA_MIN:
        raise entrada_invalida("La duración debe ser múltiplo de 30 minutos, hasta 4 horas")
    ocupados_min = {_minutos(h) for h in ocupados}
    libres = []
    for intervalo in intervalos:
        inicio, tope = _minutos(intervalo["inicio"]), _minutos(intervalo["fin"])
        while inicio + duracion_min <= tope:
            if not any(m in ocupados_min for m in range(inicio, inicio + duracion_min, BLOQUE_MIN)):
                libres.append(f"{inicio // 60:02d}:{inicio % 60:02d}")
            inicio += BLOQUE_MIN
    return libres


def ordenar_candidatos(candidatos, metricas):
    """Filtros duros ya aplicados. Desempates: menor carga del día, luego mayor tasa de resolución.
    Sin métricas (Analítica no disponible): orden alfabético y sin justificación."""
    if not metricas:
        return sorted(candidatos, key=lambda c: c["nombre"])

    def clave(c):
        m = metricas.get(c["tecnico_id"], {})
        return (m.get("carga_dia", 0), -m.get("tasa_resolucion", 0), c["nombre"])

    ordenados = sorted(candidatos, key=clave)
    resultado = []
    for candidato in ordenados:
        m = metricas.get(candidato["tecnico_id"])
        if m:
            carga = m.get("carga_dia", 0)
            visitas = "1 visita" if carga == 1 else f"{carga} visitas"
            tasa = m.get("tasa_resolucion")
            detalle = "sin historial" if tasa is None else f"{round(tasa * 100)} % de resolución sin revisita"
            candidato = {**candidato, "justificacion": f"{visitas} ese día, {detalle}"}
        resultado.append(candidato)
    return resultado


def datos_evento(visita, **extra):
    return {
        "orden_id": visita["orden_id"], "visita_id": visita["visita_id"], "tecnico_id": visita["tecnico_id"],
        "fecha": visita["fecha"], "inicio": visita["inicio"], "fin": visita["fin"],
        "numero_visita_orden": int(visita["numero_visita_orden"]), **extra,
    }


def duracion_minutos(desde_txt, hasta_txt):
    desde, hasta = leer_instante(desde_txt, "desde"), leer_instante(hasta_txt, "hasta")
    return max(0, int((hasta - desde).total_seconds() // 60))
