import base64
import json
from unittest import mock

import boto3
import pytest
from moto import mock_aws

from apoyo_pruebas import crear_tabla, ctx, cuerpo, entorno_aws, peticion
from trazora_common import dynamo, eventos, interno
from trazora_common.http import ApiError

from dominio import almacen
from dominio import partes as dom
from handlers import evidencias, on_evidencia, partes

BUCKET = "evidencias-prueba"
VISITA = {
    "visita_id": "VIS-1", "orden_id": "OT-1", "tecnico_id": "T1", "tecnico_nombre": "Carlos", "cliente_nombre": "López",
    "direccion": "Av. 1", "distrito": "Miraflores", "fecha": "2026-11-10", "numero_visita_orden": 1, "estado": "EN_ATENCION",
}
TECNICO = ctx(rol="TECNICO", tecnico="T1")
OTRO_TECNICO = ctx(rol="TECNICO", usuario="U2", tecnico="T2")


@pytest.fixture(autouse=True)
def aws(monkeypatch):
    entorno_aws(monkeypatch, "t_partes")
    monkeypatch.setenv("AGENDA_URL", "https://agenda")
    monkeypatch.setenv("BUCKET", BUCKET)
    with mock_aws():
        dynamo.reiniciar()
        eventos.reiniciar()
        almacen.reiniciar()
        crear_tabla("t_partes", "GSI1")
        boto3.client("s3").create_bucket(Bucket=BUCKET)
        monkeypatch.setenv("TOPIC_ARN", boto3.client("sns").create_topic(Name="e")["TopicArn"])
        with mock.patch.object(interno, "llamar", return_value=dict(VISITA)) as llamada:
            yield llamada
        dynamo.reiniciar()
        eventos.reiniciar()
        almacen.reiniciar()


def nuevo_parte(autorizador=TECNICO, visita="VIS-1"):
    r = partes.crear(peticion(autorizador, ruta={"visita_id": visita}, headers={"Authorization": "Bearer t"}), None)
    assert r["statusCode"] in (200, 201), r["body"]
    return cuerpo(r)


def editar(parte, autorizador=TECNICO, **cambios):
    return partes.editar(peticion(autorizador, {"version": parte["version"], **cambios}, ruta={"parte_id": parte["parte_id"]}), None)


def completo(autorizador=TECNICO):
    parte = nuevo_parte(autorizador)
    r = editar(parte, autorizador, diagnostico="Filtro obstruido", tareas=["Limpieza"], materiales=["Filtro"], resultado="RESUELTO")
    assert r["statusCode"] == 200, r["body"]
    return cuerpo(r)


def finalizar(parte, autorizador=TECNICO):
    return partes.finalizar(peticion(autorizador, {"version": parte["version"]}, ruta={"parte_id": parte["parte_id"]}), None)


def outbox(tenant="CLIMALIMA"):
    return dynamo.consultar_todo(dynamo.tabla(), f"TENANT#{tenant}", eventos.PREFIJO_OUTBOX)


def solicitar(parte, tipo="image/jpeg", autorizador=TECNICO):
    return evidencias.solicitar(peticion(autorizador, {"content_type": tipo, "nombre": "foto.jpg"}, ruta={"parte_id": parte["parte_id"]}), None)


def clave_guardada(evidencia_id):
    return dynamo.tabla().get_item(Key={"PK": "TENANT#CLIMALIMA", "SK": f"EVIDENCIA#{evidencia_id}"})["Item"]["object_key"]


def subir(clave, contenido=b"foto", tipo="image/jpeg"):
    boto3.client("s3").put_object(Bucket=BUCKET, Key=clave, Body=contenido, ContentType=tipo)


def notificar(clave):
    on_evidencia.lambda_handler({"Records": [{"s3": {"object": {"key": clave}}}]}, None)


def evidencia_estado(evidencia_id):
    return dynamo.tabla().get_item(Key={"PK": "TENANT#CLIMALIMA", "SK": f"EVIDENCIA#{evidencia_id}"})["Item"]["estado"]


# ---- Crear
def test_crear_borrador_con_copias_de_la_visita():
    parte = nuevo_parte()
    assert parte["estado"] == "BORRADOR" and parte["tecnico_id"] == "T1" and parte["orden_id"] == "OT-1"
    assert parte["cliente_nombre"] == "López"
    assert "PK" not in parte and "GSI1PK" not in parte


def test_repetir_crear_devuelve_el_mismo_borrador(aws):
    primero = nuevo_parte()
    assert nuevo_parte()["parte_id"] == primero["parte_id"]
    assert aws.call_count == 1  # El segundo ni siquiera consulta Agenda.


