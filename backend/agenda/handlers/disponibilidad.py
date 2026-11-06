import os

from trazora_common import dynamo, interno, logs
from trazora_common.auth import ADMIN, COORDINADOR, obtener_contexto, requiere_rol, token_de_peticion
from trazora_common.http import ApiError, api_handler, entrada_invalida, parametro_query, respuesta

from dominio.agenda import horarios_libres, ordenar_candidatos, prefijo_bloques_dia, validar_fecha

TIMEOUT_ANALITICA = 5  # Margen para el arranque en frío del autorizador y de la Lambda (H18).


def _metricas(event, fecha):
    """Analítica es opcional: si falla, se sigue programando con el orden predeterminado."""
    base = os.environ.get("ANALITICA_URL")
    if not base:
        return {}
    try:
        datos = interno.llamar(base, f"/analitica/tecnicos?fecha={fecha}", token_de_peticion(event), timeout=TIMEOUT_ANALITICA)
        return {m["tecnico_id"]: m for m in datos.get("items", [])}
    except ApiError as error:
        logs.error("analitica_no_disponible", codigo=error.codigo)
        return {}


@api_handler
def consultar(event, context):
    contexto = obtener_contexto(event)
    requiere_rol(contexto, ADMIN, COORDINADOR)
    fecha = validar_fecha(parametro_query(event, "fecha"))
    especialidad = parametro_query(event, "especialidad")
    try:
        duracion = int(parametro_query(event, "duracion_min", "60"))
    except ValueError:
        raise entrada_invalida("duracion_min debe ser un número")

    ruta = f"/tecnicos/disponibles?fecha={fecha}" + (f"&especialidad={especialidad}" if especialidad else "")
    candidatos = interno.llamar(os.environ["TECNICOS_URL"], ruta, token_de_peticion(event))["items"]

    ocupados = {}
    for bloque in dynamo.consultar_todo(dynamo.tabla(), contexto.pk, prefijo_bloques_dia(fecha)):
        ocupados.setdefault(bloque["tecnico_id"], set()).add(bloque["hora"])

    opciones = []
    for candidato in candidatos:
        libres = horarios_libres(candidato["intervalos"], ocupados.get(candidato["tecnico_id"], set()), duracion)
        if libres:
            opciones.append({
                "tecnico_id": candidato["tecnico_id"], "nombre": candidato["nombre"],
                "especialidades": candidato["especialidades"], "horarios": libres,
            })

    metricas = _metricas(event, fecha) if parametro_query(event, "sugerir") == "true" else {}
    return respuesta({"fecha": fecha, "duracion_min": duracion, "items": ordenar_candidatos(opciones, metricas)})
