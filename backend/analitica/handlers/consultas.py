import re
from datetime import date

from trazora_common import dynamo, interno
from trazora_common.auth import ADMIN, COORDINADOR, obtener_contexto, requiere_rol
from trazora_common.http import api_handler, entrada_invalida, parametro_query, parametro_ruta, respuesta

from dominio.analitica import (
    hoy_lima, metricas_de_tecnico, periodo_actual, resumen_de_mes, sk_dashboard, sk_dia, sk_metricas,
)

MESES_HISTORICO = 12


def fecha_valida(fecha):
    """Formato y calendario: 2026-02-30 no es un día."""
    if not isinstance(fecha, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha):
        return False
    try:
        date.fromisoformat(fecha)
    except ValueError:
        return False
    return True


def _fecha(event):
    fecha = parametro_query(event, "fecha") or hoy_lima()
    if not fecha_valida(fecha):
        raise entrada_invalida("fecha debe tener el formato AAAA-MM-DD", campo="fecha")
    return fecha


@api_handler
def dashboard(event, context):
    contexto = obtener_contexto(event)
    requiere_rol(contexto, ADMIN, COORDINADOR)
    periodo = parametro_query(event, "periodo") or periodo_actual()
    if not fecha_valida(f"{periodo}-01"):
        raise entrada_invalida("periodo debe tener el formato AAAA-MM", campo="periodo")
    tabla_ddb = dynamo.tabla()
    item = tabla_ddb.get_item(Key={"PK": contexto.pk, "SK": sk_dashboard(periodo)}).get("Item")
    historico = dynamo.consultar_pagina(tabla_ddb, contexto.pk, "DASHBOARD#", limite=MESES_HISTORICO, descendente=True)
    return respuesta({
        **resumen_de_mes(periodo, item),
        "historico": [resumen_de_mes(i["periodo"], i) for i in historico["items"]],
    })


@api_handler
def tecnicos(event, context):
    """Dos consultas por prefijo, sin importar cuánto historial tenga cada técnico (H3)."""
    contexto = obtener_contexto(event)
    requiere_rol(contexto, ADMIN, COORDINADOR)
    fecha = _fecha(event)
    return respuesta({"fecha": fecha, "items": ranking(contexto.pk, fecha)})


def ranking(pk, fecha):
    tabla_ddb = dynamo.tabla()
    acumulados = {i["tecnico_id"]: i for i in dynamo.consultar_todo(tabla_ddb, pk, "METRICAS#")}
    dias = {i["tecnico_id"]: i for i in dynamo.consultar_todo(tabla_ddb, pk, f"DIA#{fecha}#")}
    return [metricas_de_tecnico(t, acumulados.get(t), dias.get(t)) for t in sorted({*acumulados, *dias})]


def tecnicos_interno(event, context):
    """Sin ruta: la invoca Agenda con lambda.invoke al reasignar por un evento, sin token de usuario."""
    fecha = event["fecha"]
    if not fecha_valida(fecha):
        raise ValueError("fecha no válida")
    return interno.serializable({"fecha": fecha, "items": ranking(f"TENANT#{event['tenant_id']}", fecha)})


@api_handler
def tecnico(event, context):
    contexto = obtener_contexto(event)
    requiere_rol(contexto, ADMIN, COORDINADOR)
    tecnico_id = parametro_ruta(event, "tecnico_id")
    fecha = _fecha(event)
    tabla_ddb = dynamo.tabla()
    acumulado = tabla_ddb.get_item(Key={"PK": contexto.pk, "SK": sk_metricas(tecnico_id)}).get("Item")
    dia = tabla_ddb.get_item(Key={"PK": contexto.pk, "SK": sk_dia(fecha, tecnico_id)}).get("Item")
    return respuesta({"fecha": fecha, **metricas_de_tecnico(tecnico_id, acumulado, dia)})
