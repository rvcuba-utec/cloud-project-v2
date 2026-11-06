from unittest import mock

import pytest
from moto import mock_aws

from apoyo_pruebas import crear_tabla, ctx, cuerpo, entorno_aws, peticion
from trazora_common import dynamo, interno
from trazora_common.http import ApiError

from handlers import ordenes

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
