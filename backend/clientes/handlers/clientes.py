import os
import uuid

from botocore.exceptions import ClientError

from trazora_common import dynamo, idempotencia, logs
from trazora_common.auth import ADMIN, COORDINADOR, obtener_contexto, requiere_rol
from trazora_common.http import (
    api_handler, cuerpo_json, entrada_invalida, no_encontrado, parametro_query, parametro_ruta, respuesta, texto,
)

from dominio.clientes import normalizar_nombre, orden_nombre, particion_nombres, sk_cliente

GESTION = (ADMIN, COORDINADOR)  # El técnico recibe sus datos dentro de cada visita.


@api_handler
def crear(event, context):
    contexto = obtener_contexto(event)
    requiere_rol(contexto, *GESTION)
    datos = cuerpo_json(event)
    nombre = texto(datos, "nombre", 200)
    telefono = texto(datos, "telefono", 50, obligatorio=False)
    correo = texto(datos, "correo", 200, obligatorio=False)

    def construir():
        cliente_id = f"CLI-{uuid.uuid4()}"
        item = {
            "PK": contexto.pk, "SK": sk_cliente(cliente_id), "entity_type": "CLIENTE",
            "tenant_id": contexto.tenant_id, "cliente_id": cliente_id, "nombre": nombre,
            "activo": True, "creado_en": dynamo.ahora_iso(),
            "GSI1PK": particion_nombres(contexto.tenant_id), "GSI1SK": orden_nombre(nombre, cliente_id),
        }
        if telefono:
            item["telefono"] = telefono
        if correo:
            item["correo"] = correo
        return [{"Put": {"TableName": os.environ["TABLE_NAME"], "Item": item}}], dynamo.vista(item)

    resultado = idempotencia.crear(event, contexto.pk, datos, construir)
    logs.info("cliente_creado", tenant_id=contexto.tenant_id, cliente_id=resultado["cliente_id"])
    return respuesta(resultado, 201)


@api_handler
def listar(event, context):
    contexto = obtener_contexto(event)
    requiere_rol(contexto, *GESTION)
    busqueda = normalizar_nombre(parametro_query(event, "q", "") or "")
    pagina = dynamo.consultar_pagina(
        dynamo.tabla(), particion_nombres(contexto.tenant_id), busqueda or None,
        limite=parametro_query(event, "limit"), cursor=parametro_query(event, "cursor"),
        indice="GSI1", atributo_pk="GSI1PK", atributo_sk="GSI1SK",
    )
    return respuesta({"items": [dynamo.vista(i) for i in pagina["items"]], "next_cursor": pagina["next_cursor"]})


@api_handler
def detalle(event, context):
    contexto = obtener_contexto(event)
    requiere_rol(contexto, *GESTION)
    item = dynamo.tabla().get_item(
        Key={"PK": contexto.pk, "SK": sk_cliente(parametro_ruta(event, "cliente_id"))}
    ).get("Item")
    if not item:
        raise no_encontrado("Cliente")
    return respuesta(dynamo.vista(item))


@api_handler
def actualizar(event, context):
    contexto = obtener_contexto(event)
    requiere_rol(contexto, *GESTION)
    cliente_id = parametro_ruta(event, "cliente_id")
    datos = cuerpo_json(event)

    cambios = {}
    if "nombre" in datos:
        cambios["nombre"] = texto(datos, "nombre", 200)
        cambios["GSI1SK"] = orden_nombre(cambios["nombre"], cliente_id)
    for campo, maximo in (("telefono", 50), ("correo", 200)):
        if campo in datos:
            cambios[campo] = texto(datos, campo, maximo, obligatorio=False) or ""
    if "activo" in datos:
        if not isinstance(datos["activo"], bool):
            raise entrada_invalida("El campo activo no es válido", campo="activo")
        cambios["activo"] = datos["activo"]  # Se desactiva, no se borra: conserva el historial.
    if not cambios:
        raise entrada_invalida("No hay campos para actualizar")

    try:
        resultado = dynamo.tabla().update_item(
            Key={"PK": contexto.pk, "SK": sk_cliente(cliente_id)},
            UpdateExpression="SET " + ", ".join(f"#{c} = :{c}" for c in cambios),
            ConditionExpression="attribute_exists(PK)",
            ExpressionAttributeNames={f"#{c}": c for c in cambios},
            ExpressionAttributeValues={f":{c}": v for c, v in cambios.items()},
            ReturnValues="ALL_NEW",
        )
    except ClientError as error:
        if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise no_encontrado("Cliente")
        raise
    return respuesta(dynamo.vista(resultado["Attributes"]))
