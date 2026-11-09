import json
from unittest import mock

import pytest
from moto import mock_aws

from apoyo_pruebas import crear_tabla, ctx, cuerpo, entorno_aws, peticion
from trazora_common import dynamo, eventos, interno
from trazora_common.http import ApiError

from dominio import ordenes as dom
from handlers import consumidor, ordenes

UBICACION = {"cliente_nombre": "Comercial López", "cliente_activo": True, "direccion": "Av. 1", "distrito": "Miraflores"}
DATOS = {"cliente_id": "CLI-1", "ubicacion_id": "LOC-1", "tipo_servicio": "REPARACION", "descripcion": "No enfría", "prioridad": "ALTA"}


@pytest.fixture(autouse=True)
def aws(monkeypatch):
    entorno_aws(monkeypatch, "t_ordenes")
    monkeypatch.setenv("CLIENTES_URL", "https://clientes.ejemplo/dev")
    with mock_aws():
        dynamo.reiniciar()
        crear_tabla("t_ordenes", "GSI1", "GSI2")
        with mock.patch.object(interno, "llamar", return_value=UBICACION) as llamada:
            yield llamada
        dynamo.reiniciar()


def nueva(tenant="CLIMALIMA", **extra):
    r = ordenes.crear(peticion(ctx(tenant), {**DATOS, **extra}, headers={"Authorization": "Bearer tok"}), None)
    assert r["statusCode"] == 201, r["body"]
    return cuerpo(r)


def test_crea_abierta_con_datos_copiados_y_reenvia_token(aws):
    o = nueva()
    assert o["estado"] == "ABIERTA" and o["version"] == 1
    assert o["cliente_nombre"] == "Comercial López" and o["direccion"] == "Av. 1"
    assert not {"PK", "SK", "GSI1PK", "GSI2SK"} & o.keys()
    argumentos = aws.call_args.args
    assert argumentos[1] == "/clientes/CLI-1/ubicaciones/LOC-1" and argumentos[2] == "tok"


def test_tenant_del_cuerpo_se_ignora():
    assert nueva(tenant_id="FRIOSUR")["tenant_id"] == "CLIMALIMA"


def test_cliente_de_otra_empresa_rechazado(aws):
    aws.side_effect = ApiError(404, "NO_ENCONTRADO", "Ubicación no encontrada")
    r = ordenes.crear(peticion(ctx(), DATOS), None)
    assert r["statusCode"] == 404
    assert cuerpo(ordenes.listar(peticion(ctx()), None))["items"] == []


def test_cliente_inactivo_rechazado(aws):
    aws.return_value = {**UBICACION, "cliente_activo": False}
    assert ordenes.crear(peticion(ctx(), DATOS), None)["statusCode"] == 409


def test_clientes_no_disponible_es_503(aws):
    aws.side_effect = ApiError(503, "SERVICIO_NO_DISPONIBLE", "x")
    assert ordenes.crear(peticion(ctx(), DATOS), None)["statusCode"] == 503


@pytest.mark.parametrize("cambio", [{"tipo_servicio": "X"}, {"prioridad": "X"}, {"descripcion": ""}, {"cliente_id": None}])
def test_valida_entrada(cambio):
    assert ordenes.crear(peticion(ctx(), {**DATOS, **cambio}), None)["statusCode"] == 400


def test_tecnico_no_accede():
    assert ordenes.crear(peticion(ctx(rol="TECNICO"), DATOS), None)["statusCode"] == 403
    assert ordenes.listar(peticion(ctx(rol="TECNICO")), None)["statusCode"] == 403


def test_creacion_repetida_devuelve_la_misma_y_no_llama_otra_vez(aws):
    cab = {"Idempotency-Key": "k1"}
    a = ordenes.crear(peticion(ctx(), DATOS, headers=cab), None)
    b = ordenes.crear(peticion(ctx(), DATOS, headers=cab), None)
    assert cuerpo(a)["orden_id"] == cuerpo(b)["orden_id"]
    assert aws.call_count == 1
    assert len(cuerpo(ordenes.listar(peticion(ctx()), None))["items"]) == 1


def test_misma_clave_con_otros_datos_es_conflicto():
    cab = {"Idempotency-Key": "k1"}
    ordenes.crear(peticion(ctx(), DATOS, headers=cab), None)
    r = ordenes.crear(peticion(ctx(), {**DATOS, "descripcion": "otra"}, headers=cab), None)
    assert cuerpo(r)["error"]["codigo"] == "CLAVE_REUTILIZADA"


