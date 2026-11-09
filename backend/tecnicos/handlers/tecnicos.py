import os
import uuid

from botocore.exceptions import ClientError

from trazora_common import dynamo, idempotencia, logs
from trazora_common.auth import ADMIN, COORDINADOR, TECNICO, obtener_contexto, requiere_rol
from trazora_common.http import (
    api_handler, cuerpo_json, entrada_invalida, no_encontrado, parametro_query, parametro_ruta, prohibido, respuesta, texto,
)

from dominio.jornadas import sk_tecnico, validar_especialidades

GESTION = (ADMIN, COORDINADOR)


@api_handler
def crear(event, context):
    contexto = obtener_contexto(event)
    requiere_rol(contexto, *GESTION)
    datos = cuerpo_json(event)
    nombre = texto(datos, "nombre", 200)
    especialidades = validar_especialidades(datos.get("especialidades"))

    def construir():
        tecnico_id = f"TEC-{uuid.uuid4()}"
        item = {
            "PK": contexto.pk, "SK": sk_tecnico(tecnico_id), "entity_type": "TECNICO",
            "tenant_id": contexto.tenant_id, "tecnico_id": tecnico_id, "nombre": nombre,
            "especialidades": especialidades, "activo": True, "creado_en": dynamo.ahora_iso(),
        }
        return [{"Put": {"TableName": os.environ["TABLE_NAME"], "Item": item}}], dynamo.vista(item)

    resultado = idempotencia.crear(event, contexto.pk, datos, construir)
    logs.info("tecnico_creado", tenant_id=contexto.tenant_id, tecnico_id=resultado["tecnico_id"])
    return respuesta(resultado, 201)


@api_handler
def listar(event, context):
    contexto = obtener_contexto(event)
    requiere_rol(contexto, *GESTION)
    pagina = dynamo.consultar_pagina(
        dynamo.tabla(), contexto.pk, "TECNICO#",
        limite=parametro_query(event, "limit"), cursor=parametro_query(event, "cursor"),
    )
    return respuesta({"items": [dynamo.vista(i) for i in pagina["items"]], "next_cursor": pagina["next_cursor"]})


@api_handler
def detalle(event, context):
    contexto = obtener_contexto(event)
    tecnico_id = parametro_ruta(event, "tecnico_id")
    if contexto.rol == TECNICO and contexto.tecnico_id != tecnico_id:
        raise prohibido()
    item = dynamo.tabla().get_item(Key={"PK": contexto.pk, "SK": sk_tecnico(tecnico_id)}).get("Item")
    if not item:
        raise no_encontrado("Técnico")
    return respuesta(dynamo.vista(item))


@api_handler
def actualizar(event, context):
    contexto = obtener_contexto(event)
    requiere_rol(contexto, *GESTION)
    tecnico_id = parametro_ruta(event, "tecnico_id")
    datos = cuerpo_json(event)

    cambios = {}
    if "nombre" in datos:
        cambios["nombre"] = texto(datos, "nombre", 200)
    if "especialidades" in datos:
        cambios["especialidades"] = validar_especialidades(datos["especialidades"])
    if "activo" in datos:
        if not isinstance(datos["activo"], bool):
            raise entrada_invalida("El campo activo no es válido", campo="activo")
        cambios["activo"] = datos["activo"]
    if not cambios:
        raise entrada_invalida("No hay campos para actualizar")

    try:
        resultado = dynamo.tabla().update_item(
            Key={"PK": contexto.pk, "SK": sk_tecnico(tecnico_id)},
            UpdateExpression="SET " + ", ".join(f"#{c} = :{c}" for c in cambios),
            ConditionExpression="attribute_exists(PK)",
            ExpressionAttributeNames={f"#{c}": c for c in cambios},
            ExpressionAttributeValues={f":{c}": v for c, v in cambios.items()},
            ReturnValues="ALL_NEW",
        )
    except ClientError as error:
        if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise no_encontrado("Técnico")
        raise
    return respuesta(dynamo.vista(resultado["Attributes"]))
