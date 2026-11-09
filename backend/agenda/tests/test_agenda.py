import json
from unittest import mock

import pytest
from moto import mock_aws

from apoyo_pruebas import crear_tabla, ctx, cuerpo, entorno_aws, peticion
from trazora_common import dynamo, eventos, interno
from trazora_common.http import ApiError

from dominio import agenda as dom
from handlers import consumidor, control, disponibilidad, visitas

ORDEN = {"estado": "ABIERTA", "tipo_servicio": "REPARACION", "descripcion": "No enfría", "cliente_nombre": "López", "direccion": "Av. 1", "distrito": "Miraflores"}
TECNICO = {"nombre": "Carlos", "activo": True, "especialidades": ["REPARACION"]}
JORNADA = {"jornadas": [{"intervalos": [{"inicio": "08:00", "fin": "12:00"}, {"inicio": "13:00", "fin": "17:00"}]}], "ausencias": []}
# 10:00 de Lima = 15:00 UTC
I10, I11, I12 = "2026-11-10T15:00:00Z", "2026-11-10T16:00:00Z", "2026-11-10T17:00:00Z"


def llamar_falso(base, ruta, token, **kw):
    if "/ordenes/" in ruta:
        return dict(ORDEN)
    if "jornadas" in ruta:
        return JORNADA
    if "disponibles" in ruta:
        return {"items": [
            {"tecnico_id": "T1", "nombre": "Carlos", "especialidades": ["REPARACION"], **JORNADA["jornadas"][0]},
            {"tecnico_id": "T2", "nombre": "Ana", "especialidades": ["REPARACION"], **JORNADA["jornadas"][0]},
        ]}
    if "/analitica/" in ruta:
        return {"items": [
            {"tecnico_id": "T1", "carga_dia": 1, "tasa_resolucion": 0.9},
            {"tecnico_id": "T2", "carga_dia": 3, "tasa_resolucion": 0.99},
        ]}
    return dict(TECNICO)


@pytest.fixture(autouse=True)
def aws(monkeypatch):
    entorno_aws(monkeypatch, "t_agenda")
    monkeypatch.setenv("ORDENES_URL", "https://o")
    monkeypatch.setenv("TECNICOS_URL", "https://t")
    monkeypatch.setenv("ANALITICA_URL", "https://a")
    with mock_aws():
        dynamo.reiniciar()
        eventos.reiniciar()
        crear_tabla("t_agenda", "GSI1", "GSI2", "GSI3")
        import boto3
        monkeypatch.setenv("TOPIC_ARN", boto3.client("sns").create_topic(Name="e")["TopicArn"])
        with mock.patch.object(interno, "llamar", side_effect=llamar_falso) as m:
            yield m
        dynamo.reiniciar()
        eventos.reiniciar()


def programar(inicio=I10, fin=I11, tecnico="T1", orden="OT-1", tenant="CLIMALIMA", headers=None):
    return visitas.crear(peticion(ctx(tenant), {"orden_id": orden, "tecnico_id": tecnico, "inicio": inicio, "fin": fin}, headers=headers), None)


def nueva(**kw):
    r = programar(**kw)
    assert r["statusCode"] == 201, r["body"]
    return cuerpo(r)


def control_de(orden="OT-1", tenant="CLIMALIMA"):
    return dynamo.tabla().get_item(Key={"PK": f"TENANT#{tenant}", "SK": f"CONTROL_ORDEN#{orden}"})["Item"]


def bloques_guardados(tenant="CLIMALIMA"):
    return [b["SK"] for b in dynamo.consultar_todo(dynamo.tabla(), f"TENANT#{tenant}", "BLOQUE#")]


def tecnico_ctx(tecnico="T1"):
    return ctx(rol="TECNICO", usuario="U-T", tecnico=tecnico)


# ---- Dominio
def test_bloques_excluyen_el_extremo_final():
    i, f = dom.validar_horario(I10, I11)
    assert [dom.hora_lima(b) for b in dom.bloques(i, f)] == ["10:00", "10:30"]


@pytest.mark.parametrize("inicio,fin", [
    ("2026-11-10T15:15:00Z", I11), (I11, I10), (I10, I10), ("2026-11-10T15:00:00Z", "2026-11-10T19:30:00Z"),
    ("x", I11), ("2026-11-11T04:30:00Z", "2026-11-11T05:30:00Z"),  # Cruza la medianoche de Lima
])
def test_horarios_invalidos(inicio, fin):
    with pytest.raises(ApiError):
        dom.validar_horario(inicio, fin)