def test_creacion_simultanea_produce_un_solo_parte():
    """El perdedor no vio el marcador al leer, pero la transacción lo detiene."""
    primero = nuevo_parte()
    original = partes._parte_de_visita
    lecturas = []

    def ciega_la_primera_vez(*args):
        lecturas.append(1)
        return None if len(lecturas) == 1 else original(*args)

    with mock.patch.object(partes, "_parte_de_visita", side_effect=ciega_la_primera_vez):
        segundo = nuevo_parte()
    assert segundo["parte_id"] == primero["parte_id"]
    partes_guardados = dynamo.consultar_todo(dynamo.tabla(), "TENANT#CLIMALIMA", "PARTE#")
    assert len(partes_guardados) == 1


def test_visita_que_no_esta_en_atencion_es_409(aws):
    aws.return_value = {**VISITA, "estado": "PROGRAMADA"}
    r = partes.crear(peticion(TECNICO, ruta={"visita_id": "VIS-1"}, headers={"Authorization": "Bearer t"}), None)
    assert r["statusCode"] == 409 and cuerpo(r)["error"]["codigo"] == "VISITA_NO_EN_ATENCION"


def test_visita_ajena_responde_lo_que_dice_agenda(aws):
    aws.side_effect = ApiError(404, "NO_ENCONTRADO", "Visita no encontrado")
    r = partes.crear(peticion(OTRO_TECNICO, ruta={"visita_id": "VIS-1"}, headers={"Authorization": "Bearer t"}), None)
    assert r["statusCode"] == 404


def test_coordinador_no_registra_partes():
    r = partes.crear(peticion(ctx(), ruta={"visita_id": "VIS-1"}), None)
    assert r["statusCode"] == 403


# ---- Editar
def test_editar_guarda_solo_lo_enviado():
    parte = nuevo_parte()
    r = cuerpo(editar(parte, diagnostico="Falla", tareas=[" Limpieza ", "  "]))
    assert r["diagnostico"] == "Falla" and r["tareas"] == ["Limpieza"] and r["version"] == 2
    r = cuerpo(editar(r, materiales=["Filtro"]))
    assert r["diagnostico"] == "Falla" and r["materiales"] == ["Filtro"]


def test_editar_con_version_vieja_es_409():
    parte = nuevo_parte()
    editar(parte, diagnostico="uno")
    r = editar(parte, diagnostico="dos")
    assert r["statusCode"] == 409 and cuerpo(r)["error"]["codigo"] == "VERSION_DESACTUALIZADA"


@pytest.mark.parametrize("cambios", [
    {"resultado": "OTRO"}, {"tareas": "no es lista"}, {"tareas": [1]}, {"tareas": ["x"] * 31},
    {"diagnostico": "x" * 2001}, {"tareas": ["x" * 301]},
])
def test_editar_con_datos_invalidos_es_400(cambios):
    assert editar(nuevo_parte(), **cambios)["statusCode"] == 400


def test_editar_sin_version_es_400():
    parte = nuevo_parte()
    r = partes.editar(peticion(TECNICO, {"diagnostico": "x"}, ruta={"parte_id": parte["parte_id"]}), None)
    assert r["statusCode"] == 400


def test_otro_tecnico_no_ve_ni_edita():
    parte = nuevo_parte()
    assert editar(parte, OTRO_TECNICO, diagnostico="x")["statusCode"] == 404
    assert partes.detalle(peticion(OTRO_TECNICO, ruta={"parte_id": parte["parte_id"]}), None)["statusCode"] == 404
    assert partes.de_visita(peticion(OTRO_TECNICO, ruta={"visita_id": "VIS-1"}), None)["statusCode"] == 404


def test_otro_tenant_no_encuentra_el_parte():
    parte = nuevo_parte()
    r = partes.detalle(peticion(ctx(tenant="FRIOSUR"), ruta={"parte_id": parte["parte_id"]}), None)
    assert r["statusCode"] == 404


# ---- Finalizar
def test_finalizar_deja_el_evento_listo_y_lo_publica():
    parte = completo()
    with mock.patch.object(eventos, "publicar") as publicar:
        r = finalizar(parte)
    assert r["statusCode"] == 200
    final = cuerpo(r)
    assert final["estado"] == "FINALIZADO" and final["finalizado_en"]
    evento = publicar.call_args[0][0]
    assert evento["event_type"] == "ParteFinalizado" and evento["aggregate_id"] == parte["parte_id"]
    assert evento["data"]["resultado"] == "RESUELTO" and evento["data"]["visita_id"] == "VIS-1"
    assert outbox() == []


def test_finalizar_dos_veces_publica_una_sola_vez():
    parte = completo()
    with mock.patch.object(eventos, "publicar") as publicar:
        primero = cuerpo(finalizar(parte))
        segundo = finalizar(parte)
    assert segundo["statusCode"] == 200 and cuerpo(segundo)["finalizado_en"] == primero["finalizado_en"]
    assert publicar.call_count == 1


