"""Genera docs/openapi/<servicio>.json (OpenAPI 3.0) y falla si una ruta de un serverless.yml no está documentada.

Las rutas salen de los serverless.yml; el detalle de cada una (roles, cuerpo, parámetros, respuestas) está en
este archivo, escrito a partir de los handlers. Si agregas una ruta, el script se detiene hasta que la describas.
"""
import json
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "docs" / "openapi"
SERVICIOS = {
    "usuarios": "MS0 Usuarios", "clientes": "MS1 Clientes", "tecnicos": "MS2 Técnicos", "ordenes": "MS3 Órdenes",
    "agenda": "MS4 Agenda", "partes": "MS5 Partes", "analitica": "MS6 Analítica",
}
GESTION = "ADMIN, COORDINADOR"
TODOS = "ADMIN, COORDINADOR, TECNICO"
TEXTO = {"type": "string"}


def ref(nombre):
    return {"$ref": f"#/components/schemas/{nombre}"}


def objeto(propiedades, obligatorios=(), ejemplo=None):
    esquema = {"type": "object", "properties": propiedades}
    if obligatorios:
        esquema["required"] = list(obligatorios)
    if ejemplo:
        esquema["example"] = ejemplo
    return esquema


def texto(descripcion=None, **extra):
    return {"type": "string", **({"description": descripcion} if descripcion else {}), **extra}


def lista_de(nombre):
    return objeto({"items": {"type": "array", "items": ref(nombre)}, "next_cursor": {**TEXTO, "nullable": True, "description": "Cursor de la página siguiente; null si no hay más."}})


ESPECIALIDADES = ["INSTALACION", "MANTENIMIENTO", "REPARACION"]
ESTADOS_ORDEN = ["ABIERTA", "PROGRAMADA", "EN_ATENCION", "REQUIERE_REVISITA", "PENDIENTE_DE_CIERRE", "CIERRE_EN_PROCESO", "CERRADA", "CANCELADA"]
INSTANTE = texto("Instante UTC, en múltiplos de 30 minutos.", format="date-time", example="2026-11-20T15:00:00Z")
FECHA = texto("Fecha AAAA-MM-DD (día local de Lima).", format="date", example="2026-11-20")

SCHEMAS = {
    "Error": objeto({"error": objeto({
        "codigo": texto(example="ENTRADA_INVALIDA"), "mensaje": TEXTO, "detalle": {"type": "object", "additionalProperties": True},
    })}),
    "Usuario": objeto({
        "usuario_id": TEXTO, "email": texto(format="email"), "nombre": TEXTO,
        "rol": {"type": "string", "enum": ["ADMIN", "COORDINADOR", "TECNICO"]},
        "estado": {"type": "string", "enum": ["ACTIVO", "INACTIVO"]},
        "tecnico_id": {**TEXTO, "nullable": True, "description": "Obligatorio cuando el rol es TECNICO."},
    }),
    "Cliente": objeto({
        "cliente_id": texto(example="CLI-…"), "nombre": TEXTO, "telefono": TEXTO, "correo": TEXTO,
        "activo": {"type": "boolean"}, "creado_en": texto(format="date-time"),
    }),
    "Ubicacion": objeto({
        "ubicacion_id": texto(example="LOC-…"), "cliente_id": TEXTO, "nombre": TEXTO, "direccion": TEXTO, "distrito": TEXTO,
        "referencia": TEXTO, "lat": {"type": "number"}, "lng": {"type": "number"},
    }),
    "Tecnico": objeto({
        "tecnico_id": TEXTO, "nombre": TEXTO,
        "especialidades": {"type": "array", "items": {"type": "string", "enum": ESPECIALIDADES}}, "activo": {"type": "boolean"},
    }),
    "Intervalo": objeto({"inicio": texto(pattern="^([01]\\d|2[0-3]):(00|30)$", example="08:00"), "fin": texto(pattern="^([01]\\d|2[0-3]):(00|30)$", example="13:00")}, ["inicio", "fin"]),
    "Jornada": objeto({
        "tecnico_id": TEXTO, "fecha": FECHA, "zona_horaria": texto(example="America/Lima"),
        "intervalos": {"type": "array", "items": ref("Intervalo")},
    }),
    "Ausencia": objeto({"tecnico_id": TEXTO, "fecha": FECHA, "motivo": TEXTO, "registrada_por": TEXTO, "registrada_en": texto(format="date-time")}),
    "Orden": objeto({
        "orden_id": TEXTO, "cliente_id": TEXTO, "ubicacion_id": TEXTO, "cliente_nombre": TEXTO, "direccion": TEXTO, "distrito": TEXTO,
        "descripcion": TEXTO, "tipo_servicio": {"type": "string", "enum": ESPECIALIDADES},
        "prioridad": {"type": "string", "enum": ["BAJA", "MEDIA", "ALTA"]}, "estado": {"type": "string", "enum": ESTADOS_ORDEN},
        "version": {"type": "integer"}, "creada_en": texto(format="date-time"), "lat": {"type": "number"}, "lng": {"type": "number"},
    }),
    "Visita": objeto({
        "visita_id": texto(example="VIS-…"), "orden_id": TEXTO, "tecnico_id": TEXTO, "tecnico_nombre": TEXTO,
        "cliente_nombre": TEXTO, "direccion": TEXTO, "distrito": TEXTO, "tipo_servicio": TEXTO, "orden_descripcion": TEXTO,
        "inicio": INSTANTE, "fin": INSTANTE, "fecha": FECHA, "numero_visita_orden": {"type": "integer"},
        "estado": {"type": "string", "enum": ["PROGRAMADA", "EN_ATENCION", "FINALIZADA", "CANCELADA"]},
        "version": {"type": "integer"},
    }),
    "Evidencia": objeto({
        "evidencia_id": TEXTO, "estado": {"type": "string", "enum": ["PENDIENTE", "CONFIRMADA", "RECHAZADA"]},
        "content_type": TEXTO, "url": texto("URL firmada de lectura (vence en minutos)."),
    }),
    "Parte": objeto({
        "parte_id": TEXTO, "visita_id": TEXTO, "orden_id": TEXTO, "tecnico_id": TEXTO,
        "estado": {"type": "string", "enum": ["BORRADOR", "FINALIZADO"]}, "diagnostico": TEXTO,
        "tareas": {"type": "array", "items": TEXTO}, "materiales": {"type": "array", "items": TEXTO},
        "resultado": {"type": "string", "enum": ["RESUELTO", "REQUIERE_REVISITA", "NO_ATENDIDO"]},
        "version": {"type": "integer"}, "evidencias": {"type": "array", "items": ref("Evidencia")},
    }),
}
for _n in ("Usuario", "Cliente", "Ubicacion", "Tecnico", "Orden", "Visita", "Parte"):
    SCHEMAS[_n]["additionalProperties"] = True


