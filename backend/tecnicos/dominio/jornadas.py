"""Reglas de técnicos y jornadas, sin acceso a AWS."""
import re
from datetime import date

from trazora_common.http import entrada_invalida

ESPECIALIDADES = {"INSTALACION", "MANTENIMIENTO", "REPARACION"}
_HORA = re.compile(r"^([01]\d|2[0-3]):(00|30)$")
MAX_DIAS_CONSULTA = 62


def sk_tecnico(tecnico_id):
    return f"TECNICO#{tecnico_id}"


def sk_jornada(tecnico_id, fecha):
    return f"JORNADA#{tecnico_id}#{fecha}"


def sk_ausencia(tecnico_id, fecha):
    return f"AUSENCIA#{tecnico_id}#{fecha}"


def validar_fecha(valor, campo="fecha"):
    try:
        return date.fromisoformat(valor).isoformat()
    except (TypeError, ValueError):
        raise entrada_invalida(f"{campo} debe tener el formato AAAA-MM-DD", campo=campo)


def validar_especialidades(valor):
    if not isinstance(valor, list) or not valor or not set(valor) <= ESPECIALIDADES:
        raise entrada_invalida("Especialidades no válidas", permitidas=sorted(ESPECIALIDADES))
    return sorted(set(valor))


def validar_intervalos(valor):
    """Horas locales de Lima en múltiplos de 30 minutos, ordenadas y sin solaparse."""
    if not isinstance(valor, list) or not valor:
        raise entrada_invalida("Debe indicar al menos un intervalo")
    intervalos = []
    for intervalo in valor:
        inicio = intervalo.get("inicio") if isinstance(intervalo, dict) else None
        fin = intervalo.get("fin") if isinstance(intervalo, dict) else None
        if not (isinstance(inicio, str) and isinstance(fin, str) and _HORA.match(inicio) and _HORA.match(fin)):
            raise entrada_invalida("Las horas deben ser HH:00 o HH:30")
        if inicio >= fin:
            raise entrada_invalida("El inicio debe ser anterior al fin")
        intervalos.append({"inicio": inicio, "fin": fin})
    intervalos.sort(key=lambda i: i["inicio"])
    for anterior, siguiente in zip(intervalos, intervalos[1:]):
        if siguiente["inicio"] < anterior["fin"]:
            raise entrada_invalida("Los intervalos no pueden solaparse")
    return intervalos


def validar_rango(desde, hasta):
    inicio, fin = validar_fecha(desde, "desde"), validar_fecha(hasta, "hasta")
    if fin < inicio:
        raise entrada_invalida("El rango de fechas no es válido")
    if (date.fromisoformat(fin) - date.fromisoformat(inicio)).days > MAX_DIAS_CONSULTA:
        raise entrada_invalida(f"El rango máximo es de {MAX_DIAS_CONSULTA} días")
    return inicio, fin