def test_cuatro_horas_es_el_maximo_permitido():
    dom.validar_horario("2026-11-10T13:00:00Z", "2026-11-10T17:00:00Z")


def test_jornada():
    i, f = dom.validar_horario(I10, I11)
    intervalos = JORNADA["jornadas"][0]["intervalos"]
    assert dom.dentro_de_jornada(intervalos, i, f)
    i2, f2 = dom.validar_horario("2026-11-10T16:30:00Z", "2026-11-10T17:30:00Z")  # 11:30-12:30 cruza el almuerzo
    assert not dom.dentro_de_jornada(intervalos, i2, f2)


def test_horarios_libres_respeta_ocupados_y_duracion():
    intervalos = [{"inicio": "08:00", "fin": "10:00"}]
    assert dom.horarios_libres(intervalos, set(), 60) == ["08:00", "08:30", "09:00"]
    assert dom.horarios_libres(intervalos, {"08:30"}, 60) == ["09:00"]
    assert dom.horarios_libres(intervalos, {"08:30"}, 30) == ["08:00", "09:00", "09:30"]


def test_orden_de_candidatos_y_justificacion():
    c = [{"tecnico_id": "A", "nombre": "Zoe"}, {"tecnico_id": "B", "nombre": "Ana"}, {"tecnico_id": "C", "nombre": "Bea"}]
    m = {"A": {"carga_dia": 1, "tasa_resolucion": 0.9}, "B": {"carga_dia": 3, "tasa_resolucion": 1}, "C": {"carga_dia": 1, "tasa_resolucion": 0.95}}
    r = dom.ordenar_candidatos(c, m)
    assert [x["tecnico_id"] for x in r] == ["C", "A", "B"]
    assert r[0]["justificacion"] == "1 visita ese día, 95 % de resolución sin revisita"


def test_tecnico_sin_historial_lo_dice_en_vez_de_mostrar_cero():
    candidatos = [{"tecnico_id": "A", "nombre": "Ana", "horarios": []}]
    r = dom.ordenar_candidatos(candidatos, {"A": {"tecnico_id": "A", "carga_dia": 2}})
    assert r[0]["justificacion"] == "2 visitas ese día, sin historial"


def test_sin_metricas_orden_alfabetico_sin_justificacion():
    r = dom.ordenar_candidatos([{"tecnico_id": "A", "nombre": "Zoe"}, {"tecnico_id": "B", "nombre": "Ana"}], {})
    assert [x["nombre"] for x in r] == ["Ana", "Zoe"] and "justificacion" not in r[0]


# ---- Programar
def test_programar_guarda_todo_junto():
    v = nueva()
    assert v["estado"] == "PROGRAMADA" and v["numero_visita_orden"] == 1 and v["fecha"] == "2026-11-10"
    assert v["cliente_nombre"] == "López" and v["tecnico_nombre"] == "Carlos"
    assert not {"PK", "SK", "GSI1PK"} & v.keys()
    assert len(bloques_guardados()) == 2
    c = control_de()
    assert c["visitas_activas"] == 1 and c["visitas_total"] == 1


def test_horario_ocupado_no_deja_rastros():
    nueva()
    r = programar(inicio="2026-11-10T15:30:00Z", fin="2026-11-10T16:30:00Z", orden="OT-2")
    assert r["statusCode"] == 409 and cuerpo(r)["error"]["codigo"] == "HORARIO_OCUPADO"
    assert len(bloques_guardados()) == 2
    assert control_de("OT-2")["visitas_activas"] == 0
    assert len(cuerpo(visitas.listar(peticion(ctx(), query={"fecha": "2026-11-10"}), None))["items"]) == 1


def test_contiguas_y_otro_tecnico_si_pueden():
    nueva()
    nueva(inicio=I11, fin=I12, orden="OT-2")
    nueva(tecnico="T2", orden="OT-3")


def test_mismo_horario_en_otra_empresa_no_choca():
    nueva()
    nueva(tenant="FRIOSUR")


def test_numero_de_visita_aumenta():
    nueva()
    v2 = nueva(inicio=I11, fin=I12)
    assert v2["numero_visita_orden"] == 2 and control_de()["visitas_activas"] == 2


def test_creacion_repetida_no_duplica():
    cab = {"Idempotency-Key": "k1"}
    a = cuerpo(programar(headers=cab))
    b = cuerpo(programar(headers=cab))
    assert a["visita_id"] == b["visita_id"]
    assert control_de()["visitas_total"] == 1


