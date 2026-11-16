import json
from unittest import mock

import pytest
from moto import mock_aws

from apoyo_pruebas import crear_tabla, ctx, cuerpo, entorno_aws, evento_alb, peticion
from trazora_common import alb, dynamo, eventos

from dominio import analitica as dom
from handlers import consultas, consumidor

FECHA = "2026-11-10"


@pytest.fixture(autouse=True)
def aws(monkeypatch):
    entorno_aws(monkeypatch, "t_analitica")
    with mock_aws():
        dynamo.reiniciar()
        crear_tabla("t_analitica")
        yield
        dynamo.reiniciar()


def evento(tipo, tenant="CLIMALIMA", event_id=None, **datos):
    return eventos.crear_evento(tipo, tenant, "VISITA", "V1", 1, datos, event_id=event_id)


def aplicar(ev):
    return consumidor.lambda_handler({"Records": [{"messageId": "m1", "body": json.dumps({"Message": json.dumps(ev)})}]}, None)


def programada(tecnico="T1", fecha=FECHA, **kw):
    return evento("VisitaProgramada", tecnico_id=tecnico, fecha=fecha, **kw)


def completada(tecnico="T1", resultado="RESUELTO", numero=1, duracion=30, **kw):
    return evento("VisitaCompletada", tecnico_id=tecnico, fecha=FECHA, resultado=resultado,
                  numero_visita_orden=numero, duracion_min=duracion, **kw)


def lista(fecha=FECHA, tenant="CLIMALIMA"):
    r = cuerpo(consultas.tecnicos(peticion(ctx(tenant), query={"fecha": fecha}), None))
    return {m["tecnico_id"]: m for m in r["items"]}


def mes(periodo="2026-11", tenant="CLIMALIMA"):
    return cuerpo(consultas.dashboard(peticion(ctx(tenant), query={"periodo": periodo}), None))


def test_dashboard_y_detalle_mediante_alb(monkeypatch):
    aplicar(programada(tecnico="TEC-1"))
    aplicar(programada(tecnico="TEC-2", tenant="FRIOSUR"))
    monkeypatch.setenv("STAGE", "test")
    monkeypatch.setenv("ALB_RUTA", "GET /analitica/dashboard")
    identidad = alb.codificar_identidad(ctx())
    panel = evento_alb("GET", "/test/analitica/dashboard", identidad,
                       query={"periodo": ["2026-11"], "tenant_id": ["FRIOSUR"]})
    r = consultas.dashboard(panel, None)
    assert r["statusCode"] == 200 and cuerpo(r)["visitas_programadas"] == 1

    panel["multiValueHeaders"][alb.IDENTIDAD] = [alb.codificar_identidad(ctx(rol="TECNICO"))]
    assert consultas.dashboard(panel, None)["statusCode"] == 403
    monkeypatch.setenv("ALB_RUTA", "GET /analitica/tecnicos/{tecnico_id}")
    detalle = evento_alb("GET", "/test/analitica/tecnicos/TEC-1", identidad, query={"fecha": [FECHA]})
    assert cuerpo(consultas.tecnico(detalle, None))["carga_dia"] == 1
    detalle["path"] = "/test/analitica/tecnicos/TEC-2"
    assert cuerpo(consultas.tecnico(detalle, None))["carga_dia"] == 0
    detalle["multiValueQueryStringParameters"] = {"fecha": ["inválida"]}
    assert consultas.tecnico(detalle, None)["statusCode"] == 400


def test_programar_suma_a_la_carga_y_cancelar_resta():
    aplicar(programada())
    assert lista()["T1"]["carga_dia"] == 1 and mes()["visitas_programadas"] == 1
    aplicar(evento("VisitaCancelada", tecnico_id="T1", fecha=FECHA))
    assert lista()["T1"]["carga_dia"] == 0 and mes()["visitas_programadas"] == 0