def cuerpo(esquema, ejemplo=None):
    medio = {"schema": esquema}
    if ejemplo:
        medio["example"] = ejemplo
    return {"required": True, "content": {"application/json": medio}}


def param(nombre, donde, descripcion, requerido=False, esquema=None):
    return {"name": nombre, "in": donde, "required": requerido or donde == "path", "description": descripcion, "schema": esquema or TEXTO}


LIMIT = param("limit", "query", "Tamaño de página, de 1 a 100.", esquema={"type": "integer", "minimum": 1, "maximum": 100})
CURSOR = param("cursor", "query", "`next_cursor` de la página anterior.")
IDEM = {"$ref": "#/components/parameters/IdempotencyKey"}
VERSION = {"version": {"type": "integer", "description": "Versión que viste por última vez. Si cambió, responde 409 VERSION_DESACTUALIZADA."}}


def op(resumen, roles, respuesta, *, estado="200", descripcion="", cuerpo_=None, params=(), idem=False, conflictos="", publico=False,
       nota_respuesta=None, alternativas=None, depende=False, extra=None):
    """roles: texto de los roles permitidos. respuesta: esquema de la respuesta exitosa.
    alternativas: {estado: descripción} de otras respuestas exitosas con el mismo esquema.
    depende: llama a otro servicio, así que puede responder 503. extra: {estado: respuesta de components} adicionales."""
    if idem:
        conflictos = ", ".join(c for c in (conflictos, "CLAVE_REUTILIZADA (la misma `Idempotency-Key` con otros datos)") if c)
    texto_desc = descripcion
    if roles:
        texto_desc = (texto_desc + "\n\n" if texto_desc else "") + f"**Roles permitidos:** {roles}."
    if conflictos:
        texto_desc += f"\n\n**Conflictos (409):** {conflictos}."
    operacion = {"summary": resumen, "description": texto_desc, "parameters": list(params) + ([IDEM] if idem else [])}
    if cuerpo_:
        operacion["requestBody"] = cuerpo_
    operacion["responses"] = {estado: {"description": nota_respuesta or "Correcto", "content": {"application/json": {"schema": respuesta}}}}
    for otro, nota in (alternativas or {}).items():
        operacion["responses"][otro] = {"description": nota, "content": {"application/json": {"schema": respuesta}}}
    if not publico:
        operacion["security"] = [{"bearerAuth": []}]
        operacion["responses"]["401"] = {"$ref": "#/components/responses/NoAutenticado"}
        operacion["responses"]["403"] = {"$ref": "#/components/responses/Prohibido"}
    else:
        operacion["security"] = []
    operacion["responses"]["400"] = {"$ref": "#/components/responses/EntradaInvalida"}
    if conflictos:
        operacion["responses"]["409"] = {"$ref": "#/components/responses/Conflicto"}
    if depende:
        operacion["responses"]["503"] = {"$ref": "#/components/responses/NoDisponible"}
    for codigo_http, nombre in (extra or {}).items():
        operacion["responses"][codigo_http] = {"$ref": f"#/components/responses/{nombre}"}
    return operacion


def con_404(operacion):
    operacion["responses"]["404"] = {"$ref": "#/components/responses/NoEncontrado"}
    return operacion


def p404(*args, **kw):
    return con_404(op(*args, **kw))


def id_ruta(nombre, descripcion):
    return param(nombre, "path", descripcion, True)


