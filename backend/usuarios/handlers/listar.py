from boto3.dynamodb.conditions import Attr, Key

from trazora_common import dynamo
from trazora_common.auth import ADMIN, obtener_contexto, requiere_rol
from trazora_common.http import api_handler, entrada_invalida, parametro_query, respuesta

from dominio.usuarios import ESTADOS, ROLES, texto_busqueda, vista_publica

# Con filtros se leen varias páginas de DynamoDB para llenar una de la API: 30 de 1 000 cubren los
# 10 000 perfiles de una empresa en una petición, sin dejar al administrador ante una página vacía.
PAGINAS_MAXIMAS = 30
LECTURA_FILTRADA = 1000


@api_handler
def lambda_handler(event, context):
    """Búsqueda por nombre o correo y filtros por rol y estado. Los filtros se aplican al leer
    la partición de la empresa: con 10 000 perfiles bastan unas pocas páginas de DynamoDB."""
    contexto = obtener_contexto(event)
    requiere_rol(contexto, ADMIN)
    limite = dynamo.limite_valido(parametro_query(event, "limit"))
    q = (parametro_query(event, "q") or "").strip()
    rol, estado = parametro_query(event, "rol"), parametro_query(event, "estado")
    if rol and rol not in ROLES:
        raise entrada_invalida("Rol no válido")
    if estado and estado not in ESTADOS:
        raise entrada_invalida("Estado no válido")

    filtro = None
    for condicion in (
        Attr("busqueda").contains(texto_busqueda(q, "").strip()) if q else None,
        Attr("rol").eq(rol) if rol else None,
        Attr("estado").eq(estado) if estado else None,
    ):
        if condicion is not None:
            filtro = condicion if filtro is None else filtro & condicion

    tabla_ddb = dynamo.tabla()
    inicio = dynamo.decodificar_cursor(parametro_query(event, "cursor"), contexto.pk)
    items = []
    for _ in range(PAGINAS_MAXIMAS):
        parametros = {
            "KeyConditionExpression": Key("PK").eq(contexto.pk) & Key("SK").begins_with("USUARIO#"),
            "Limit": limite if filtro is None else LECTURA_FILTRADA,
        }
        if filtro is not None:
            parametros["FilterExpression"] = filtro
        if inicio:
            parametros["ExclusiveStartKey"] = inicio
        pagina = tabla_ddb.query(**parametros)
        items += pagina.get("Items", [])
        inicio = pagina.get("LastEvaluatedKey")
        if len(items) >= limite or not inicio:
            break
    if len(items) > limite:
        items = items[:limite]
        inicio = {"PK": items[-1]["PK"], "SK": items[-1]["SK"]}
    return respuesta({"items": [vista_publica(i) for i in items], "next_cursor": dynamo.codificar_cursor(inicio)})