def test_reprogramar_mueve_la_carga_entre_dias_tecnicos_y_meses():
    aplicar(programada())
    aplicar(evento("VisitaReprogramada", tecnico_id="T2", fecha="2026-12-01", tecnico_anterior="T1", fecha_anterior=FECHA))
    assert lista()["T1"]["carga_dia"] == 0
    assert lista("2026-12-01")["T2"]["carga_dia"] == 1
    assert mes()["visitas_programadas"] == 0 and mes("2026-12")["visitas_programadas"] == 1


def test_reprogramar_el_mismo_dia_no_toca_contadores_y_no_falla():
    aplicar(programada())
    aplicar(evento("VisitaReprogramada", tecnico_id="T1", fecha=FECHA, tecnico_anterior="T1", fecha_anterior=FECHA))
    assert lista()["T1"]["carga_dia"] == 1


def test_tasa_cuenta_solo_primeras_visitas_y_promedia_tiempo():
    aplicar(completada(resultado="RESUELTO", duracion=30))
    aplicar(completada(resultado="REQUIERE_REVISITA", duracion=60))
    aplicar(completada(resultado="RESUELTO", numero=2, duracion=90))
    m = lista()["T1"]
    assert m["tasa_resolucion"] == 0.5
    assert m["visitas_completadas_total"] == 3 and m["revisitas_generadas"] == 1
    assert m["tiempo_promedio_min"] == 60


def test_tecnico_sin_historial_no_muestra_tasa_inventada():
    aplicar(programada())
    m = lista()["T1"]
    assert "tasa_resolucion" not in m and "tiempo_promedio_min" not in m


def test_evento_repetido_no_cuenta_dos_veces():
    ev = completada(event_id="E1")
    aplicar(ev)
    aplicar(ev)
    assert lista()["T1"]["visitas_completadas_total"] == 1
    assert mes()["visitas_completadas"] == 1


def test_orden_de_llegada_no_altera_el_resultado():
    aplicar(evento("VisitaCancelada", tecnico_id="T1", fecha=FECHA))
    aplicar(programada())
    assert lista()["T1"]["carga_dia"] == 0


def test_ciclo_de_ordenes_en_el_mes():
    aplicar(evento("OrdenCreada", creada_en="2026-11-02T15:00:00Z"))
    aplicar(evento("OrdenCreada", creada_en="2026-11-03T15:00:00Z"))
    assert mes()["ordenes_abiertas"] == 2
    aplicar(evento("OrdenCerrada", creada_en="2026-11-02T15:00:00Z", terminada_en="2026-11-05T03:00:00Z"))
    aplicar(evento("OrdenCancelada", creada_en="2026-11-03T15:00:00Z", terminada_en="2026-11-04T15:00:00Z"))
    r = mes()
    assert r["ordenes_abiertas"] == 0 and r["ordenes_cerradas"] == 1 and r["ordenes_canceladas"] == 1
    assert r["tiempo_promedio_cierre_dias"] == 2.5


def test_orden_que_termina_otro_mes_afecta_ambos_periodos():
    aplicar(evento("OrdenCreada", creada_en="2026-11-30T15:00:00Z"))
    aplicar(evento("OrdenCerrada", creada_en="2026-11-30T15:00:00Z", terminada_en="2026-12-01T15:00:00Z"))
    assert mes()["ordenes_abiertas"] == 0 and mes()["ordenes_cerradas"] == 0
    assert mes("2026-12")["ordenes_cerradas"] == 1


def test_el_mes_usa_la_hora_de_lima():
    # 1 de diciembre a las 03:00 UTC sigue siendo 30 de noviembre en Lima.
    aplicar(evento("OrdenCreada", creada_en="2026-12-01T03:00:00Z"))
    assert mes()["ordenes_creadas"] == 1


def test_aislamiento_entre_empresas():
    aplicar(completada())
    assert lista(tenant="FRIOSUR") == {}
    assert mes(tenant="FRIOSUR")["visitas_completadas"] == 0


def test_mes_sin_datos_responde_en_cero_e_incluye_historico():
    aplicar(evento("OrdenCreada", creada_en="2026-11-02T15:00:00Z"))
    r = mes("2020-01")
    assert r["ordenes_creadas"] == 0
    assert [h["periodo"] for h in r["historico"]] == ["2026-11"]