# --------------------------------------------------------------------------- rutas
RUTAS = {
    "usuarios": {
        ("POST", "/auth/login"): op(
            "Iniciar sesión", "", objeto({"token": texto("Token opaco para la cabecera `Authorization: Bearer <token>`."), "expira_en": {"type": "integer", "description": "Instante Unix de vencimiento (8 horas)."}}),
            descripcion="Único punto donde el cliente indica la empresa (`tenant_id`). Responde 401 con el mismo mensaje si la empresa, el correo o la contraseña no coinciden.",
            publico=True, cuerpo_=cuerpo(objeto({"tenant_id": texto(example="CLIMALIMA"), "email": texto(format="email"), "password": texto(format="password")}, ["tenant_id", "email", "password"])),
            extra={"401": "CredencialesInvalidas"},
        ),
        ("POST", "/usuarios"): op(
            "Crear usuario", "ADMIN", ref("Usuario"), estado="201",
            descripcion="La contraseña exige al menos 8 caracteres. Si el rol es `TECNICO`, `tecnico_id` es obligatorio y debe ser un técnico "
                        "de la misma empresa (si no existe, 404). El correo se guarda en minúsculas.",
            cuerpo_=cuerpo(objeto({
                "email": texto(format="email"), "nombre": texto(maxLength=200), "password": texto(minLength=8, format="password"),
                "rol": {"type": "string", "enum": ["ADMIN", "COORDINADOR", "TECNICO"]}, "tecnico_id": texto(maxLength=100),
            }, ["email", "nombre", "password", "rol"])), conflictos="CORREO_EN_USO (el correo ya existe en la empresa)",
            depende=True, extra={"404": "NoEncontrado"},
        ),
        ("GET", "/usuarios"): op(
            "Listar usuarios", "ADMIN", lista_de("Usuario"),
            params=[LIMIT, CURSOR, param("q", "query", "Busca por nombre o correo."),
                    param("rol", "query", "Filtra por rol.", esquema={"type": "string", "enum": ["ADMIN", "COORDINADOR", "TECNICO"]}),
                    param("estado", "query", "Filtra por estado.", esquema={"type": "string", "enum": ["ACTIVO", "INACTIVO"]})],
        ),
        ("GET", "/usuarios/me"): p404("Usuario de la sesión", TODOS, {**ref("Usuario"), "description": "Incluye `tenant_nombre`."}),
        ("PATCH", "/usuarios/{usuario_id}"): p404(
            "Actualizar usuario", "ADMIN", ref("Usuario"), params=[id_ruta("usuario_id", "ID del usuario.")],
            descripcion="Solo cambian los campos enviados. Un administrador no puede cambiar su propio rol ni estado. "
                        "Un usuario `INACTIVO` no puede iniciar sesión y sus tokens dejan de valer (hasta 60 s por la caché del autorizador). "
                        "Responde 404 si el usuario o el `tecnico_id` indicado no existen en la empresa.",
            cuerpo_=cuerpo(objeto({
                "nombre": texto(maxLength=200), "rol": {"type": "string", "enum": ["ADMIN", "COORDINADOR", "TECNICO"]},
                "estado": {"type": "string", "enum": ["ACTIVO", "INACTIVO"]}, "tecnico_id": texto(maxLength=100),
            })), depende=True,
        ),
    },
    "clientes": {
        ("POST", "/clientes"): op(
            "Crear cliente", GESTION, ref("Cliente"), estado="201", idem=True,
            cuerpo_=cuerpo(objeto({"nombre": texto(maxLength=200), "telefono": texto(maxLength=50), "correo": texto(maxLength=200)}, ["nombre"])),
        ),
        ("GET", "/clientes"): op("Listar clientes", GESTION, lista_de("Cliente"), descripcion="Ordenados por nombre.",
                                 params=[LIMIT, CURSOR, param("q", "query", "Busca por el inicio del nombre, sin distinguir mayúsculas ni tildes.")]),
        ("GET", "/clientes/{cliente_id}"): p404("Detalle de un cliente", GESTION, ref("Cliente"), params=[id_ruta("cliente_id", "ID del cliente.")]),
        ("PATCH", "/clientes/{cliente_id}"): p404(
            "Actualizar o desactivar un cliente", GESTION, ref("Cliente"), params=[id_ruta("cliente_id", "ID del cliente.")],
            descripcion="Se desactiva con `activo: false`; nunca se borra, para conservar el historial. Debe enviarse al menos un campo.",
            cuerpo_=cuerpo(objeto({"nombre": texto(maxLength=200), "telefono": texto(maxLength=50), "correo": texto(maxLength=200), "activo": {"type": "boolean"}})),
        ),
        ("POST", "/clientes/{cliente_id}/ubicaciones"): p404(
            "Crear ubicación de un cliente", GESTION, ref("Ubicacion"), estado="201", idem=True, params=[id_ruta("cliente_id", "ID del cliente.")],
            descripcion="`lat` y `lng` son opcionales, pero deben enviarse juntas. El punto se elige en el mapa.",
            conflictos="CLIENTE_INACTIVO",
            cuerpo_=cuerpo(objeto({
                "nombre": texto(maxLength=200), "direccion": texto(maxLength=300), "distrito": texto(maxLength=100), "referencia": texto(maxLength=300),
                "lat": {"type": "number", "minimum": -90, "maximum": 90}, "lng": {"type": "number", "minimum": -180, "maximum": 180},
            }, ["nombre", "direccion", "distrito"])),
        ),
        ("GET", "/clientes/{cliente_id}/ubicaciones"): p404("Listar ubicaciones de un cliente", GESTION, lista_de("Ubicacion"), params=[id_ruta("cliente_id", "ID del cliente."), LIMIT, CURSOR]),
        ("GET", "/clientes/{cliente_id}/ubicaciones/{ubicacion_id}"): p404(
            "Detalle de una ubicación", GESTION,
            {"allOf": [ref("Ubicacion"), objeto({"cliente_nombre": TEXTO, "cliente_activo": {"type": "boolean"}})]},
            descripcion="Incluye el nombre y el estado del cliente (Órdenes lo usa para validar y copiar los datos).",
            params=[id_ruta("cliente_id", "ID del cliente."), id_ruta("ubicacion_id", "ID de la ubicación.")]),
    },
    "tecnicos": {
        ("POST", "/tecnicos"): op(
            "Crear técnico", GESTION, ref("Tecnico"), estado="201", idem=True,
            cuerpo_=cuerpo(objeto({"nombre": texto(maxLength=200), "especialidades": {"type": "array", "minItems": 1, "items": {"type": "string", "enum": ESPECIALIDADES}}}, ["nombre", "especialidades"])),
        ),
        ("GET", "/tecnicos"): op("Listar técnicos", GESTION, lista_de("Tecnico"), params=[LIMIT, CURSOR]),
        ("GET", "/tecnicos/disponibles"): op(
            "Técnicos con jornada en una fecha", GESTION,
            objeto({"fecha": FECHA, "items": {"type": "array", "items": objeto({"tecnico_id": TEXTO, "nombre": TEXTO, "especialidades": {"type": "array", "items": TEXTO}, "intervalos": {"type": "array", "items": ref("Intervalo")}})}}),
            descripcion="Candidatos del día en una sola consulta. Excluye técnicos inactivos, ausentes o sin jornada definida.",
            params=[param("fecha", "query", "Día AAAA-MM-DD.", True, FECHA), param("especialidad", "query", "Filtra por especialidad.", esquema={"type": "string", "enum": ESPECIALIDADES})],
        ),
        ("GET", "/tecnicos/{tecnico_id}"): p404("Detalle de un técnico", "ADMIN, COORDINADOR, o TECNICO solo sobre sí mismo", ref("Tecnico"), params=[id_ruta("tecnico_id", "ID del técnico.")]),
        ("PATCH", "/tecnicos/{tecnico_id}"): p404(
            "Actualizar o desactivar un técnico", GESTION, ref("Tecnico"), params=[id_ruta("tecnico_id", "ID del técnico.")],
            cuerpo_=cuerpo(objeto({"nombre": texto(maxLength=200), "especialidades": {"type": "array", "items": {"type": "string", "enum": ESPECIALIDADES}}, "activo": {"type": "boolean"}})),
        ),
        ("PUT", "/tecnicos/{tecnico_id}/jornadas/{fecha}"): p404(
            "Definir la jornada de un día", GESTION, ref("Jornada"), params=[id_ruta("tecnico_id", "ID del técnico."), param("fecha", "path", "Día AAAA-MM-DD.", True, FECHA)],
            descripcion="Reemplaza la jornada del día. Horas locales de Lima, en HH:00 o HH:30, ordenadas y sin solaparse.",
            cuerpo_=cuerpo(objeto({"intervalos": {"type": "array", "minItems": 1, "items": ref("Intervalo")}}, ["intervalos"], {"intervalos": [{"inicio": "08:00", "fin": "13:00"}, {"inicio": "14:00", "fin": "18:00"}]})),
        ),
        ("PUT", "/tecnicos/{tecnico_id}/ausencias/{fecha}"): p404(
            "Registrar ausencia de un día", "ADMIN, COORDINADOR, o TECNICO solo sobre sí mismo", ref("Ausencia"), estado="201",
            nota_respuesta="Ausencia registrada", alternativas={"200": "Ya estaba registrada: la devuelve sin cambios ni nueva notificación."},
            params=[id_ruta("tecnico_id", "ID del técnico."), param("fecha", "path", "Día AAAA-MM-DD.", True, FECHA)],
            descripcion="Agenda reasigna las visitas de ese día. Registrarla dos veces devuelve la misma ausencia sin volver a notificar.",
            cuerpo_=cuerpo(objeto({"motivo": texto(maxLength=300)}, ["motivo"])),
        ),
        ("GET", "/tecnicos/{tecnico_id}/jornadas"): p404(
            "Consultar jornadas y ausencias de un rango", "ADMIN, COORDINADOR, o TECNICO solo sobre sí mismo", objeto({"jornadas": {"type": "array", "items": ref("Jornada")}, "ausencias": {"type": "array", "items": ref("Ausencia")}}),
            params=[id_ruta("tecnico_id", "ID del técnico."), param("desde", "query", "Primer día AAAA-MM-DD.", True, FECHA), param("hasta", "query", "Último día AAAA-MM-DD (rango máximo de 62 días).", True, FECHA)],
        ),
    },
    "ordenes": {
        ("POST", "/ordenes"): p404(
            "Crear orden de trabajo", GESTION, ref("Orden"), estado="201", idem=True, depende=True,
            descripcion="La orden nace `ABIERTA`. Copia el nombre, la dirección y el punto del cliente y la ubicación. "
                        "Responde 404 si el cliente o la ubicación no existen en la empresa.",
            conflictos="CLIENTE_INACTIVO",
            cuerpo_=cuerpo(objeto({
                "cliente_id": TEXTO, "ubicacion_id": TEXTO, "descripcion": texto(maxLength=2000),
                "tipo_servicio": {"type": "string", "enum": ESPECIALIDADES}, "prioridad": {"type": "string", "enum": ["BAJA", "MEDIA", "ALTA"]},
            }, ["cliente_id", "ubicacion_id", "descripcion", "tipo_servicio", "prioridad"])),
        ),
        ("GET", "/ordenes"): op(
            "Listar órdenes", GESTION, lista_de("Orden"),
            descripcion="Más recientes primero (por fecha de creación; con `estado=CERRADA` o `CANCELADA`, por fecha de término). "
                        "No se puede filtrar por estado y por cliente a la vez.",
            params=[LIMIT, CURSOR, param("estado", "query", "Filtra por estado.", esquema={"type": "string", "enum": ESTADOS_ORDEN}), param("cliente_id", "query", "Filtra por cliente.")],
        ),
        ("GET", "/ordenes/mapa"): op(
            "Puntos para el mapa del panel", GESTION,
            objeto({"puntos": {"type": "array", "items": objeto({"orden_id": TEXTO, "estado": TEXTO, "lat": {"type": "number"}, "lng": {"type": "number"}, "cliente_nombre": TEXTO, "distrito": TEXTO, "prioridad": TEXTO, "tipo_servicio": TEXTO, "descripcion": TEXTO})},
                    "conteo": {"type": "object", "additionalProperties": {"type": "integer"}}, "cerradas_desde": texto(format="date-time")}),
            descripcion="Órdenes vivas y las cerradas en los últimos 14 días (por fecha de cierre). `conteo` cuenta hasta 400 por estado.",
        ),
        ("GET", "/ordenes/{orden_id}"): p404("Detalle de una orden", GESTION, ref("Orden"), params=[id_ruta("orden_id", "ID de la orden.")]),
        ("PATCH", "/ordenes/{orden_id}"): p404(
            "Cambiar la prioridad", GESTION, ref("Orden"), params=[id_ruta("orden_id", "ID de la orden.")],
            descripcion="Solo cambia la prioridad. La versión evita pisar un cambio que el usuario no vio.", conflictos="ORDEN_TERMINADA, VERSION_DESACTUALIZADA",
            cuerpo_=cuerpo(objeto({"prioridad": {"type": "string", "enum": ["BAJA", "MEDIA", "ALTA"]}, **VERSION}, ["prioridad", "version"])),
        ),
        ("GET", "/ordenes/{orden_id}/historial"): p404(
            "Historial de eventos de la orden", GESTION,
            objeto({"items": {"type": "array", "items": {"type": "object", "additionalProperties": True}}, "next_cursor": {**TEXTO, "nullable": True}}),
            params=[id_ruta("orden_id", "ID de la orden."), LIMIT, CURSOR], descripcion="Más recientes primero.",
        ),
        ("POST", "/ordenes/{orden_id}/cerrar"): p404(
            "Cerrar la orden", GESTION, ref("Orden"), params=[id_ruta("orden_id", "ID de la orden.")],
            descripcion="Solo desde `PENDIENTE_DE_CIERRE`. Pasa por `CIERRE_EN_PROCESO` mientras Agenda bloquea nuevas visitas. "
                        "Si se interrumpe, repetir la llamada la completa. Si ya está cerrada, devuelve la orden sin cambios.",
            conflictos="ORDEN_TERMINADA, ESTADO_NO_PERMITE, OPERACION_EN_CURSO, VISITAS_ACTIVAS, VERSION_DESACTUALIZADA, CONFLICTO_CONCURRENTE",
            extra={"503": "CierrePendiente"},
        ),
        ("POST", "/ordenes/{orden_id}/cancelar"): p404(
            "Cancelar la orden", GESTION, ref("Orden"), params=[id_ruta("orden_id", "ID de la orden.")],
            descripcion="Desde `ABIERTA`, `PROGRAMADA`, `REQUIERE_REVISITA` o `PENDIENTE_DE_CIERRE`. Cancela también las visitas programadas "
                        "y responde cuántas en `visitas_canceladas`. Misma coordinación que `cerrar`; si una visita está en atención, se rechaza.",
            conflictos="ORDEN_TERMINADA, ESTADO_NO_PERMITE, OPERACION_EN_CURSO, VISITA_EN_ATENCION, VERSION_DESACTUALIZADA, CONFLICTO_CONCURRENTE",
            extra={"503": "CierrePendiente"},
        ),
    },
    "agenda": {
        ("POST", "/visitas"): p404(
            "Programar una visita", GESTION, ref("Visita"), estado="201", idem=True, depende=True,
            descripcion="Valida contra Órdenes y Técnicos: orden admite visitas, técnico activo, con la especialidad, presente y dentro de su jornada. "
                        "Reserva bloques de 30 minutos para que dos visitas no se solapen. De 30 minutos a 4 horas, el mismo día y no en el pasado (400). "
                        "Responde 404 si la orden o el técnico no existen.",
            conflictos="ORDEN_NO_ADMITE_VISITAS, TECNICO_INACTIVO, ESPECIALIDAD_INCOMPATIBLE, TECNICO_AUSENTE, FUERA_DE_JORNADA, HORARIO_OCUPADO",
            cuerpo_=cuerpo(objeto({"orden_id": TEXTO, "tecnico_id": TEXTO, "inicio": INSTANTE, "fin": INSTANTE}, ["orden_id", "tecnico_id", "inicio", "fin"]),
                           {"orden_id": "ORD-…", "tecnico_id": "TEC-…", "inicio": "2026-11-20T15:00:00Z", "fin": "2026-11-20T16:00:00Z"}),
        ),
        ("GET", "/visitas"): op(
            "Listar visitas", f"{TODOS}. El técnico ve siempre sus propias visitas", lista_de("Visita"),
            descripcion="Indica al menos uno de `tecnico_id`, `orden_id` o `fecha` (el técnico no necesita ninguno). Con `tecnico_id` puedes acotar con `fecha` o `desde`.",
            params=[LIMIT, CURSOR, param("tecnico_id", "query", "Visitas de un técnico."), param("orden_id", "query", "Visitas de una orden."),
                    param("fecha", "query", "Visitas de un día AAAA-MM-DD.", esquema=FECHA), param("desde", "query", "Con `tecnico_id`: desde este día.", esquema=FECHA)],
        ),
        ("GET", "/visitas/{visita_id}"): p404("Detalle de una visita", f"{TODOS}. El técnico solo las suyas", ref("Visita"), params=[id_ruta("visita_id", "ID de la visita.")]),
        ("POST", "/visitas/{visita_id}/reprogramar"): p404(
            "Reprogramar una visita", GESTION, ref("Visita"), params=[id_ruta("visita_id", "ID de la visita.")],
            descripcion="Solo visitas `PROGRAMADA` y a un horario futuro. Si falla, la reserva anterior se conserva. `tecnico_id` es opcional: sin él se mantiene el técnico.",
            conflictos="ESTADO_NO_PERMITE, VERSION_DESACTUALIZADA, HORARIO_OCUPADO, FUERA_DE_JORNADA, TECNICO_AUSENTE, TECNICO_INACTIVO, ESPECIALIDAD_INCOMPATIBLE",
            depende=True,
            cuerpo_=cuerpo(objeto({**VERSION, "inicio": INSTANTE, "fin": INSTANTE, "tecnico_id": TEXTO}, ["version", "inicio", "fin"])),
        ),
        ("POST", "/visitas/{visita_id}/cancelar"): p404(
            "Cancelar una visita", GESTION, ref("Visita"), params=[id_ruta("visita_id", "ID de la visita.")],
            descripcion="Libera los bloques. Repetirla no vuelve a restar del contador de la orden.", conflictos="ESTADO_NO_PERMITE, VERSION_DESACTUALIZADA",
        ),
        ("POST", "/visitas/{visita_id}/iniciar"): p404(
            "Iniciar la atención de una visita", "TECNICO (solo sus visitas), ADMIN", ref("Visita"), params=[id_ruta("visita_id", "ID de la visita.")],
            descripcion="Pasa la visita a `EN_ATENCION`. Es el paso previo a crear el parte.", conflictos="ESTADO_NO_PERMITE, VERSION_DESACTUALIZADA",
        ),
        ("GET", "/disponibilidad"): op(
            "Horarios libres por técnico", GESTION,
            objeto({"fecha": FECHA, "duracion_min": {"type": "integer"}, "items": {"type": "array", "items": objeto({
                "tecnico_id": TEXTO, "nombre": TEXTO, "especialidades": {"type": "array", "items": TEXTO},
                "horarios": {"type": "array", "items": TEXTO, "description": "Horas de inicio posibles, por ejemplo `08:00`."}})}}),
            descripcion="Combina las jornadas (Técnicos) con los bloques ya ocupados (Agenda) y descarta horarios que ya pasaron. Con `sugerir=true` ordena los candidatos con las métricas de Analítica.",
            depende=True,
            params=[param("fecha", "query", "Día AAAA-MM-DD.", True, FECHA), param("especialidad", "query", "Filtra por especialidad.", esquema={"type": "string", "enum": ESPECIALIDADES}),
                    param("duracion_min", "query", "Duración buscada en minutos: múltiplo de 30, hasta 240 (por defecto 60).", esquema={"type": "integer", "default": 60, "minimum": 30, "maximum": 240, "multipleOf": 30}),
                    param("sugerir", "query", "`true` para ordenar por carga y tasa de resolución.", esquema={"type": "string", "enum": ["true", "false"]})],
        ),
        ("GET", "/alertas"): op(
            "Alertas de agenda", GESTION,
            objeto({"pendientes": {"type": "array", "items": {"type": "object", "additionalProperties": True}, "description": "Visitas sin resolver, por inicio."},
                    "recientes": {"type": "array", "items": {"type": "object", "additionalProperties": True}, "description": "Últimos 15 avisos, por ejemplo reasignaciones."}}),
        ),
    },
    "partes": {
        ("POST", "/visitas/{visita_id}/partes"): p404(
            "Crear el parte de una visita", "TECNICO (solo sus visitas), ADMIN", {**ref("Parte"), "description": "El borrador, vacío."}, estado="201",
            params=[id_ruta("visita_id", "ID de la visita.")],
            descripcion="La visita debe estar `EN_ATENCION`. Si ya hay un borrador, lo devuelve con 200 en vez de crear otro.",
            conflictos="VISITA_NO_EN_ATENCION, PARTE_YA_FINALIZADO", depende=True, nota_respuesta="Borrador creado",
            alternativas={"200": "Ya existía un borrador para la visita: lo devuelve."},
        ),
        ("GET", "/visitas/{visita_id}/parte"): p404("Parte de una visita", f"{TODOS}. El técnico solo los suyos", ref("Parte"), params=[id_ruta("visita_id", "ID de la visita.")]),
        ("GET", "/partes"): op(
            "Listar partes de una orden", GESTION, lista_de("Parte"), params=[param("orden_id", "query", "ID de la orden.", True), LIMIT, CURSOR]),
        ("GET", "/partes/{parte_id}"): p404("Detalle de un parte", f"{TODOS}. El técnico solo los suyos", ref("Parte"), params=[id_ruta("parte_id", "ID del parte.")],
                                           descripcion="Incluye las evidencias, con URL firmada de lectura."),
        ("PUT", "/partes/{parte_id}"): p404(
            "Editar el borrador del parte", "TECNICO (solo los suyos), ADMIN", ref("Parte"), params=[id_ruta("parte_id", "ID del parte.")],
            descripcion="Solo cambian los campos enviados; un borrador puede quedar incompleto.", conflictos="PARTE_YA_FINALIZADO, VERSION_DESACTUALIZADA",
            cuerpo_=cuerpo(objeto({
                **VERSION, "diagnostico": texto(maxLength=2000), "tareas": {"type": "array", "maxItems": 30, "items": texto(maxLength=300)},
                "materiales": {"type": "array", "maxItems": 30, "items": texto(maxLength=300)},
                "resultado": {"type": "string", "enum": ["RESUELTO", "REQUIERE_REVISITA", "NO_ATENDIDO"]},
            }, ["version"])),
        ),
        ("POST", "/partes/{parte_id}/finalizar"): p404(
            "Finalizar el parte", "TECNICO (solo los suyos), ADMIN", ref("Parte"), params=[id_ruta("parte_id", "ID del parte.")],
            descripcion="Exige diagnóstico y resultado, y al menos una tarea salvo que el resultado sea `NO_ATENDIDO`. Cierra la visita y publica el resultado para Órdenes y Analítica.",
            conflictos="PARTE_INCOMPLETO, VERSION_DESACTUALIZADA",
            cuerpo_=cuerpo(objeto(VERSION, ["version"])),
        ),
        ("POST", "/partes/{parte_id}/evidencias"): p404(
            "Pedir URL firmada para subir una foto", "TECNICO (solo los suyos), ADMIN",
            objeto({"evidencia_id": TEXTO, "url": texto("URL del bucket S3."), "fields": {"type": "object", "additionalProperties": TEXTO, "description": "Campos del formulario de subida (POST multipart a `url`)."},
                    "max_bytes": {"type": "integer", "example": 5242880}, "expira_en_segundos": {"type": "integer", "example": 300}}),
            estado="201", params=[id_ruta("parte_id", "ID del parte.")],
            descripcion="La foto no pasa por esta API: se sube directo a S3 con los `fields` y luego se confirma. Máximo 5 MB, JPG o PNG, y 20 solicitudes por parte.",
            conflictos="PARTE_YA_FINALIZADO, EVIDENCIA_NO_ADMITIDA",
            cuerpo_=cuerpo(objeto({"content_type": {"type": "string", "enum": ["image/jpeg", "image/png"]}, "nombre": texto(maxLength=200)}, ["content_type"])),
        ),
        ("POST", "/evidencias/{evidencia_id}/confirmar"): p404(
            "Confirmar una foto subida", "TECNICO (solo los suyos), ADMIN",
            objeto({"evidencia_id": TEXTO, "estado": {"type": "string", "enum": ["CONFIRMADA", "RECHAZADA"]}}),
            params=[id_ruta("evidencia_id", "ID de la evidencia.")],
            descripcion="Revisa el archivo en S3 (tamaño y tipo). `RECHAZADA` si no cumple.", conflictos="ARCHIVO_NO_ENCONTRADO",
        ),
    },
    "analitica": {
        ("GET", "/analitica/dashboard"): op(
            "Resumen mensual e histórico", GESTION,
            objeto({"periodo": texto(example="2026-11"), "ordenes_creadas": {"type": "integer"}, "ordenes_abiertas": {"type": "integer"}, "ordenes_cerradas": {"type": "integer"},
                    "ordenes_canceladas": {"type": "integer"}, "visitas_programadas": {"type": "integer"}, "visitas_completadas": {"type": "integer"},
                    "tiempo_promedio_cierre_dias": {"type": "number", "description": "Solo aparece si hubo órdenes cerradas."},
                    "historico": {"type": "array", "items": {"type": "object", "additionalProperties": True, "description": "Mismos campos, de meses anteriores."}}}),
            descripcion="Se alimenta de eventos: puede tardar unos segundos en reflejar un cambio reciente.",
            params=[param("periodo", "query", "Mes AAAA-MM (por defecto el actual).", esquema={"type": "string", "pattern": "^\\d{4}-\\d{2}$"})],
        ),
        ("GET", "/analitica/tecnicos"): op(
            "Métricas de todos los técnicos", GESTION, objeto({"fecha": FECHA, "items": {"type": "array", "items": ref("MetricasTecnico")}}),
            params=[param("fecha", "query", "Día AAAA-MM-DD (por defecto hoy en Lima).", esquema=FECHA)],
        ),
        ("GET", "/analitica/tecnicos/{tecnico_id}"): op(
            "Métricas de un técnico", GESTION, {"allOf": [objeto({"fecha": FECHA}), ref("MetricasTecnico")]},
            descripcion="Analítica no guarda el catálogo de técnicos: un técnico sin historial devuelve los contadores en cero.",
            params=[id_ruta("tecnico_id", "ID del técnico."), param("fecha", "query", "Día AAAA-MM-DD (por defecto hoy en Lima).", esquema=FECHA)],
        ),
    },
}
SCHEMAS["MetricasTecnico"] = objeto({
    "tecnico_id": TEXTO, "carga_dia": {"type": "integer", "description": "Visitas asignadas ese día."}, "completadas_dia": {"type": "integer"},
    "visitas_completadas_total": {"type": "integer"}, "revisitas_generadas": {"type": "integer"},
    "tasa_resolucion": {"type": "number", "description": "Resueltas en la primera visita, de 0 a 1. No aparece sin historial."},
    "tiempo_promedio_min": {"type": "number", "description": "Duración media de una visita. No aparece sin historial."},
})

