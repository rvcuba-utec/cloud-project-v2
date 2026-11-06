from trazora_common import dynamo
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
    contexto = obtener_contexto(event)
    requiere_rol(contexto, *GESTION)
    tecnico_id = parametro_ruta(event, "tecnico_id")
    fecha = validar_fecha(parametro_ruta(event, "fecha"))
    motivo = texto(cuerpo_json(event), "motivo", 300)
    tabla_ddb = dynamo.tabla()
    _exigir_tecnico(tabla_ddb, contexto, tecnico_id)
    item = {
        "PK": contexto.pk, "SK": sk_ausencia(tecnico_id, fecha), "entity_type": "AUSENCIA",
        "tenant_id": contexto.tenant_id, "tecnico_id": tecnico_id, "fecha": fecha, "motivo": motivo,
    }
    tabla_ddb.put_item(Item=item)
    return respuesta(dynamo.vista(item))


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

    tabla_ddb = dynamo.tabla()
    candidatos = []
    for tecnico in dynamo.consultar_todo(tabla_ddb, contexto.pk, "TECNICO#"):
        if not tecnico.get("activo") or (especialidad and especialidad not in tecnico.get("especialidades", [])):
            continue
        tecnico_id = tecnico["tecnico_id"]
        jornada = tabla_ddb.get_item(Key={"PK": contexto.pk, "SK": sk_jornada(tecnico_id, fecha)}).get("Item")
        if not jornada:
            continue
        if tabla_ddb.get_item(Key={"PK": contexto.pk, "SK": sk_ausencia(tecnico_id, fecha)}).get("Item"):
            continue
        candidatos.append({**dynamo.vista(tecnico), "intervalos": jornada["intervalos"]})
    return respuesta({"fecha": fecha, "items": candidatos})
