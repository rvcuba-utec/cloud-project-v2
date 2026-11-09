import os
import uuid

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from trazora_common import dynamo, eventos, interno, logs
from trazora_common.auth import ADMIN, COORDINADOR, TECNICO, obtener_contexto, requiere_rol, token_de_peticion
from trazora_common.http import (
    api_handler, conflicto, cuerpo_json, entrada_invalida, no_encontrado, parametro_query, parametro_ruta, respuesta,
)

from dominio import almacen
from dominio.partes import (
    BORRADOR, CONFIRMADA, FINALIZADO, PENDIENTE, cambios_de_borrador, exigir_completo, indice_de_orden, sk_marca, sk_parte,
)

EN_ATENCION = "EN_ATENCION"
ESCRIBEN = (TECNICO, ADMIN)


def _nombre_tabla():
    return os.environ["TABLE_NAME"]


def obtener_parte(tabla_ddb, contexto, parte_id):
    parte = tabla_ddb.get_item(Key={"PK": contexto.pk, "SK": sk_parte(parte_id)}, ConsistentRead=True).get("Item")
    if not parte or (contexto.rol == TECNICO and parte["tecnico_id"] != contexto.tecnico_id):
        raise no_encontrado("Parte")  # Un técnico no descubre partes ajenos.
    return parte


def _parte_de_visita(tabla_ddb, contexto, visita_id):
    marca = tabla_ddb.get_item(Key={"PK": contexto.pk, "SK": sk_marca(visita_id)}, ConsistentRead=True).get("Item")
    return obtener_parte(tabla_ddb, contexto, marca["parte_id"]) if marca else None


def _evidencias(tabla_ddb, contexto, parte):
    """Con la URL de lectura solo las confirmadas: la clave del objeto no sale de la API."""
    resultado, inicio = [], None
    while True:
        parametros = {
            "IndexName": "GSI1",
            "KeyConditionExpression": Key("GSI1PK").eq(f"TENANT#{contexto.tenant_id}#PARTE#{parte['parte_id']}"),
        }
        if inicio:
            parametros["ExclusiveStartKey"] = inicio
        pagina = tabla_ddb.query(**parametros)
        for item in pagina.get("Items", []):
            if parte["estado"] == FINALIZADO and item["estado"] == PENDIENTE:
                continue  # Subidas abandonadas: ya no se esperan.
            salida = {k: item[k] for k in ("evidencia_id", "estado", "content_type", "nombre") if k in item}
            if item["estado"] == CONFIRMADA:
                salida["url"] = almacen.firmar_lectura(item["object_key"])
            resultado.append(salida)
        inicio = pagina.get("LastEvaluatedKey")
        if not inicio:
            return resultado


def _con_evidencias(tabla_ddb, contexto, parte):
    return {**dynamo.vista(parte), "evidencias": _evidencias(tabla_ddb, contexto, parte)}