def test_listar_filtra_y_aisla():
    a = nueva()
    nueva(cliente_id="CLI-2")
    nueva(tenant="FRIOSUR")
    todas = cuerpo(ordenes.listar(peticion(ctx()), None))["items"]
    assert len(todas) == 2
    por_estado = cuerpo(ordenes.listar(peticion(ctx(), query={"estado": "ABIERTA"}), None))["items"]
    assert len(por_estado) == 2
    assert cuerpo(ordenes.listar(peticion(ctx(), query={"estado": "CERRADA"}), None))["items"] == []
    por_cliente = cuerpo(ordenes.listar(peticion(ctx(), query={"cliente_id": "CLI-1"}), None))["items"]
    assert [o["orden_id"] for o in por_cliente] == [a["orden_id"]]


def test_listado_de_mas_reciente_a_mas_antigua():
    a, b = nueva(), nueva()
    ids = [o["orden_id"] for o in cuerpo(ordenes.listar(peticion(ctx()), None))["items"]]
    assert ids == sorted([a["orden_id"], b["orden_id"]], reverse=True)


def test_filtros_invalidos():
    assert ordenes.listar(peticion(ctx(), query={"estado": "X"}), None)["statusCode"] == 400
    assert ordenes.listar(peticion(ctx(), query={"estado": "ABIERTA", "cliente_id": "C"}), None)["statusCode"] == 400


def test_otra_empresa_recibe_404():
    o = nueva()
    ruta = {"orden_id": o["orden_id"]}
    assert ordenes.detalle(peticion(ctx("FRIOSUR"), ruta=ruta), None)["statusCode"] == 404
    assert ordenes.historial(peticion(ctx("FRIOSUR"), ruta=ruta), None)["statusCode"] == 404
    assert ordenes.actualizar(peticion(ctx("FRIOSUR"), {"prioridad": "BAJA", "version": 1}, ruta), None)["statusCode"] == 404


def test_cambio_de_prioridad_controla_version():
    o = nueva()
    ruta = {"orden_id": o["orden_id"]}
    r = ordenes.actualizar(peticion(ctx(), {"prioridad": "BAJA", "version": 1}, ruta), None)
    assert cuerpo(r)["prioridad"] == "BAJA" and cuerpo(r)["version"] == 2
    viejo = ordenes.actualizar(peticion(ctx(), {"prioridad": "ALTA", "version": 1}, ruta), None)
    assert viejo["statusCode"] == 409 and cuerpo(viejo)["error"]["detalle"]["version"] == 2


def test_orden_terminada_no_cambia():
    o = nueva()
    dynamo.tabla().update_item(
        Key={"PK": "TENANT#CLIMALIMA", "SK": f"ORDEN#{o['orden_id']}"},
        UpdateExpression="SET estado = :e", ExpressionAttributeValues={":e": "CERRADA"},
    )
    r = ordenes.actualizar(peticion(ctx(), {"prioridad": "BAJA", "version": 1}, {"orden_id": o["orden_id"]}), None)
    assert cuerpo(r)["error"]["codigo"] == "ORDEN_TERMINADA"


def test_historial_registra_la_creacion():
    o = nueva()
    items = cuerpo(ordenes.historial(peticion(ctx(), ruta={"orden_id": o["orden_id"]}), None))["items"]
    assert [i["tipo"] for i in items] == ["ORDEN_CREADA"]


# ---- Cierre y cancelación
def _forzar_estado(orden, estado):
    dynamo.tabla().update_item(
        Key={"PK": "TENANT#CLIMALIMA", "SK": f"ORDEN#{orden['orden_id']}"},
        UpdateExpression="SET estado = :e, GSI1PK = :g",
        ExpressionAttributeValues={":e": estado, ":g": f"TENANT#CLIMALIMA#ESTADO#{estado}"},
    )


def _guardada(orden):
    return dynamo.tabla().get_item(Key={"PK": "TENANT#CLIMALIMA", "SK": f"ORDEN#{orden['orden_id']}"})["Item"]


@pytest.fixture
def bloqueo(monkeypatch):
    monkeypatch.setenv("AGENDA_BLOQUEO_FN", "agenda-bloqueo")
    with mock.patch.object(ordenes, "_pedir_bloqueo", return_value={"bloqueada": True, "visitas_activas": 0}) as m:
        yield m