@pytest.mark.parametrize("cambio,codigo", [
    ({"activo": False}, "TECNICO_INACTIVO"),
    ({"especialidades": ["INSTALACION"]}, "ESPECIALIDAD_INCOMPATIBLE"),
])
def test_tecnico_invalido(aws, cambio, codigo):
    def falso(base, ruta, token, **kw):
        return {**TECNICO, **cambio} if "/tecnicos/" in ruta and "jornadas" not in ruta else llamar_falso(base, ruta, token)
    aws.side_effect = falso
    assert cuerpo(programar())["error"]["codigo"] == codigo


def test_fuera_de_jornada_y_ausencia(aws):
    assert cuerpo(programar(inicio="2026-11-10T17:00:00Z", fin="2026-11-10T18:00:00Z"))["error"]["codigo"] == "FUERA_DE_JORNADA"

    def ausente(base, ruta, token, **kw):
        return {**JORNADA, "ausencias": [{"fecha": "2026-11-10"}]} if "jornadas" in ruta else llamar_falso(base, ruta, token)
    aws.side_effect = ausente
    assert cuerpo(programar())["error"]["codigo"] == "TECNICO_AUSENTE"


def test_orden_cerrada_no_admite(aws):
    aws.side_effect = lambda b, r, t, **k: {**ORDEN, "estado": "CERRADA"} if "/ordenes/" in r else llamar_falso(b, r, t)
    assert cuerpo(programar())["error"]["codigo"] == "ORDEN_NO_ADMITE_VISITAS"


def test_orden_de_otra_empresa_404(aws):
    aws.side_effect = ApiError(404, "NO_ENCONTRADO", "Orden no encontrada")
    assert programar()["statusCode"] == 404


def test_tecnico_no_programa():
    r = visitas.crear(peticion(tecnico_ctx(), {"orden_id": "O", "tecnico_id": "T1", "inicio": I10, "fin": I11}), None)
    assert r["statusCode"] == 403


def test_evento_publicado_borra_outbox():
    nueva()
    assert dynamo.consultar_todo(dynamo.tabla(), "TENANT#CLIMALIMA", "OUTBOX#") == []


def test_fallo_al_publicar_conserva_visita_y_evento(monkeypatch):
    monkeypatch.setenv("TOPIC_ARN", "arn:aws:sns:us-east-1:123456789012:no-existe")
    assert programar()["statusCode"] == 201
    pendientes = dynamo.consultar_todo(dynamo.tabla(), "TENANT#CLIMALIMA", "OUTBOX#")
    assert pendientes[0]["evento"]["event_type"] == "VisitaProgramada"


# ---- Reprogramar
def reprogramar(v, inicio, fin, version=None, **extra):
    return visitas.reprogramar(peticion(ctx(), {"inicio": inicio, "fin": fin, "version": version or v["version"], **extra}, {"visita_id": v["visita_id"]}), None)


def test_reprogramar_conserva_bloques_compartidos():
    v = nueva()  # 10:00-11:00
    r = reprogramar(v, "2026-11-10T15:30:00Z", "2026-11-10T16:30:00Z")  # 10:30-11:30
    assert r["statusCode"] == 200, r["body"]
    horas = sorted(dynamo.tabla().get_item(Key={"PK": "TENANT#CLIMALIMA", "SK": s})["Item"]["hora"] for s in bloques_guardados())
    assert horas == ["10:30", "11:00"]
    assert cuerpo(r)["version"] == 2


def test_reprogramar_fallida_conserva_lo_anterior():
    v = nueva()
    nueva(inicio=I11, fin=I12, orden="OT-2")
    r = reprogramar(v, "2026-11-10T15:30:00Z", "2026-11-10T16:30:00Z")
    assert r["statusCode"] == 409 and cuerpo(r)["error"]["codigo"] == "HORARIO_OCUPADO"
    guardada = cuerpo(visitas.detalle(peticion(ctx(), ruta={"visita_id": v["visita_id"]}), None))
    assert guardada["inicio"] == I10 and guardada["version"] == 1
    assert len(bloques_guardados()) == 4


def test_reprogramar_con_otro_tecnico_mueve_indices():
    v = nueva()
    assert reprogramar(v, I10, I11, tecnico_id="T2")["statusCode"] == 200
    assert cuerpo(visitas.listar(peticion(ctx(), query={"tecnico_id": "T1"}), None))["items"] == []
    assert len(cuerpo(visitas.listar(peticion(ctx(), query={"tecnico_id": "T2"}), None))["items"]) == 1


