from trazora_common import dynamo, eventos, interno, logs
from trazora_common.auth import ADMIN, COORDINADOR, TECNICO, obtener_contexto, requiere_rol
from trazora_common.http import (
    api_handler, cuerpo_json, entrada_invalida, no_encontrado, parametro_query, parametro_ruta, prohibido, respuesta, texto,
)

from dominio.jornadas import (
    ESPECIALIDADES, sk_ausencia, sk_jornada, sk_tecnico, validar_fecha, validar_intervalos, validar_rango,
)

GESTION = (ADMIN, COORDINADOR)
ZONA = "America/Lima"


def _exigir_tecnico(tabla_ddb, contexto, tecnico_id):
    if not tabla_ddb.get_item(Key={"PK": contexto.pk, "SK": sk_tecnico(tecnico_id)}).get("Item"):
        raise no_encontrado("Técnico")


@api_handler
def definir_jornada(event, context):
    contexto = obtener_contexto(event)
    requiere_rol(contexto, *GESTION)
    tecnico_id = parametro_ruta(event, "tecnico_id")
    fecha = validar_fecha(parametro_ruta(event, "fecha"))
    intervalos = validar_intervalos(cuerpo_json(event).get("intervalos"))
    tabla_ddb = dynamo.tabla()
    _exigir_tecnico(tabla_ddb, contexto, tecnico_id)
    item = {
        "PK": contexto.pk, "SK": sk_jornada(tecnico_id, fecha), "entity_type": "JORNADA",
        "tenant_id": contexto.tenant_id, "tecnico_id": tecnico_id, "fecha": fecha,
        "zona_horaria": ZONA, "intervalos": intervalos,
    }
    tabla_ddb.put_item(Item=item)
    return respuesta(dynamo.vista(item))


@api_handler
def registrar_ausencia(event, context):
    """También la registra el propio técnico (por ejemplo, si enferma). Agenda reasigna sus visitas
    de ese día al recibir TecnicoAusente; registrarla dos veces no vuelve a publicar."""
    contexto = obtener_contexto(event)
    tecnico_id = parametro_ruta(event, "tecnico_id")
    if contexto.rol == TECNICO:
        if contexto.tecnico_id != tecnico_id:
            raise prohibido()
    else:
        requiere_rol(contexto, *GESTION)
    fecha = validar_fecha(parametro_ruta(event, "fecha"))
    motivo = texto(cuerpo_json(event), "motivo", 300)
    tabla_ddb = dynamo.tabla()
    _exigir_tecnico(tabla_ddb, contexto, tecnico_id)
    clave = {"PK": contexto.pk, "SK": sk_ausencia(tecnico_id, fecha)}
    previa = tabla_ddb.get_item(Key=clave, ConsistentRead=True).get("Item")
    if previa:
        return respuesta(dynamo.vista(previa))
    item = {
        **clave, "entity_type": "AUSENCIA", "tenant_id": contexto.tenant_id, "tecnico_id": tecnico_id,
        "fecha": fecha, "motivo": motivo, "registrada_por": contexto.rol, "registrada_en": dynamo.ahora_iso(),
    }
    evento = eventos.crear_evento(
        "TecnicoAusente", contexto.tenant_id, "TECNICO", tecnico_id, 1,
        {"tecnico_id": tecnico_id, "fecha": fecha, "motivo": motivo},
        correlation_id=f"{tecnico_id}#{fecha}",
    )
    try:
        dynamo.transaccion([
            {"Put": {"TableName": tabla_ddb.name, "Item": item, "ConditionExpression": "attribute_not_exists(PK)"}},
            eventos.operacion_outbox(evento),
        ])
    except dynamo.TransaccionCancelada:
        return respuesta(dynamo.vista(tabla_ddb.get_item(Key=clave, ConsistentRead=True)["Item"]))
    eventos.publicar_y_borrar(evento)
    logs.info("tecnico_ausente", tenant_id=contexto.tenant_id, tecnico_id=tecnico_id, fecha=fecha)
    return respuesta(dynamo.vista(item), 201)


@api_handler
def consultar(event, context):
    contexto = obtener_contexto(event)
    tecnico_id = parametro_ruta(event, "tecnico_id")
    if contexto.rol == TECNICO and contexto.tecnico_id != tecnico_id:
        raise prohibido()
    desde, hasta = validar_rango(parametro_query(event, "desde"), parametro_query(event, "hasta"))
    tabla_ddb = dynamo.tabla()
    _exigir_tecnico(tabla_ddb, contexto, tecnico_id)
    jornadas = dynamo.consultar_rango(tabla_ddb, contexto.pk, sk_jornada(tecnico_id, desde), sk_jornada(tecnico_id, hasta))
    ausencias = dynamo.consultar_rango(tabla_ddb, contexto.pk, sk_ausencia(tecnico_id, desde), sk_ausencia(tecnico_id, hasta))
    return respuesta({
        "jornadas": [dynamo.vista(i) for i in jornadas],
        "ausencias": [dynamo.vista(i) for i in ausencias],
    })


@api_handler
def disponibles(event, context):
    """Candidatos de una sola vez (H2), para que Agenda no haga una llamada por técnico.
    Con get_item, visto en clase: como máximo dos lecturas por técnico."""
    contexto = obtener_contexto(event)
    requiere_rol(contexto, *GESTION)
    fecha = validar_fecha(parametro_query(event, "fecha"))
    especialidad = parametro_query(event, "especialidad")
    if especialidad is not None and especialidad not in ESPECIALIDADES:
        raise entrada_invalida("Especialidad no válida", permitidas=sorted(ESPECIALIDADES))

    return respuesta({"fecha": fecha, "items": candidatos_del_dia(dynamo.tabla(), contexto.pk, fecha, especialidad)})


def disponibles_interno(event, context):
    """Sin ruta: la invoca Agenda con lambda.invoke al reasignar visitas por un evento, cuando no
    hay token de usuario que reenviar (como bloquearOrden, H1)."""
    fecha = validar_fecha(event["fecha"])
    items = candidatos_del_dia(dynamo.tabla(), f"TENANT#{event['tenant_id']}", fecha, event.get("especialidad"))
    return interno.serializable({"fecha": fecha, "items": items})


def candidatos_del_dia(tabla_ddb, pk, fecha, especialidad=None):
    candidatos = []
    for tecnico in dynamo.consultar_todo(tabla_ddb, pk, "TECNICO#"):
        if not tecnico.get("activo") or (especialidad and especialidad not in tecnico.get("especialidades", [])):
            continue
        tecnico_id = tecnico["tecnico_id"]
        jornada = tabla_ddb.get_item(Key={"PK": pk, "SK": sk_jornada(tecnico_id, fecha)}).get("Item")
        if not jornada:
            continue
        if tabla_ddb.get_item(Key={"PK": pk, "SK": sk_ausencia(tecnico_id, fecha)}, ConsistentRead=True).get("Item"):
            continue
        candidatos.append({**dynamo.vista(tecnico), "intervalos": jornada["intervalos"]})
    return candidatos
