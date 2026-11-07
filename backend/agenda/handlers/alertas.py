"""Lo que el coordinador debe atender ahora, y lo que el sistema resolvió solo."""
from trazora_common import dynamo
from trazora_common.auth import ADMIN, COORDINADOR, obtener_contexto, requiere_rol
from trazora_common.http import api_handler, respuesta

RECIENTES = 15


@api_handler
def listar(event, context):
    contexto = obtener_contexto(event)
    requiere_rol(contexto, ADMIN, COORDINADOR)
    tabla_ddb = dynamo.tabla()
    pendientes = dynamo.consultar_todo(tabla_ddb, contexto.pk, "ALERTA#")
    avisos = dynamo.consultar_pagina(tabla_ddb, contexto.pk, "AVISO#", limite=RECIENTES, descendente=True)
    return respuesta({
        "pendientes": sorted((dynamo.vista(a) for a in pendientes), key=lambda a: a["inicio"]),
        "recientes": [dynamo.vista(a) for a in avisos["items"]],
    })