def test_reprogramar_version_antigua():
    v = nueva()
    reprogramar(v, I11, I12)
    assert cuerpo(reprogramar(v, I10, I11))["error"]["codigo"] == "VERSION_DESACTUALIZADA"


def test_visita_en_atencion_no_se_reprograma_ni_cancela():
    v = nueva()
    visitas.iniciar(peticion(tecnico_ctx(), ruta={"visita_id": v["visita_id"]}), None)
    assert cuerpo(reprogramar(v, I11, I12, version=2))["error"]["codigo"] == "ESTADO_NO_PERMITE"
    assert visitas.cancelar(peticion(ctx(), ruta={"visita_id": v["visita_id"]}), None)["statusCode"] == 409


# ---- Cancelar
def test_cancelar_libera_y_repetir_no_resta_dos_veces():
    v = nueva()
    ruta = {"visita_id": v["visita_id"]}
    assert cuerpo(visitas.cancelar(peticion(ctx(), ruta=ruta), None))["estado"] == "CANCELADA"
    assert bloques_guardados() == [] and control_de()["visitas_activas"] == 0
    assert visitas.cancelar(peticion(ctx(), ruta=ruta), None)["statusCode"] == 200
    assert control_de()["visitas_activas"] == 0
    nueva()  # El horario quedó libre


# ---- Iniciar y acceso
def test_iniciar_solo_el_asignado():
    v = nueva()
    ruta = {"visita_id": v["visita_id"]}
    assert visitas.iniciar(peticion(tecnico_ctx("T2"), ruta=ruta), None)["statusCode"] == 404
    assert visitas.iniciar(peticion(ctx(), ruta=ruta), None)["statusCode"] == 403
    r = visitas.iniciar(peticion(tecnico_ctx(), ruta=ruta), None)
    assert cuerpo(r)["estado"] == "EN_ATENCION" and cuerpo(r)["iniciada_en"]
    assert visitas.iniciar(peticion(tecnico_ctx(), ruta=ruta), None)["statusCode"] == 200


def test_tecnico_solo_ve_sus_visitas_aunque_pida_otras():
    nueva()
    v2 = nueva(tecnico="T2", orden="OT-2")
    ids = [x["visita_id"] for x in cuerpo(visitas.listar(peticion(tecnico_ctx("T2"), query={"tecnico_id": "T1"}), None))["items"]]
    assert ids == [v2["visita_id"]]
    assert visitas.detalle(peticion(tecnico_ctx("T1"), ruta={"visita_id": v2["visita_id"]}), None)["statusCode"] == 404


def test_otra_empresa_no_ve_ni_actua():
    v = nueva()
    ruta = {"visita_id": v["visita_id"]}
    assert visitas.detalle(peticion(ctx("FRIOSUR"), ruta=ruta), None)["statusCode"] == 404
    assert visitas.cancelar(peticion(ctx("FRIOSUR"), ruta=ruta), None)["statusCode"] == 404
    assert cuerpo(visitas.listar(peticion(ctx("FRIOSUR"), query={"fecha": "2026-11-10"}), None))["items"] == []


def test_listar_requiere_filtro():
    assert visitas.listar(peticion(ctx()), None)["statusCode"] == 400


def test_listar_por_fecha_de_un_tecnico():
    nueva()
    nueva(inicio="2026-11-11T15:00:00Z", fin="2026-11-11T16:00:00Z", orden="OT-2")
    r = cuerpo(visitas.listar(peticion(ctx(), query={"tecnico_id": "T1", "fecha": "2026-11-11"}), None))
    assert [v["fecha"] for v in r["items"]] == ["2026-11-11"]
    r = cuerpo(visitas.listar(peticion(ctx(), query={"tecnico_id": "T1", "desde": "2026-11-11"}), None))
    assert len(r["items"]) == 1


def test_sin_pasados_solo_ofrece_desde_ahora():
    from datetime import datetime, timezone
    ahora = datetime(2026, 11, 9, 14, 40, tzinfo=timezone.utc)  # 09:40 en Lima
    horas = ["08:00", "09:30", "10:00", "10:30", "13:00"]
    assert dom.sin_pasados("2026-11-09", horas, ahora) == ["10:00", "10:30", "13:00"]
    assert dom.sin_pasados("2026-11-10", horas, ahora) == horas
    assert dom.sin_pasados("2026-11-08", horas, ahora) == []
    exacto = datetime(2026, 11, 9, 15, 0, tzinfo=timezone.utc)  # 10:00 en Lima
    assert dom.sin_pasados("2026-11-09", horas, exacto)[0] == "10:00"