def test_si_publicar_falla_finaliza_igual_y_queda_pendiente():
    parte = completo()
    with mock.patch.object(eventos, "publicar", side_effect=RuntimeError("SNS caído")):
        r = finalizar(parte)
    assert r["statusCode"] == 200
    assert len(outbox()) == 1


def test_finalizar_incompleto_es_409():
    parte = nuevo_parte()
    r = finalizar(parte)
    assert r["statusCode"] == 409 and cuerpo(r)["error"]["codigo"] == "PARTE_INCOMPLETO"
    parte = cuerpo(editar(parte, diagnostico="x", resultado="RESUELTO"))
    assert cuerpo(finalizar(parte))["error"]["detalle"]["campo"] == "tareas"


def test_no_atendido_no_exige_tareas():
    parte = cuerpo(editar(nuevo_parte(), diagnostico="Cliente ausente", resultado="NO_ATENDIDO"))
    assert finalizar(parte)["statusCode"] == 200


def test_finalizar_con_version_vieja_es_409():
    parte = completo()
    vieja = {**parte, "version": parte["version"] - 1}
    assert finalizar(vieja)["statusCode"] == 409


def test_parte_finalizado_no_se_edita_ni_admite_otro_para_la_visita():
    parte = completo()
    finalizar(parte)
    assert editar(parte, diagnostico="otro")["statusCode"] == 409
    r = partes.crear(peticion(TECNICO, ruta={"visita_id": "VIS-1"}, headers={"Authorization": "Bearer t"}), None)
    assert r["statusCode"] == 409 and cuerpo(r)["error"]["codigo"] == "PARTE_YA_FINALIZADO"


def test_coordinador_consulta_pero_no_finaliza():
    parte = completo()
    assert finalizar(parte, ctx())["statusCode"] == 403
    assert partes.detalle(peticion(ctx(), ruta={"parte_id": parte["parte_id"]}), None)["statusCode"] == 200


# ---- Consultas
def test_partes_de_una_orden_y_aislamiento():
    parte = nuevo_parte()
    r = cuerpo(partes.listar(peticion(ctx(), query={"orden_id": "OT-1"}), None))
    assert [p["parte_id"] for p in r["items"]] == [parte["parte_id"]]
    r = cuerpo(partes.listar(peticion(ctx(tenant="FRIOSUR"), query={"orden_id": "OT-1"}), None))
    assert r["items"] == []


def test_tecnico_no_lista_por_orden():
    assert partes.listar(peticion(TECNICO, query={"orden_id": "OT-1"}), None)["statusCode"] == 403


def test_listar_exige_orden():
    assert partes.listar(peticion(ctx()), None)["statusCode"] == 400


def test_parte_de_visita_sin_parte_es_404():
    assert partes.de_visita(peticion(TECNICO, ruta={"visita_id": "VIS-2"}), None)["statusCode"] == 404


# ---- Evidencias
def test_firma_limita_tamano_tipo_y_clave():
    parte = nuevo_parte()
    r = solicitar(parte)
    assert r["statusCode"] == 201
    firma = cuerpo(r)
    politica = json.loads(base64.b64decode(firma["fields"]["policy"]))
    assert ["content-length-range", 1, 5 * 1024 * 1024] in politica["conditions"]
    assert {"Content-Type": "image/jpeg"} in politica["conditions"]
    clave = firma["fields"]["key"]
    assert clave == f"tenants/CLIMALIMA/ordenes/OT-1/visitas/VIS-1/{firma['evidencia_id']}.jpg"
    assert evidencia_estado(firma["evidencia_id"]) == "PENDIENTE"


@pytest.mark.parametrize("tipo", ["application/pdf", "image/svg+xml", "", None])
def test_tipo_no_permitido_es_400(tipo):
    assert solicitar(nuevo_parte(), tipo)["statusCode"] == 400


def test_parte_finalizado_no_admite_archivos():
    parte = completo()
    finalizar(parte)
    assert solicitar(parte)["statusCode"] == 409


def test_limite_de_solicitudes_por_parte():
    parte = nuevo_parte()
    for _ in range(dom.MAX_SOLICITUDES):
        assert solicitar(parte)["statusCode"] == 201
    assert solicitar(parte)["statusCode"] == 409


def test_otro_tecnico_no_solicita():
    assert solicitar(nuevo_parte(), autorizador=OTRO_TECNICO)["statusCode"] == 404


