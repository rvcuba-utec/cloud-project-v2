import os
import uuid

from trazora_common import dynamo, idempotencia
from trazora_common.auth import ADMIN, COORDINADOR, obtener_contexto, requiere_rol
from trazora_common.http import (
    api_handler, conflicto, cuerpo_json, no_encontrado, parametro_query, parametro_ruta, respuesta, texto,
)

from dominio.clientes import sk_cliente, sk_ubicacion

GESTION = (ADMIN, COORDINADOR)


def _cliente(tabla_ddb, contexto, cliente_id):
    item = tabla_ddb.get_item(Key={"PK": contexto.pk, "SK": sk_cliente(cliente_id)}).get("Item")
    if not item:
        raise no_encontrado("Cliente")
    return item


@api_handler
def crear(event, context):
    contexto = obtener_contexto(event)
    requiere_rol(contexto, *GESTION)
    cliente_id = parametro_ruta(event, "cliente_id")
    datos = cuerpo_json(event)
    nombre = texto(datos, "nombre", 200)
    direccion = texto(datos, "direccion", 300)
    distrito = texto(datos, "distrito", 100)
    referencia = texto(datos, "referencia", 300, obligatorio=False)

    def construir():
        if not _cliente(dynamo.tabla(), contexto, cliente_id).get("activo"):
            raise conflicto("CLIENTE_INACTIVO", "El cliente está desactivado")
        ubicacion_id = f"LOC-{uuid.uuid4()}"
        item = {
            "PK": contexto.pk, "SK": sk_ubicacion(cliente_id, ubicacion_id), "entity_type": "UBICACION",
            "tenant_id": contexto.tenant_id, "cliente_id": cliente_id, "ubicacion_id": ubicacion_id,
            "nombre": nombre, "direccion": direccion, "distrito": distrito,
        }
        if referencia:
            item["referencia"] = referencia
        return [{"Put": {"TableName": os.environ["TABLE_NAME"], "Item": item}}], dynamo.vista(item)

    return respuesta(idempotencia.crear(event, contexto.pk, {**datos, "cliente_id": cliente_id}, construir), 201)


@api_handler
def listar(event, context):
    contexto = obtener_contexto(event)
    requiere_rol(contexto, *GESTION)
    cliente_id = parametro_ruta(event, "cliente_id")
    tabla_ddb = dynamo.tabla()
    _cliente(tabla_ddb, contexto, cliente_id)
    pagina = dynamo.consultar_pagina(
        tabla_ddb, contexto.pk, f"UBICACION#{cliente_id}#",
        limite=parametro_query(event, "limit"), cursor=parametro_query(event, "cursor"),
    )
    return respuesta({"items": [dynamo.vista(i) for i in pagina["items"]], "next_cursor": pagina["next_cursor"]})


@api_handler
def detalle(event, context):
    """También la usa Órdenes para validar la referencia y copiar el nombre del cliente (H17)."""
    contexto = obtener_contexto(event)
    requiere_rol(contexto, *GESTION)
    cliente_id = parametro_ruta(event, "cliente_id")
    tabla_ddb = dynamo.tabla()
    cliente = _cliente(tabla_ddb, contexto, cliente_id)
    item = tabla_ddb.get_item(
        Key={"PK": contexto.pk, "SK": sk_ubicacion(cliente_id, parametro_ruta(event, "ubicacion_id"))}
    ).get("Item")
    if not item:
        raise no_encontrado("Ubicación")
    return respuesta({**dynamo.vista(item), "cliente_nombre": cliente["nombre"], "cliente_activo": cliente.get("activo", False)})