def test_disponibilidad_hoy_no_propone_horas_pasadas(monkeypatch):
    from datetime import datetime, timezone
    monkeypatch.setattr(disponibilidad, "ahora_utc", lambda: datetime(2026, 11, 10, 17, 10, tzinfo=timezone.utc))  # 12:10 Lima
    r = cuerpo(disponibilidad.consultar(peticion(ctx(), query={"fecha": "2026-11-10", "duracion_min": "60"}), None))
    for item in r["items"]:
        assert all(h >= "12:10" for h in item["horarios"])


# ---- Disponibilidad
def test_disponibilidad_quita_ocupados():
    nueva()
    r = cuerpo(disponibilidad.consultar(peticion(ctx(), query={"fecha": "2026-11-10", "duracion_min": "60"}), None))
    carlos = next(i for i in r["items"] if i["tecnico_id"] == "T1")
    assert "10:00" not in carlos["horarios"] and "09:30" not in carlos["horarios"] and "11:00" in carlos["horarios"]
    ana = next(i for i in r["items"] if i["tecnico_id"] == "T2")
    assert "10:00" in ana["horarios"]


def test_sugerencia_ordena_y_justifica():
    r = cuerpo(disponibilidad.consultar(peticion(ctx(), query={"fecha": "2026-11-10", "sugerir": "true"}), None))
    assert r["items"][0]["tecnico_id"] == "T1" and "justificacion" in r["items"][0]


def test_analitica_caida_sigue_funcionando(aws):
    def falso(base, ruta, token, **kw):
        if "/analitica/" in ruta:
            raise ApiError(503, "SERVICIO_NO_DISPONIBLE", "x")
        return llamar_falso(base, ruta, token)
    aws.side_effect = falso
    r = disponibilidad.consultar(peticion(ctx(), query={"fecha": "2026-11-10", "sugerir": "true"}), None)
    assert r["statusCode"] == 200
    assert [i["nombre"] for i in cuerpo(r)["items"]] == ["Ana", "Carlos"]
    assert "justificacion" not in cuerpo(r)["items"][0]


def test_sin_url_de_analitica_sigue_funcionando(monkeypatch):
    monkeypatch.setenv("ANALITICA_URL", "")
    assert disponibilidad.consultar(peticion(ctx(), query={"fecha": "2026-11-10", "sugerir": "true"}), None)["statusCode"] == 200


def test_tecnico_no_consulta_disponibilidad():
    assert disponibilidad.consultar(peticion(tecnico_ctx(), query={"fecha": "2026-11-10"}), None)["statusCode"] == 403


# ---- Bloqueo
def bloquear(orden="OT-1", op="OP-1"):
    return control.bloquear({"tenant_id": "CLIMALIMA", "orden_id": orden, "operacion_id": op}, None)


def test_bloqueo_rechazado_con_visitas_activas():
    nueva()
    assert bloquear() == {"bloqueada": False, "visitas_activas": 1, "visitas_canceladas": 0}
    assert control_de()["acepta_programaciones"] is True


def test_bloqueo_impide_nuevas_visitas_y_es_repetible():
    assert bloquear("OT-9")["bloqueada"] is True  # Orden sin visitas: crea el control
    assert bloquear("OT-9")["bloqueada"] is True
    r = programar(orden="OT-9")
    assert r["statusCode"] == 409 and cuerpo(r)["error"]["codigo"] == "ORDEN_NO_ADMITE_VISITAS"


def test_bloqueo_tras_cancelar_la_unica_visita():
    v = nueva()
    visitas.cancelar(peticion(ctx(), ruta={"visita_id": v["visita_id"]}), None)
    assert bloquear()["bloqueada"] is True


def test_otra_operacion_no_reutiliza_bloqueo_ajeno():
    bloquear("OT-9", "OP-1")
    assert bloquear("OT-9", "OP-2")["bloqueada"] is False


# ---- Consumidor de ParteFinalizado
def _parte_finalizado(visita, resultado="RESUELTO", event_id=None, finalizado="2026-11-10T15:45:00Z"):
    evento = eventos.crear_evento(
        "ParteFinalizado", "CLIMALIMA", "PARTE", "PAR-1", 2,
        {"parte_id": "PAR-1", "visita_id": visita["visita_id"], "orden_id": visita["orden_id"],
         "tecnico_id": visita["tecnico_id"], "resultado": resultado, "finalizado_en": finalizado},
        event_id=event_id,
    )
    return {"Records": [{"body": json.dumps({"Message": json.dumps(evento)})}]}