def test_contador_negativo_no_se_muestra():
    aplicar(evento("VisitaCancelada", tecnico_id="T1", fecha=FECHA))  # Su programación fue anterior a la tabla.
    assert lista()["T1"]["carga_dia"] == 0 and mes()["visitas_programadas"] == 0


def test_tecnico_individual():
    aplicar(completada())
    r = cuerpo(consultas.tecnico(peticion(ctx(), ruta={"tecnico_id": "T1"}, query={"fecha": FECHA}), None))
    assert r["tasa_resolucion"] == 1 and r["fecha"] == FECHA


@pytest.mark.parametrize("handler,kw", [
    (consultas.dashboard, {}), (consultas.tecnicos, {}), (consultas.tecnico, {"ruta": {"tecnico_id": "T1"}}),
])
def test_tecnico_no_consulta_analitica(handler, kw):
    assert handler(peticion(ctx(rol="TECNICO", tecnico="T1"), **kw), None)["statusCode"] == 403


@pytest.mark.parametrize("query", [{"periodo": "noviembre"}, {"periodo": "2026-11-01"}])
def test_periodo_invalido_es_400(query):
    assert consultas.dashboard(peticion(ctx(), query=query), None)["statusCode"] == 400


def test_fecha_invalida_es_400():
    assert consultas.tecnicos(peticion(ctx(), query={"fecha": "ayer"}), None)["statusCode"] == 400


@pytest.mark.parametrize("mensaje", [
    {"Records": [{"messageId": "m1", "body": "no es json"}]},
    {"Records": [{"messageId": "m1", "body": json.dumps({"Message": json.dumps(evento("OtroEvento"))})}]},
    {"Records": [{"messageId": "m1", "body": json.dumps({"Message": json.dumps(evento("VisitaProgramada"))})}]},
])
def test_mensaje_invalido_falla_para_terminar_en_la_dlq(mensaje):
    assert consumidor.lambda_handler(mensaje, None) == {"batchItemFailures": [{"itemIdentifier": "m1"}]}


def test_conflicto_agotado_falla_para_que_sqs_reintente():
    with mock.patch.object(dynamo, "transaccion", side_effect=RuntimeError("conflicto")):
        assert aplicar(programada()) == {"batchItemFailures": [{"itemIdentifier": "m1"}]}


def test_efectos_agrupan_por_item():
    r = dom.efectos(completada(duracion=45))
    assert set(r) == {"METRICAS#T1", f"DIA#{FECHA}#T1", "DASHBOARD#2026-11"}
    assert r["METRICAS#T1"]["sumas"]["suma_minutos"] == 45
    assert "revisitas_generadas" not in r["METRICAS#T1"]["sumas"]


def test_ranking_interno_es_json_y_aislado():
    aplicar(completada())
    r = consultas.tecnicos_interno({"tenant_id": "CLIMALIMA", "fecha": FECHA}, None)
    assert r["items"][0]["tecnico_id"] == "T1"
    json.dumps(r)
    assert consultas.tecnicos_interno({"tenant_id": "FRIOSUR", "fecha": FECHA}, None)["items"] == []


@pytest.mark.parametrize("periodo", ["2026-13", "2026-00", "11-2026", "2026-1", "2026-11-01"])
def test_dashboard_rechaza_periodos_que_no_existen(periodo):
    r = consultas.dashboard(peticion(ctx(), query={"periodo": periodo}), None)
    assert r["statusCode"] == 400 and cuerpo(r)["error"]["detalle"]["campo"] == "periodo"


@pytest.mark.parametrize("fecha", ["2026-02-30", "2026-13-01", "hoy", "2026-1-01"])
def test_metricas_rechazan_fechas_que_no_existen(fecha):
    assert consultas.tecnicos(peticion(ctx(), query={"fecha": fecha}), None)["statusCode"] == 400
    assert consultas.tecnico(peticion(ctx(), ruta={"tecnico_id": "T1"}, query={"fecha": fecha}), None)["statusCode"] == 400
    with pytest.raises(ValueError):
        consultas.tecnicos_interno({"tenant_id": "CLIMALIMA", "fecha": fecha}, None)