RESPUESTAS = {
    "EntradaInvalida": ("400", "Entrada inválida (`ENTRADA_INVALIDA`).", "ENTRADA_INVALIDA"),
    "NoAutenticado": ("401", "Sesión no válida o vencida (`NO_AUTENTICADO`).", "NO_AUTENTICADO"),
    "Prohibido": ("403", "El rol no tiene permiso (`PROHIBIDO`).", "PROHIBIDO"),
    "NoEncontrado": ("404", "No existe o es de otra empresa (`NO_ENCONTRADO`).", "NO_ENCONTRADO"),
    "Conflicto": ("409", "Conflicto de estado, versión u horario. El campo `error.codigo` dice cuál.", "HORARIO_OCUPADO"),
    "CredencialesInvalidas": ("401", "Empresa, correo o contraseña incorrectos, o cuenta inactiva (`CREDENCIALES_INVALIDAS`).", "CREDENCIALES_INVALIDAS"),
    "NoDisponible": ("503", "Un servicio relacionado no respondió (`SERVICIO_NO_DISPONIBLE`). Se puede reintentar.", "SERVICIO_NO_DISPONIBLE"),
    "CierrePendiente": ("503", "No se pudo confirmar con Agenda (`CIERRE_PENDIENTE`). La orden queda en `CIERRE_EN_PROCESO`: repetir la llamada la completa.", "CIERRE_PENDIENTE"),
}