def _en_atencion():
    visita = nueva()
    iniciada = cuerpo(visitas.iniciar(peticion(ctx(rol="TECNICO", tecnico="T1"), ruta={"visita_id": visita["visita_id"]}), None))
    assert iniciada["estado"] == "EN_ATENCION"
    return iniciada


def test_parte_finalizado_termina_la_visita_y_anuncia_el_resultado():
    visita = _en_atencion()
    with mock.patch.object(eventos, "publicar") as publicar:
        consumidor.lambda_handler(_parte_finalizado(visita), None)
    actual = cuerpo(visitas.detalle(peticion(ctx(), ruta={"visita_id": visita["visita_id"]}), None))
    assert actual["estado"] == "FINALIZADA" and actual["resultado"] == "RESUELTO"
    assert control_de()["visitas_activas"] == 0
    evento = publicar.call_args[0][0]
    assert evento["event_type"] == "VisitaCompletada"
    assert evento["aggregate_version"] == visita["version"] + 1
    assert evento["data"]["resultado"] == "RESUELTO" and evento["data"]["numero_visita_orden"] == 1


def test_parte_repetido_no_resta_dos_veces():
    visita = _en_atencion()
    mensaje = _parte_finalizado(visita, event_id="E1")
    with mock.patch.object(eventos, "publicar") as publicar:
        consumidor.lambda_handler(mensaje, None)
        consumidor.lambda_handler(mensaje, None)
    assert publicar.call_count == 1
    assert control_de()["visitas_activas"] == 0


def test_repetido_que_coincide_en_la_transaccion_se_absorbe():
    """Ambos leyeron EN_ATENCION: el segundo se detiene por INBOX, no por el estado."""
    visita = _en_atencion()
    mensaje = _parte_finalizado(visita, event_id="E1")
    dynamo.tabla().put_item(Item={"PK": "TENANT#CLIMALIMA", "SK": "INBOX#E1"})
    consumidor.lambda_handler(mensaje, None)
    actual = cuerpo(visitas.detalle(peticion(ctx(), ruta={"visita_id": visita["visita_id"]}), None))
    assert actual["estado"] == "EN_ATENCION"
    assert control_de()["visitas_activas"] == 1


def test_parte_de_visita_cancelada_registra_el_conflicto_sin_reintentar(capsys):
    visita = nueva()
    visitas.cancelar(peticion(ctx(), ruta={"visita_id": visita["visita_id"]}), None)
    consumidor.lambda_handler(_parte_finalizado(visita), None)
    assert "conflicto_parte_visita" in capsys.readouterr().out
    assert control_de()["visitas_activas"] == 0


def test_mensaje_invalido_falla_para_terminar_en_la_dlq():
    with pytest.raises(Exception):
        consumidor.lambda_handler({"Records": [{"body": "no es json"}]}, None)
    with pytest.raises(ValueError):
        consumidor.lambda_handler(_parte_finalizado({"visita_id": "NO", "orden_id": "O", "tecnico_id": "T"}), None)


def test_si_publicar_falla_el_evento_queda_para_el_barrido():
    visita = _en_atencion()
    with mock.patch.object(eventos, "publicar", side_effect=RuntimeError("SNS caído")):
        consumidor.lambda_handler(_parte_finalizado(visita), None)
    pendientes = dynamo.consultar_todo(dynamo.tabla(), "TENANT#CLIMALIMA", eventos.PREFIJO_OUTBOX)
    assert [p["evento"]["event_type"] for p in pendientes] == ["VisitaCompletada"]



# ---- Cancelación en cascada
def test_cancelar_orden_cancela_sus_visitas_programadas_y_bloquea():
    a = nueva(inicio=I10, fin=I11)
    nueva(inicio=I11, fin=I12)
    r = control.bloquear({"tenant_id": "CLIMALIMA", "orden_id": "OT-1", "operacion_id": "OP", "cancelar_programadas": True}, None)
    assert r == {"bloqueada": True, "visitas_activas": 0, "visitas_canceladas": 2}
    assert bloques_guardados() == []
    assert cuerpo(visitas.detalle(peticion(ctx(), ruta={"visita_id": a["visita_id"]}), None))["estado"] == "CANCELADA"


def test_cascada_no_toca_una_visita_en_atencion():
    en_curso = nueva(inicio=I10, fin=I11)
    visitas.iniciar(peticion(ctx(rol="TECNICO", tecnico="T1"), ruta={"visita_id": en_curso["visita_id"]}), None)
    nueva(inicio=I11, fin=I12)
    r = control.bloquear({"tenant_id": "CLIMALIMA", "orden_id": "OT-1", "operacion_id": "OP", "cancelar_programadas": True}, None)
    assert r == {"bloqueada": False, "visitas_activas": 1, "visitas_canceladas": 1}