def test_cerrar_exige_pendiente_de_cierre(bloqueo):
    o = nueva()
    r = ordenes.cerrar(peticion(ctx(), ruta={"orden_id": o["orden_id"]}), None)
    assert r["statusCode"] == 409 and cuerpo(r)["error"]["codigo"] == "ESTADO_NO_PERMITE"
    assert bloqueo.call_count == 0


def test_cerrar_ok_y_repetir_es_seguro(bloqueo):
    o = nueva()
    _forzar_estado(o, "PENDIENTE_DE_CIERRE")
    ruta = {"orden_id": o["orden_id"]}
    r = ordenes.cerrar(peticion(ctx(), ruta=ruta), None)
    assert r["statusCode"] == 200 and cuerpo(r)["estado"] == "CERRADA"
    assert ordenes.cerrar(peticion(ctx(), ruta=ruta), None)["statusCode"] == 200
    assert bloqueo.call_count == 1
    assert cuerpo(ordenes.listar(peticion(ctx(), query={"estado": "CERRADA"}), None))["items"]
    assert not {"operacion_cierre", "destino_cierre"} & _guardada(o).keys()


def test_cierre_rechazado_vuelve_al_estado_anterior(bloqueo):
    bloqueo.return_value = {"bloqueada": False, "visitas_activas": 2}
    o = nueva()
    _forzar_estado(o, "PENDIENTE_DE_CIERRE")
    r = ordenes.cerrar(peticion(ctx(), ruta={"orden_id": o["orden_id"]}), None)
    assert r["statusCode"] == 409 and cuerpo(r)["error"]["detalle"]["visitas_activas"] == 2
    assert _guardada(o)["estado"] == "PENDIENTE_DE_CIERRE"


def test_fallo_de_comunicacion_conserva_operacion_y_reintenta_con_el_mismo_id(bloqueo):
    bloqueo.side_effect = RuntimeError("sin respuesta")
    o = nueva()
    _forzar_estado(o, "PENDIENTE_DE_CIERRE")
    ruta = {"orden_id": o["orden_id"]}
    r = ordenes.cerrar(peticion(ctx(), ruta=ruta), None)
    assert r["statusCode"] == 503
    guardada = _guardada(o)
    assert guardada["estado"] == "CIERRE_EN_PROCESO"
    primera = bloqueo.call_args.args[2]

    bloqueo.side_effect = None
    bloqueo.return_value = {"bloqueada": True, "visitas_activas": 0}
    assert cuerpo(ordenes.cerrar(peticion(ctx(), ruta=ruta), None))["estado"] == "CERRADA"
    assert bloqueo.call_args.args[2] == primera


def test_cancelar_abierta(bloqueo):
    o = nueva()
    assert cuerpo(ordenes.cancelar(peticion(ctx(), ruta={"orden_id": o["orden_id"]}), None))["estado"] == "CANCELADA"


def test_cancelar_no_interfiere_con_cierre_en_curso(bloqueo):
    bloqueo.side_effect = RuntimeError("x")
    o = nueva()
    _forzar_estado(o, "PENDIENTE_DE_CIERRE")
    ordenes.cerrar(peticion(ctx(), ruta={"orden_id": o["orden_id"]}), None)
    r = ordenes.cancelar(peticion(ctx(), ruta={"orden_id": o["orden_id"]}), None)
    assert cuerpo(r)["error"]["codigo"] == "OPERACION_EN_CURSO"


def test_cerrar_otra_empresa_404(bloqueo):
    o = nueva()
    assert ordenes.cerrar(peticion(ctx("FRIOSUR"), ruta={"orden_id": o["orden_id"]}), None)["statusCode"] == 404


def test_tecnico_no_cierra(bloqueo):
    o = nueva()
    assert ordenes.cerrar(peticion(ctx(rol="TECNICO"), ruta={"orden_id": o["orden_id"]}), None)["statusCode"] == 403


def test_outbox_pendiente_si_no_se_puede_publicar():
    o = nueva()  # Sin TOPIC_ARN en este entorno: la orden se guarda y el evento queda pendiente.
    pendientes = dynamo.consultar_todo(dynamo.tabla(), "TENANT#CLIMALIMA", "OUTBOX#")
    assert [p["evento"]["aggregate_id"] for p in pendientes] == [o["orden_id"]]