DESCRIPCION = """{titulo}. Cada microservicio es su propia API: este documento cubre solo {titulo_corto}.

**Cómo probarlo:** 1) en el servicio *usuarios* ejecuta `POST /auth/login`; 2) copia el `token`; 3) pulsa **Authorize** y pégalo (sin escribir `Bearer`); 4) prueba cualquier endpoint de cualquier servicio: el token vale para todos.

El tenant y el rol salen del token, nunca del cuerpo ni de la URL. Los errores tienen la forma `{{"error": {{"codigo", "mensaje", "detalle"}}}}`. Las listas se paginan con `limit` y `cursor`."""


def rutas_de_serverless(servicio):
    funcion, encontradas = None, []
    for linea in (RAIZ / f"backend/{servicio}/serverless.yml").read_text(encoding="utf-8").splitlines():
        m = re.search(r"http: \{ path: '?([^',]+)'?, method: (\w+)", linea)
        if m:
            encontradas.append((m.group(2).upper(), "/" + m.group(1)))
    return encontradas


def referencias(nodo, acumulado):
    if isinstance(nodo, dict):
        for clave, valor in nodo.items():
            if clave == "$ref" and valor.startswith("#/components/schemas/"):
                nombre = valor.rsplit("/", 1)[1]
                if nombre not in acumulado:
                    acumulado.add(nombre)
                    referencias(SCHEMAS[nombre], acumulado)
            else:
                referencias(valor, acumulado)
    elif isinstance(nodo, list):
        for valor in nodo:
            referencias(valor, acumulado)


