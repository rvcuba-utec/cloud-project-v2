"""Reglas del parte de trabajo y de sus evidencias, sin acceso a AWS."""
from trazora_common.http import conflicto, entrada_invalida, opcion, texto

BORRADOR = "BORRADOR"
FINALIZADO = "FINALIZADO"
RESUELTO = "RESUELTO"
REQUIERE_REVISITA = "REQUIERE_REVISITA"
NO_ATENDIDO = "NO_ATENDIDO"
RESULTADOS = {RESUELTO, REQUIERE_REVISITA, NO_ATENDIDO}

PENDIENTE = "PENDIENTE"
CONFIRMADA = "CONFIRMADA"
RECHAZADA = "RECHAZADA"
TIPOS_ARCHIVO = {"image/jpeg": "jpg", "image/png": "png"}
MAX_BYTES = 5 * 1024 * 1024
MAX_SOLICITUDES = 20  # Por parte. Cuenta también las subidas abandonadas.
VALIDEZ_FIRMA_SEGUNDOS = 300

MAX_DIAGNOSTICO = 2000
MAX_ELEMENTOS = 30
MAX_ELEMENTO = 300


def sk_parte(parte_id):
    return f"PARTE#{parte_id}"


def sk_marca(visita_id):
    """Solo existe una por visita: es lo que garantiza un único parte."""
    return f"MARCA_VISITA#{visita_id}"


def sk_evidencia(evidencia_id):
    return f"EVIDENCIA#{evidencia_id}"


def indice_de_orden(tenant_id, orden_id, parte_id):
    return {"GSI1PK": f"TENANT#{tenant_id}#ORDEN#{orden_id}", "GSI1SK": f"PARTE#{parte_id}"}


def indice_de_parte(tenant_id, parte_id, evidencia_id):
    return {"GSI1PK": f"TENANT#{tenant_id}#PARTE#{parte_id}", "GSI1SK": f"EVIDENCIA#{evidencia_id}"}


def clave_objeto(tenant_id, orden_id, visita_id, evidencia_id, extension):
    return f"tenants/{tenant_id}/ordenes/{orden_id}/visitas/{visita_id}/{evidencia_id}.{extension}"


def leer_clave_objeto(clave):
    """Devuelve (tenant_id, evidencia_id), o None si la clave no sigue el formato del backend."""
    partes = clave.split("/")
    if len(partes) != 7 or partes[0] != "tenants" or "." not in partes[-1]:
        return None
    return partes[1], partes[-1].rsplit(".", 1)[0]


def lista_textos(datos, campo):
    valor = datos.get(campo)
    if valor is None:
        return []
    if not isinstance(valor, list) or len(valor) > MAX_ELEMENTOS:
        raise entrada_invalida(f"El campo {campo} no es válido", campo=campo)
    limpios = []
    for elemento in valor:
        if not isinstance(elemento, str) or len(elemento) > MAX_ELEMENTO:
            raise entrada_invalida(f"El campo {campo} no es válido", campo=campo)
        if elemento.strip():
            limpios.append(elemento.strip())
    return limpios


def cambios_de_borrador(datos):
    """Solo los campos enviados. Un borrador puede quedar incompleto; finalizar exige lo demás."""
    cambios = {}
    if "diagnostico" in datos:
        cambios["diagnostico"] = texto(datos, "diagnostico", MAX_DIAGNOSTICO, obligatorio=False) or ""
    for campo in ("tareas", "materiales"):
        if campo in datos:
            cambios[campo] = lista_textos(datos, campo)
    if "resultado" in datos:
        cambios["resultado"] = opcion(datos, "resultado", RESULTADOS) if datos["resultado"] else ""
    return cambios


def exigir_completo(parte):
    if not parte.get("diagnostico"):
        raise conflicto("PARTE_INCOMPLETO", "Falta el diagnóstico", campo="diagnostico")
    if not parte.get("resultado"):
        raise conflicto("PARTE_INCOMPLETO", "Falta el resultado", campo="resultado")
    # Si no se atendió, el diagnóstico explica el motivo y no hay tareas que informar.
    if parte["resultado"] != NO_ATENDIDO and not parte.get("tareas"):
        raise conflicto("PARTE_INCOMPLETO", "Indica al menos una tarea realizada", campo="tareas")


def archivo_valido(tamano, tipo):
    return 0 < tamano <= MAX_BYTES and tipo in TIPOS_ARCHIVO