# ---- Reasignación por ausencia
from dominio.agenda import elegir_reemplazo  # noqa: E402
from handlers import alertas, reasignacion  # noqa: E402

CANDIDATOS = [
    {"tecnico_id": "T2", "nombre": "Ana", "especialidades": ["REPARACION"], "intervalos": JORNADA["jornadas"][0]["intervalos"]},
    {"tecnico_id": "T3", "nombre": "Beto", "especialidades": ["REPARACION"], "intervalos": JORNADA["jornadas"][0]["intervalos"]},
    {"tecnico_id": "T4", "nombre": "Ciro", "especialidades": ["INSTALACION"], "intervalos": JORNADA["jornadas"][0]["intervalos"]},
]
VISITA_10 = {"inicio": I10, "fin": I11, "tipo_servicio": "REPARACION"}


def test_elegir_reemplazo_prefiere_menos_carga_y_respeta_especialidad_y_horario():
    metricas = {"T2": {"carga_dia": 3, "tasa_resolucion": 0.99}, "T3": {"carga_dia": 1, "tasa_resolucion": 0.8}}
    elegido, porque = elegir_reemplazo(VISITA_10, CANDIDATOS, metricas, {}, "T1")
    assert elegido["tecnico_id"] == "T3" and "1 visita ese día" in porque
    elegido, _ = elegir_reemplazo(VISITA_10, CANDIDATOS, metricas, {"T3": {"10:00"}}, "T1")
    assert elegido["tecnico_id"] == "T2"
    assert elegir_reemplazo(VISITA_10, CANDIDATOS, metricas, {"T2": {"10:00"}, "T3": {"10:30"}}, "T1") == (None, None)


def test_elegir_reemplazo_fuera_de_jornada_no_sirve():
    tarde = {**VISITA_10, "inicio": "2026-11-10T23:00:00Z", "fin": "2026-11-11T00:00:00Z"}  # 18:00 en Lima
    assert elegir_reemplazo(tarde, CANDIDATOS, {}, {}, "T1") == (None, None)


def _ausencia(tecnico="T1", fecha="2026-11-10", event_id=None):
    evento = eventos.crear_evento("TecnicoAusente", "CLIMALIMA", "TECNICO", tecnico, 1,
                                  {"tecnico_id": tecnico, "fecha": fecha, "motivo": "Enfermo"}, event_id=event_id)
    return {"Records": [{"body": json.dumps({"Message": json.dumps(evento)})}]}


@pytest.fixture
def invocaciones(monkeypatch):
    monkeypatch.setenv("TECNICOS_FN", "tecnicos-interno")
    monkeypatch.setenv("ANALITICA_FN", "analitica-interno")

    def invocar(nombre, carga):
        if nombre == "tecnicos-interno":
            return {"items": [c for c in CANDIDATOS if c["tecnico_id"] != carga.get("excluir")]}
        return {"items": [{"tecnico_id": "T2", "carga_dia": 0, "tasa_resolucion": 0.95}, {"tecnico_id": "T3", "carga_dia": 2, "tasa_resolucion": 0.9}]}

    with mock.patch.object(interno, "invocar", side_effect=invocar) as m:
        yield m


def _detalle(visita_id):
    return cuerpo(visitas.detalle(peticion(ctx(), ruta={"visita_id": visita_id}), None))


def test_ausencia_reasigna_al_mejor_y_mueve_los_bloques(invocaciones):
    v = nueva(inicio=I10, fin=I11)
    with mock.patch.object(eventos, "publicar") as publicar:
        r = consumidor.lambda_handler(_ausencia(), None)
    assert r == {"reasignadas": 1, "alertas": 0}
    actual = _detalle(v["visita_id"])
    assert actual["tecnico_id"] == "T2" and actual["tecnico_nombre"] == "Ana" and actual["reasignada_automaticamente"]
    assert {b.split("#")[2] for b in bloques_guardados()} == {"T2"}
    evento = publicar.call_args[0][0]
    assert evento["event_type"] == "VisitaReprogramada" and evento["data"]["automatica"] is True
    assert evento["data"]["tecnico_anterior"] == "T1"
    avisos = cuerpo(alertas.listar(peticion(ctx()), None))
    assert avisos["pendientes"] == [] and avisos["recientes"][0]["tipo"] == "REASIGNADA"
    assert "Ana" in avisos["recientes"][0]["detalle"]