def construir(servicio):
    declaradas = set(rutas_de_serverless(servicio))
    descritas = set(RUTAS[servicio])
    if declaradas != descritas:
        sys.exit(f"{servicio}: rutas distintas. Sin documentar: {sorted(declaradas - descritas)}. Documentadas que ya no existen: {sorted(descritas - declaradas)}.")
    rutas = {}
    for (metodo, ruta), operacion in RUTAS[servicio].items():
        operacion = json.loads(json.dumps(operacion))
        operacion["operationId"] = f"{servicio}_{metodo.lower()}_{re.sub(r'[^a-z0-9]+', '_', ruta.lower()).strip('_')}"
        operacion["tags"] = [SERVICIOS[servicio]]
        rutas.setdefault(ruta, {})[metodo.lower()] = operacion
    usados = {"Error"}
    referencias(rutas, usados)
    return {
        "openapi": "3.0.3",
        "info": {
            "title": f"Trazora FSM · {SERVICIOS[servicio]}", "version": "1.0.0",
            "description": DESCRIPCION.format(titulo=f"API de {SERVICIOS[servicio]}", titulo_corto=f"el servicio de {servicio}"),
        },
        "servers": [{"url": "https://REEMPLAZAR.execute-api.us-east-1.amazonaws.com/dev", "description": "La página /docs/ la reemplaza por la URL real del servicio."}],
        "tags": [{"name": SERVICIOS[servicio]}],
        "paths": rutas,
        "components": {
            "securitySchemes": {"bearerAuth": {"type": "http", "scheme": "bearer", "description": "Token que devuelve `POST /auth/login`. Vale 8 horas."}},
            "parameters": {"IdempotencyKey": {"name": "Idempotency-Key", "in": "header", "required": False,
                                              "description": "Identificador único de la creación. Repetir la petición con la misma clave devuelve el mismo resultado en vez de crear un duplicado.", "schema": TEXTO}},
            "responses": {nombre: {"description": d, "content": {"application/json": {"schema": ref("Error"), "example": {"error": {"codigo": c, "mensaje": "…", "detalle": {}}}}}} for nombre, (_, d, c) in RESPUESTAS.items()},
            "schemas": {n: SCHEMAS[n] for n in sorted(usados)},
        },
    }


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    total = 0
    for servicio in SERVICIOS:
        spec = construir(servicio)
        (SALIDA / f"{servicio}.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        total += sum(len(v) for v in spec["paths"].values())
    (SALIDA / "servicios.json").write_text(
        json.dumps([{"id": s, "nombre": n, "archivo": f"{s}.json"} for s, n in SERVICIOS.items()], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OpenAPI: {len(SERVICIOS)} servicios, {total} operaciones en docs/openapi/")


if __name__ == "__main__":
    main()