# ---- Estado derivado
def _v(estado, numero=1, resultado=None):
    entrada = {"estado": estado, "version": 1, "numero": numero}
    return {**entrada, "resultado": resultado} if resultado else entrada


@pytest.mark.parametrize("resumen,esperado", [
    ({}, "ABIERTA"),
    ({"a": _v("CANCELADA")}, "ABIERTA"),
    ({"a": _v("PROGRAMADA")}, "PROGRAMADA"),
    ({"a": _v("EN_ATENCION"), "b": _v("PROGRAMADA", 2)}, "EN_ATENCION"),
    ({"a": _v("FINALIZADA", 1, "RESUELTO")}, "PENDIENTE_DE_CIERRE"),
    ({"a": _v("FINALIZADA", 1, "REQUIERE_REVISITA")}, "REQUIERE_REVISITA"),
    ({"a": _v("FINALIZADA", 1, "NO_ATENDIDO")}, "REQUIERE_REVISITA"),
    ({"a": _v("FINALIZADA", 1, "REQUIERE_REVISITA"), "b": _v("PROGRAMADA", 2)}, "PROGRAMADA"),
    ({"a": _v("FINALIZADA", 1, "REQUIERE_REVISITA"), "b": _v("FINALIZADA", 2, "RESUELTO")}, "PENDIENTE_DE_CIERRE"),
    ({"a": _v("FINALIZADA", 1, "RESUELTO"), "b": _v("FINALIZADA", 2, "NO_ATENDIDO")}, "REQUIERE_REVISITA"),
    ({"a": _v("FINALIZADA", 1, "RESUELTO"), "b": _v("CANCELADA", 2)}, "PENDIENTE_DE_CIERRE"),
])
def test_derivar_estado(resumen, esperado):
    assert dom.derivar_estado(resumen) == esperado


# ---- Consumidor
def _evento_visita(orden_id, tipo, version, visita="V1", numero=1, tenant="CLIMALIMA", event_id=None, **extra):
    evento = eventos.crear_evento(tipo, tenant, "VISITA", visita, version,
                                  {"orden_id": orden_id, "visita_id": visita, "numero_visita_orden": numero, **extra},
                                  event_id=event_id)
    return {"Records": [{"body": json.dumps({"Message": json.dumps(evento)})}]}


def _estado(orden_id):
    return cuerpo(ordenes.detalle(peticion(ctx(), ruta={"orden_id": orden_id}), None))


def test_eventos_de_visita_mueven_la_orden_y_su_indice():
    orden = nueva()["orden_id"]
    consumidor.lambda_handler(_evento_visita(orden, "VisitaProgramada", 1), None)
    assert _estado(orden)["estado"] == "PROGRAMADA"
    consumidor.lambda_handler(_evento_visita(orden, "VisitaIniciada", 2), None)
    assert _estado(orden)["estado"] == "EN_ATENCION"
    consumidor.lambda_handler(_evento_visita(orden, "VisitaCompletada", 3, resultado="RESUELTO"), None)
    assert _estado(orden)["estado"] == "PENDIENTE_DE_CIERRE"

    lista = cuerpo(ordenes.listar(peticion(ctx(), query={"estado": "PENDIENTE_DE_CIERRE"}), None))
    assert [o["orden_id"] for o in lista["items"]] == [orden]
    assert cuerpo(ordenes.listar(peticion(ctx(), query={"estado": "ABIERTA"}), None))["items"] == []


def test_evento_atrasado_no_retrocede_el_estado():
    orden = nueva()["orden_id"]
    consumidor.lambda_handler(_evento_visita(orden, "VisitaCompletada", 3, resultado="RESUELTO"), None)
    version = _estado(orden)["version"]
    consumidor.lambda_handler(_evento_visita(orden, "VisitaIniciada", 2), None)
    consumidor.lambda_handler(_evento_visita(orden, "VisitaProgramada", 1), None)
    actual = _estado(orden)
    assert actual["estado"] == "PENDIENTE_DE_CIERRE" and actual["version"] == version


def test_las_versiones_son_por_visita():
    orden = nueva()["orden_id"]
    consumidor.lambda_handler(_evento_visita(orden, "VisitaCompletada", 3, resultado="REQUIERE_REVISITA"), None)
    assert _estado(orden)["estado"] == "REQUIERE_REVISITA"
    consumidor.lambda_handler(_evento_visita(orden, "VisitaProgramada", 1, visita="V2", numero=2), None)
    assert _estado(orden)["estado"] == "PROGRAMADA"