@api_handler
def crear(event, context):
    """Un parte por visita. Volver a pedirlo devuelve el borrador existente, sin duplicar."""
    contexto = obtener_contexto(event)
    requiere_rol(contexto, *ESCRIBEN)
    visita_id = parametro_ruta(event, "visita_id")
    tabla_ddb = dynamo.tabla()

    def existente():
        parte = _parte_de_visita(tabla_ddb, contexto, visita_id)
        if parte and parte["estado"] == FINALIZADO:
            raise conflicto("PARTE_YA_FINALIZADO", "Esta visita ya tiene un parte finalizado", parte_id=parte["parte_id"])
        return parte

    previo = existente()
    if previo:
        return respuesta(_con_evidencias(tabla_ddb, contexto, previo))

    # Agenda responde 404 si la visita es de otro técnico o de otra empresa.
    visita = interno.llamar(os.environ["AGENDA_URL"], f"/visitas/{visita_id}", token_de_peticion(event))
    if visita["estado"] != EN_ATENCION:
        raise conflicto("VISITA_NO_EN_ATENCION", "La visita debe estar en atención")

    parte_id = f"PAR-{uuid.uuid4()}"
    parte = {
        "PK": contexto.pk, "SK": sk_parte(parte_id), "entity_type": "PARTE",
        "tenant_id": contexto.tenant_id, "parte_id": parte_id, "visita_id": visita_id,
        "orden_id": visita["orden_id"], "tecnico_id": visita["tecnico_id"],
        # Copias (H17): el detalle del parte no necesita consultar otros servicios.
        "tecnico_nombre": visita["tecnico_nombre"], "cliente_nombre": visita["cliente_nombre"],
        "direccion": visita["direccion"], "distrito": visita["distrito"],
        "fecha": visita["fecha"], "numero_visita_orden": visita["numero_visita_orden"],
        "estado": BORRADOR, "diagnostico": "", "tareas": [], "materiales": [], "resultado": "",
        "evidencias_solicitadas": 0, "version": 1, "creado_en": dynamo.ahora_iso(),
        **indice_de_orden(contexto.tenant_id, visita["orden_id"], parte_id),
    }
    try:
        dynamo.transaccion([
            {"Put": {"TableName": _nombre_tabla(), "Item": parte}},
            {"Put": {
                "TableName": _nombre_tabla(),
                "Item": {"PK": contexto.pk, "SK": sk_marca(visita_id), "entity_type": "MARCA_VISITA", "parte_id": parte_id},
                "ConditionExpression": "attribute_not_exists(PK)",
            }},
        ])
    except dynamo.TransaccionCancelada:
        # Dos pestañas a la vez: gana una y la otra recibe ese mismo parte.
        return respuesta(_con_evidencias(tabla_ddb, contexto, existente()))
    logs.info("parte_creado", tenant_id=contexto.tenant_id, correlation_id=visita["orden_id"], parte_id=parte_id)
    return respuesta({**dynamo.vista(parte), "evidencias": []}, 201)


@api_handler
def de_visita(event, context):
    contexto = obtener_contexto(event)
    tabla_ddb = dynamo.tabla()
    parte = _parte_de_visita(tabla_ddb, contexto, parametro_ruta(event, "visita_id"))
    if not parte:
        raise no_encontrado("Parte")
    return respuesta(_con_evidencias(tabla_ddb, contexto, parte))


@api_handler
def detalle(event, context):
    contexto = obtener_contexto(event)
    tabla_ddb = dynamo.tabla()
    parte = obtener_parte(tabla_ddb, contexto, parametro_ruta(event, "parte_id"))
    return respuesta(_con_evidencias(tabla_ddb, contexto, parte))


@api_handler
def listar(event, context):
    contexto = obtener_contexto(event)
    requiere_rol(contexto, ADMIN, COORDINADOR)
    orden_id = parametro_query(event, "orden_id")
    if not orden_id:
        raise entrada_invalida("Indica orden_id")
    pagina = dynamo.consultar_pagina(
        dynamo.tabla(), f"TENANT#{contexto.tenant_id}#ORDEN#{orden_id}", indice="GSI1",
        atributo_pk="GSI1PK", atributo_sk="GSI1SK",
        limite=parametro_query(event, "limit"), cursor=parametro_query(event, "cursor"),
    )
    return respuesta({"items": [dynamo.vista(i) for i in pagina["items"]], "next_cursor": pagina["next_cursor"]})


def _version(datos):
    version = datos.get("version")
    if not isinstance(version, int) or isinstance(version, bool):
        raise entrada_invalida("El campo version es obligatorio", campo="version")
    return version