def test_notificacion_confirma_y_el_detalle_entrega_url():
    parte = nuevo_parte()
    firma = cuerpo(solicitar(parte))
    clave = firma["fields"]["key"]
    detalle = cuerpo(partes.detalle(peticion(TECNICO, ruta={"parte_id": parte["parte_id"]}), None))
    assert detalle["evidencias"][0]["estado"] == "PENDIENTE" and "url" not in detalle["evidencias"][0]

    subir(clave)
    notificar(clave)
    assert evidencia_estado(firma["evidencia_id"]) == "CONFIRMADA"
    detalle = cuerpo(partes.detalle(peticion(TECNICO, ruta={"parte_id": parte["parte_id"]}), None))
    assert "X-Amz-Signature" in detalle["evidencias"][0]["url"]
    assert "object_key" not in detalle["evidencias"][0]


def test_notificacion_decodifica_la_clave():
    parte = nuevo_parte()
    firma = cuerpo(solicitar(parte))
    clave = firma["fields"]["key"]
    subir(clave)
    notificar(clave.replace("/", "%2F", 1))
    assert evidencia_estado(firma["evidencia_id"]) == "CONFIRMADA"


def test_notificacion_rechaza_tipo_inesperado_sin_url():
    parte = nuevo_parte()
    firma = cuerpo(solicitar(parte))
    subir(firma["fields"]["key"], tipo="text/html")
    notificar(firma["fields"]["key"])
    assert evidencia_estado(firma["evidencia_id"]) == "RECHAZADA"
    detalle = cuerpo(partes.detalle(peticion(TECNICO, ruta={"parte_id": parte["parte_id"]}), None))
    assert "url" not in detalle["evidencias"][0]


def test_notificacion_repetida_no_cambia_nada():
    firma = cuerpo(solicitar(nuevo_parte()))
    subir(firma["fields"]["key"])
    notificar(firma["fields"]["key"])
    subir(firma["fields"]["key"], tipo="text/html")
    notificar(firma["fields"]["key"])
    assert evidencia_estado(firma["evidencia_id"]) == "CONFIRMADA"


@pytest.mark.parametrize("clave", ["otra/ruta.jpg", "tenants/CLIMALIMA/ordenes/OT-1/visitas/VIS-1/EVI-X.jpg"])
def test_notificacion_de_clave_desconocida_no_falla(clave, capsys):
    notificar(clave)
    assert '"tipo": "ERROR"' in capsys.readouterr().out


def test_clave_de_otro_tenant_no_confirma_la_evidencia():
    firma = cuerpo(solicitar(nuevo_parte()))
    falsa = firma["fields"]["key"].replace("CLIMALIMA", "FRIOSUR")
    subir(falsa)
    notificar(falsa)
    assert evidencia_estado(firma["evidencia_id"]) == "PENDIENTE"


def test_confirmar_como_respaldo():
    firma = cuerpo(solicitar(nuevo_parte()))
    evento = peticion(TECNICO, ruta={"evidencia_id": firma["evidencia_id"]})
    r = evidencias.confirmar(evento, None)
    assert r["statusCode"] == 409 and cuerpo(r)["error"]["codigo"] == "ARCHIVO_NO_ENCONTRADO"
    subir(firma["fields"]["key"])
    assert cuerpo(evidencias.confirmar(evento, None))["estado"] == "CONFIRMADA"
    assert cuerpo(evidencias.confirmar(evento, None))["estado"] == "CONFIRMADA"


def test_confirmar_ajena_es_404():
    firma = cuerpo(solicitar(nuevo_parte()))
    subir(firma["fields"]["key"])
    ruta = {"evidencia_id": firma["evidencia_id"]}
    assert evidencias.confirmar(peticion(OTRO_TECNICO, ruta=ruta), None)["statusCode"] == 404
    assert evidencias.confirmar(peticion(ctx(tenant="FRIOSUR", rol="ADMIN"), ruta=ruta), None)["statusCode"] == 404


def test_detalle_de_finalizado_oculta_pendientes_abandonadas():
    parte = completo()
    firma = cuerpo(solicitar(parte))
    subir(firma["fields"]["key"])
    notificar(firma["fields"]["key"])
    solicitar(parte)  # Esta nunca se sube.
    finalizar(parte)
    detalle = cuerpo(partes.detalle(peticion(TECNICO, ruta={"parte_id": parte["parte_id"]}), None))
    assert [e["evidencia_id"] for e in detalle["evidencias"]] == [firma["evidencia_id"]]


@pytest.mark.parametrize("tamano,tipo,esperado", [
    (1, "image/png", True), (dom.MAX_BYTES, "image/jpeg", True), (0, "image/png", False),
    (dom.MAX_BYTES + 1, "image/png", False), (10, "text/html", False), (10, None, False),
])
def test_archivo_valido(tamano, tipo, esperado):
    assert dom.archivo_valido(tamano, tipo) is esperado
