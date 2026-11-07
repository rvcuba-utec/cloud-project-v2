import os
import uuid

from trazora_common import dynamo, logs
from trazora_common.auth import TECNICO, ADMIN, obtener_contexto, requiere_rol
from trazora_common.http import (
    api_handler, conflicto, cuerpo_json, no_encontrado, opcion, parametro_ruta, respuesta, texto,
)

from dominio import almacen
from dominio.partes import (
    BORRADOR, MAX_BYTES, MAX_SOLICITUDES, PENDIENTE, RECHAZADA, TIPOS_ARCHIVO, VALIDEZ_FIRMA_SEGUNDOS,
    clave_objeto, indice_de_parte, sk_evidencia, sk_parte,
)
from handlers.partes import obtener_parte

ESCRIBEN = (TECNICO, ADMIN)


@api_handler
def solicitar(event, context):
    contexto = obtener_contexto(event)
    requiere_rol(contexto, *ESCRIBEN)
    parte_id = parametro_ruta(event, "parte_id")
    datos = cuerpo_json(event)
    tipo = opcion(datos, "content_type", set(TIPOS_ARCHIVO))
    nombre = texto(datos, "nombre", 200, obligatorio=False)
    parte = obtener_parte(dynamo.tabla(), contexto, parte_id)
    if parte["estado"] != BORRADOR:
        raise conflicto("PARTE_YA_FINALIZADO", "Un parte finalizado no admite más archivos")

    evidencia_id = f"EVI-{uuid.uuid4()}"
    clave = clave_objeto(contexto.tenant_id, parte["orden_id"], parte["visita_id"], evidencia_id, TIPOS_ARCHIVO[tipo])
    evidencia = {
        "PK": contexto.pk, "SK": sk_evidencia(evidencia_id), "entity_type": "EVIDENCIA",
        "tenant_id": contexto.tenant_id, "evidencia_id": evidencia_id, "parte_id": parte_id,
        "tecnico_id": parte["tecnico_id"], "object_key": clave, "content_type": tipo,
        "estado": PENDIENTE, "creada_en": dynamo.ahora_iso(),
        **indice_de_parte(contexto.tenant_id, parte_id, evidencia_id),
    }
    if nombre:
        evidencia["nombre"] = nombre
    try:
        # En la misma transacción: un parte que se finaliza ahora mismo no recibe más archivos.
        dynamo.transaccion([
            {"Update": {
                "TableName": os.environ["TABLE_NAME"],
                "Key": {"PK": contexto.pk, "SK": sk_parte(parte_id)},
                "UpdateExpression": "ADD evidencias_solicitadas :uno",
                "ConditionExpression": "estado = :borrador AND evidencias_solicitadas < :maximo",
                "ExpressionAttributeValues": {":uno": 1, ":borrador": BORRADOR, ":maximo": MAX_SOLICITUDES},
            }},
            {"Put": {"TableName": os.environ["TABLE_NAME"], "Item": evidencia}},
        ])
    except dynamo.TransaccionCancelada:
        raise conflicto("EVIDENCIA_NO_ADMITIDA", "El parte ya no admite más archivos")
    firma = almacen.firmar_subida(clave, tipo)
    return respuesta({
        "evidencia_id": evidencia_id, "url": firma["url"], "fields": firma["fields"],
        "max_bytes": MAX_BYTES, "expira_en_segundos": VALIDEZ_FIRMA_SEGUNDOS,
    }, 201)


@api_handler
def confirmar(event, context):
    """Respaldo por si la notificación de S3 se demora. Repetirlo devuelve el mismo estado."""
    contexto = obtener_contexto(event)
    requiere_rol(contexto, *ESCRIBEN)
    evidencia_id = parametro_ruta(event, "evidencia_id")
    tabla_ddb = dynamo.tabla()
    evidencia = tabla_ddb.get_item(Key={"PK": contexto.pk, "SK": sk_evidencia(evidencia_id)}, ConsistentRead=True).get("Item")
    if not evidencia or (contexto.rol == TECNICO and evidencia["tecnico_id"] != contexto.tecnico_id):
        raise no_encontrado("Evidencia")
    estado = almacen.revisar_y_marcar(tabla_ddb, contexto.pk, evidencia)
    if estado == PENDIENTE:
        raise conflicto("ARCHIVO_NO_ENCONTRADO", "El archivo todavía no llegó. Súbelo de nuevo.")
    if estado == RECHAZADA:
        logs.info("evidencia_rechazada", tenant_id=contexto.tenant_id, evidencia_id=evidencia_id)
    return respuesta({"evidencia_id": evidencia_id, "estado": estado})