def test_mensaje_repetido_no_se_aplica_dos_veces():
    orden = nueva()["orden_id"]
    mensaje = _evento_visita(orden, "VisitaProgramada", 1, event_id="E1")
    consumidor.lambda_handler(mensaje, None)
    version = _estado(orden)["version"]
    historial = cuerpo(ordenes.historial(peticion(ctx(), ruta={"orden_id": orden}), None))["items"]
    consumidor.lambda_handler(mensaje, None)
    assert _estado(orden)["version"] == version
    assert len(cuerpo(ordenes.historial(peticion(ctx(), ruta={"orden_id": orden}), None))["items"]) == len(historial)


def test_orden_terminada_no_cambia_de_estado():
    orden = nueva()["orden_id"]
    dynamo.tabla().update_item(Key={"PK": "TENANT#CLIMALIMA", "SK": f"ORDEN#{orden}"},
                               UpdateExpression="SET estado = :e", ExpressionAttributeValues={":e": "CANCELADA"})
    consumidor.lambda_handler(_evento_visita(orden, "VisitaCancelada", 2), None)
    assert _estado(orden)["estado"] == "CANCELADA"


def test_durante_el_cierre_se_actualiza_el_estado_al_que_volveria():
    orden = nueva()["orden_id"]
    clave = {"PK": "TENANT#CLIMALIMA", "SK": f"ORDEN#{orden}"}
    dynamo.tabla().update_item(Key=clave, UpdateExpression="SET estado = :e, estado_previo = :p",
                               ExpressionAttributeValues={":e": "CIERRE_EN_PROCESO", ":p": "ABIERTA"})
    consumidor.lambda_handler(_evento_visita(orden, "VisitaProgramada", 1), None)
    item = dynamo.tabla().get_item(Key=clave)["Item"]
    assert item["estado"] == "CIERRE_EN_PROCESO" and item["estado_previo"] == "PROGRAMADA"


def test_conflicto_con_otra_escritura_relee_y_aplica():
    orden = nueva()["orden_id"]
    leido = {"veces": 0}

    def transaccion_que_falla_una_vez(operaciones, *a, **k):
        leido["veces"] += 1
        if leido["veces"] == 1:
            raise dynamo.TransaccionCancelada(["None", "ConditionalCheckFailed", "None"])
        return real(operaciones, *a, **k)

    real = dynamo.transaccion
    with mock.patch.object(dynamo, "transaccion", side_effect=transaccion_que_falla_una_vez):
        consumidor.lambda_handler(_evento_visita(orden, "VisitaProgramada", 1), None)
    assert leido["veces"] == 2
    assert _estado(orden)["estado"] == "PROGRAMADA"


def test_parte_finalizado_queda_en_el_historial_sin_cambiar_estado():
    orden = nueva()["orden_id"]
    evento = eventos.crear_evento("ParteFinalizado", "CLIMALIMA", "PARTE", "P1", 2,
                                  {"orden_id": orden, "visita_id": "V1", "resultado": "RESUELTO"}, event_id="E9")
    mensaje = {"Records": [{"body": json.dumps({"Message": json.dumps(evento)})}]}
    consumidor.lambda_handler(mensaje, None)
    consumidor.lambda_handler(mensaje, None)
    items = cuerpo(ordenes.historial(peticion(ctx(), ruta={"orden_id": orden}), None))["items"]
    assert [i["tipo"] for i in items].count("PARTE_FINALIZADO") == 1
    assert _estado(orden)["estado"] == "ABIERTA"


def test_mensajes_invalidos_fallan_para_terminar_en_la_dlq():
    with pytest.raises(Exception):
        consumidor.lambda_handler({"Records": [{"body": "x"}]}, None)
    with pytest.raises(ValueError):
        consumidor.lambda_handler(_evento_visita("NO-EXISTE", "VisitaProgramada", 1), None)
    with pytest.raises(ValueError):
        consumidor.lambda_handler(_evento_visita("X", "OtroEvento", 1), None)


# ---- Cancelación en cascada y mapa
def test_cancelar_pide_cancelar_visitas_y_informa_cuantas(bloqueo):
    bloqueo.return_value = {"bloqueada": True, "visitas_activas": 0, "visitas_canceladas": 2}
    o = nueva()
    r = ordenes.cancelar(peticion(ctx(), ruta={"orden_id": o["orden_id"]}), None)
    assert r["statusCode"] == 200 and cuerpo(r)["visitas_canceladas"] == 2
    assert bloqueo.call_args.kwargs["cancelar_programadas"] is True


