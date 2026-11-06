from trazora_common import dynamo
from trazora_common.auth import ADMIN, obtener_contexto, requiere_rol
from trazora_common.http import api_handler, parametro_query, respuesta

from dominio.usuarios import vista_publica


@api_handler
def lambda_handler(event, context):
    contexto = obtener_contexto(event)
    requiere_rol(contexto, ADMIN)
    pagina = dynamo.consultar_pagina(
        dynamo.tabla(),
        contexto.pk,
        "USUARIO#",
        limite=parametro_query(event, "limit"),
        cursor=parametro_query(event, "cursor"),
    )
    return respuesta({
        "items": [vista_publica(i) for i in pagina["items"]],
        "next_cursor": pagina["next_cursor"],
    })