@api_handler
def editar(event, context):
    contexto = obtener_contexto(event)
    requiere_rol(contexto, *ESCRIBEN)
    parte_id = parametro_ruta(event, "parte_id")
    datos = cuerpo_json(event)
    version = _version(datos)
    cambios = cambios_de_borrador(datos)
    tabla_ddb = dynamo.tabla()
    parte = obtener_parte(tabla_ddb, contexto, parte_id)
    if parte["estado"] != BORRADOR:
        raise conflicto("PARTE_YA_FINALIZADO", "Un parte finalizado no se puede editar")
    if not cambios:
        return respuesta(_con_evidencias(tabla_ddb, contexto, parte))
    try:
        actualizado = tabla_ddb.update_item(
            Key={"PK": contexto.pk, "SK": sk_parte(parte_id)},
            UpdateExpression="SET #v = :nueva, " + ", ".join(f"#c_{k} = :c_{k}" for k in cambios),
            ConditionExpression="estado = :borrador AND #v = :version",
            ExpressionAttributeNames={"#v": "version", **{f"#c_{k}": k for k in cambios}},
            ExpressionAttributeValues={
                ":nueva": version + 1, ":borrador": BORRADOR, ":version": version,
                **{f":c_{k}": v for k, v in cambios.items()},
            },
            ReturnValues="ALL_NEW",
        )["Attributes"]
    except ClientError as error:
        if error.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
        raise conflicto("VERSION_DESACTUALIZADA", "El parte cambió. Actualiza e intenta de nuevo.")
    return respuesta(_con_evidencias(tabla_ddb, contexto, actualizado))


@api_handler
def finalizar(event, context):
    contexto = obtener_contexto(event)
    requiere_rol(contexto, *ESCRIBEN)
    parte_id = parametro_ruta(event, "parte_id")
    datos = cuerpo_json(event)
    tabla_ddb = dynamo.tabla()
    parte = obtener_parte(tabla_ddb, contexto, parte_id)
    if parte["estado"] == FINALIZADO:  # Un reintento recibe lo mismo y no publica otro evento.
        return respuesta(_con_evidencias(tabla_ddb, contexto, parte))
    version = _version(datos)
    if int(parte["version"]) != version:
        raise conflicto("VERSION_DESACTUALIZADA", "El parte cambió. Actualiza e intenta de nuevo.", version=int(parte["version"]))
    exigir_completo(parte)

    ahora = dynamo.ahora_iso()
    nuevo = {**parte, "estado": FINALIZADO, "finalizado_en": ahora, "version": version + 1}
    evento = eventos.crear_evento(
        "ParteFinalizado", contexto.tenant_id, "PARTE", parte_id, version + 1,
        {
            "parte_id": parte_id, "visita_id": parte["visita_id"], "orden_id": parte["orden_id"],
            "tecnico_id": parte["tecnico_id"], "resultado": parte["resultado"], "finalizado_en": ahora,
        },
        correlation_id=parte["orden_id"],
    )
    try:
        dynamo.transaccion([
            {"Update": {
                "TableName": _nombre_tabla(),
                "Key": {"PK": contexto.pk, "SK": sk_parte(parte_id)},
                "UpdateExpression": "SET estado = :final, finalizado_en = :ahora, #v = :nueva",
                "ConditionExpression": "estado = :borrador AND #v = :version",
                "ExpressionAttributeNames": {"#v": "version"},
                "ExpressionAttributeValues": {
                    ":final": FINALIZADO, ":ahora": ahora, ":nueva": version + 1,
                    ":borrador": BORRADOR, ":version": version,
                },
            }},
            eventos.operacion_outbox(evento),
        ])
    except dynamo.TransaccionCancelada:
        actual = obtener_parte(tabla_ddb, contexto, parte_id)
        if actual["estado"] == FINALIZADO:  # Dos envíos a la vez: el evento lo publicó el otro.
            return respuesta(_con_evidencias(tabla_ddb, contexto, actual))
        raise conflicto("VERSION_DESACTUALIZADA", "El parte cambió. Actualiza e intenta de nuevo.")
    eventos.publicar_y_borrar(evento)
    logs.info("parte_finalizado", tenant_id=contexto.tenant_id, correlation_id=parte["orden_id"], parte_id=parte_id)
    return respuesta(_con_evidencias(tabla_ddb, contexto, nuevo))