def test_cerrar_no_cancela_visitas(bloqueo):
    o = nueva()
    _forzar_estado(o, "PENDIENTE_DE_CIERRE")
    ordenes.cerrar(peticion(ctx(), ruta={"orden_id": o["orden_id"]}), None)
    assert bloqueo.call_args.kwargs["cancelar_programadas"] is False


def test_cancelar_con_visita_en_atencion_lo_explica(bloqueo):
    bloqueo.return_value = {"bloqueada": False, "visitas_activas": 1, "visitas_canceladas": 1}
    o = nueva()
    r = ordenes.cancelar(peticion(ctx(), ruta={"orden_id": o["orden_id"]}), None)
    assert r["statusCode"] == 409 and cuerpo(r)["error"]["codigo"] == "VISITA_EN_ATENCION"
    assert _guardada(o)["estado"] == "ABIERTA"


def test_orden_copia_las_coordenadas_y_aparece_en_el_mapa(aws):
    aws.return_value = {**UBICACION, "lat": -12.12, "lng": -77.03}
    o = nueva()
    aws.return_value = UBICACION
    nueva()  # Sin coordenadas: cuenta, pero no se dibuja.
    r = cuerpo(ordenes.mapa(peticion(ctx()), None))
    assert [p["orden_id"] for p in r["puntos"]] == [o["orden_id"]]
    assert r["puntos"][0]["lat"] == -12.12 and r["conteo"]["ABIERTA"] == 2
    assert cuerpo(ordenes.mapa(peticion(ctx(tenant="FRIOSUR")), None))["puntos"] == []


def test_mapa_solo_para_gestion():
    assert ordenes.mapa(peticion(ctx(rol="TECNICO")), None)["statusCode"] == 403


def test_historial_dice_que_la_reasignacion_fue_automatica():
    orden = nueva()["orden_id"]
    consumidor.lambda_handler(_evento_visita(orden, "VisitaProgramada", 1), None)
    consumidor.lambda_handler(_evento_visita(orden, "VisitaReprogramada", 2, automatica=True, motivo="Ausencia de Carlos"), None)
    items = cuerpo(ordenes.historial(peticion(ctx(), ruta={"orden_id": orden}), None))["items"]
    assert any("reasignada sola: Ausencia de Carlos" in i["detalle"] for i in items)


def test_cancelar_tolera_que_los_eventos_cambien_la_orden_mientras_tanto(bloqueo):
    """En AWS, las VisitaCancelada de la cascada llegan a Órdenes antes del paso final."""
    o = nueva()

    def bloquear_y_simular_eventos(*args, **kwargs):
        dynamo.tabla().update_item(Key={"PK": "TENANT#CLIMALIMA", "SK": f"ORDEN#{o['orden_id']}"},
                                   UpdateExpression="ADD #v :uno SET estado_previo = :e",
                                   ExpressionAttributeNames={"#v": "version"}, ExpressionAttributeValues={":uno": 1, ":e": "ABIERTA"})
        return {"bloqueada": True, "visitas_activas": 0, "visitas_canceladas": 2}

    bloqueo.side_effect = bloquear_y_simular_eventos
    r = ordenes.cancelar(peticion(ctx(), ruta={"orden_id": o["orden_id"]}), None)
    assert r["statusCode"] == 200 and cuerpo(r)["estado"] == "CANCELADA", r["body"]


def test_rechazo_tambien_tolera_eventos_intermedios(bloqueo):
    o = nueva()

    def bloquear_y_simular_eventos(*args, **kwargs):
        dynamo.tabla().update_item(Key={"PK": "TENANT#CLIMALIMA", "SK": f"ORDEN#{o['orden_id']}"},
                                   UpdateExpression="ADD #v :uno", ExpressionAttributeNames={"#v": "version"}, ExpressionAttributeValues={":uno": 1})
        return {"bloqueada": False, "visitas_activas": 1, "visitas_canceladas": 1}

    bloqueo.side_effect = bloquear_y_simular_eventos
    r = ordenes.cancelar(peticion(ctx(), ruta={"orden_id": o["orden_id"]}), None)
    assert r["statusCode"] == 409 and cuerpo(r)["error"]["codigo"] == "VISITA_EN_ATENCION"
    assert _guardada(o)["estado"] == "ABIERTA"