def _registro(ev, identificador):
    return {"messageId": identificador, "body": json.dumps({"Message": json.dumps(ev)})}


def test_lote_mixto_reintenta_solo_el_fallido_y_conserva_metricas(capsys):
    ev = programada(event_id="e1")
    lote = {"Records": [_registro(ev, "m1"), {"messageId": "m2", "body": "secreto-fixture"}]}
    esperado = {"batchItemFailures": [{"itemIdentifier": "m2"}]}
    assert consumidor.lambda_handler(lote, None) == esperado
    assert consumidor.lambda_handler(lote, None) == esperado
    assert dynamo.tabla().get_item(Key={"PK": "TENANT#CLIMALIMA", "SK": "DASHBOARD#2026-11"})["Item"]["visitas_programadas"] == 1
    salida = capsys.readouterr().out
    assert "secreto-fixture" not in salida
    entradas = [json.loads(x) for x in salida.splitlines()]
    fallo = next(x for x in entradas if x.get("error_code") == "EVENTO_INVALIDO")
    assert fallo["log_datos"]["message_id"] == "m2" and fallo["stacktrace"]


def test_dashboard_denegado_devuelve_503_con_causa_privada(monkeypatch, capsys):
    from types import SimpleNamespace
    from botocore.exceptions import ClientError

    monkeypatch.setenv("STAGE", "test")
    monkeypatch.setenv("SERVICE_NAME", "analitica")
    error = ClientError({"Error": {"Code": "AccessDeniedException", "Message": "contenido-privado-fixture"}}, "GetItem")
    contexto = SimpleNamespace(aws_request_id="req-analitica-01", function_name="api-analitica-test-dashboard")
    with mock.patch.object(dynamo, "tabla") as tabla:
        tabla.return_value.get_item.side_effect = error
        r = consultas.dashboard(peticion(ctx(), headers={"Authorization": "Bearer token-fixture"}), contexto)
    assert r["statusCode"] == 503 and cuerpo(r)["error"]["request_id"] == "req-analitica-01"
    salida = capsys.readouterr().out
    registro = json.loads(salida)
    assert (registro["stage"], registro["service"], registro["tenant_id"]) == ("test", "analitica", "CLIMALIMA")
    assert registro["log_datos"]["aws_code"] == "AccessDeniedException" and registro["stacktrace"]
    assert all(s not in salida + r["body"] for s in ["contenido-privado-fixture", "token-fixture"])
    assert "AccessDenied" not in r["body"]


def test_mensaje_irrecuperable_llega_a_dlq_simulada():
    import boto3
    sqs = boto3.client("sqs")
    dlq = sqs.create_queue(QueueName="test-q-analitica-dlq")["QueueUrl"]
    arn = sqs.get_queue_attributes(QueueUrl=dlq, AttributeNames=["QueueArn"])["Attributes"]["QueueArn"]
    cola = sqs.create_queue(QueueName="test-q-analitica", Attributes={
        "VisibilityTimeout": "0", "RedrivePolicy": json.dumps({"deadLetterTargetArn": arn, "maxReceiveCount": 5})})["QueueUrl"]
    mid = sqs.send_message(QueueUrl=cola, MessageBody="malformado")["MessageId"]
    for _ in range(5):
        m = sqs.receive_message(QueueUrl=cola)["Messages"][0]
        respuesta = consumidor.lambda_handler({"Records": [{"messageId": m["MessageId"], "body": m["Body"]}]}, None)
        assert respuesta == {"batchItemFailures": [{"itemIdentifier": mid}]}
    assert not sqs.receive_message(QueueUrl=cola).get("Messages")
    assert sqs.receive_message(QueueUrl=dlq)["Messages"][0]["Body"] == "malformado"