def test_dos_visitas_a_la_misma_hora_no_van_al_mismo_reemplazo(invocaciones):
    nueva(inicio=I10, fin=I11, orden="OT-1")
    dynamo.tabla().put_item(Item={"PK": "TENANT#CLIMALIMA", "SK": "BLOQUE#2026-11-10#T9#x", "tecnico_id": "T9", "hora": "x"})
    with mock.patch.object(interno, "llamar", side_effect=llamar_falso):
        r2 = programar(inicio=I10, fin=I11, tecnico="T5", orden="OT-2")
    assert r2["statusCode"] == 201
    # T5 también se ausenta ese día: sus visitas compiten por los mismos reemplazos.
    consumidor.lambda_handler(_ausencia(), None)
    consumidor.lambda_handler(_ausencia(tecnico="T5"), None)
    tecnicos = sorted({b.split("#")[2] for b in bloques_guardados()} - {"T9"})
    assert tecnicos == ["T2", "T3"]


def test_sin_reemplazo_queda_alerta_y_al_reprogramar_desaparece(invocaciones):
    invocaciones.side_effect = lambda nombre, carga: {"items": []}
    v = nueva(inicio=I10, fin=I11)
    r = consumidor.lambda_handler(_ausencia(), None)
    assert r == {"reasignadas": 0, "alertas": 1}
    pendientes = cuerpo(alertas.listar(peticion(ctx()), None))["pendientes"]
    assert [a["visita_id"] for a in pendientes] == [v["visita_id"]]
    actual = _detalle(v["visita_id"])
    assert actual["requiere_reprogramacion"] is True and actual["estado"] == "PROGRAMADA"
    visitas.reprogramar(peticion(ctx(), {"inicio": I11, "fin": I12, "version": actual["version"]}, ruta={"visita_id": v["visita_id"]}), None)
    assert cuerpo(alertas.listar(peticion(ctx()), None))["pendientes"] == []
    assert _detalle(v["visita_id"])["requiere_reprogramacion"] is False


def test_cancelar_la_visita_tambien_resuelve_la_alerta(invocaciones):
    invocaciones.side_effect = lambda nombre, carga: {"items": []}
    v = nueva()
    consumidor.lambda_handler(_ausencia(), None)
    visitas.cancelar(peticion(ctx(), ruta={"visita_id": v["visita_id"]}), None)
    assert cuerpo(alertas.listar(peticion(ctx()), None))["pendientes"] == []


def test_mensaje_repetido_no_reasigna_dos_veces(invocaciones):
    nueva()
    mensaje = _ausencia(event_id="E-AUS")
    consumidor.lambda_handler(mensaje, None)
    with mock.patch.object(eventos, "publicar") as publicar:
        r = consumidor.lambda_handler(mensaje, None)
    assert publicar.call_count == 0
    assert len(cuerpo(alertas.listar(peticion(ctx()), None))["recientes"]) == 1
    assert r["reasignadas"] == 0


def test_analitica_caida_reasigna_igual(invocaciones):
    def invocar(nombre, carga):
        if nombre == "analitica-interno":
            raise RuntimeError("caída")
        return {"items": CANDIDATOS}
    invocaciones.side_effect = invocar
    v = nueva()
    assert consumidor.lambda_handler(_ausencia(), None)["reasignadas"] == 1
    assert _detalle(v["visita_id"])["tecnico_id"] == "T2"  # Alfabético: Ana antes que Beto.


def test_ausencia_sin_visitas_no_consulta_a_nadie(invocaciones):
    assert consumidor.lambda_handler(_ausencia(), None) == {"reasignadas": 0, "alertas": 0}
    assert invocaciones.call_count == 0


def test_otras_fechas_y_visitas_iniciadas_no_se_tocan(invocaciones):
    otra = nueva(inicio="2026-11-11T15:00:00Z", fin="2026-11-11T16:00:00Z")
    iniciada = nueva(inicio=I10, fin=I11)
    visitas.iniciar(peticion(ctx(rol="TECNICO", tecnico="T1"), ruta={"visita_id": iniciada["visita_id"]}), None)
    consumidor.lambda_handler(_ausencia(), None)
    assert _detalle(otra["visita_id"])["tecnico_id"] == "T1"
    assert _detalle(iniciada["visita_id"])["tecnico_id"] == "T1"


def test_alertas_solo_para_gestion():
    assert alertas.listar(peticion(ctx(rol="TECNICO", tecnico="T1")), None)["statusCode"] == 403
