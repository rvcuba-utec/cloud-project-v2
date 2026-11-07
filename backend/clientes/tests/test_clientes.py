import pytest
from moto import mock_aws

from apoyo_pruebas import crear_tabla, ctx, cuerpo, entorno_aws, peticion
from trazora_common import dynamo

from dominio.clientes import normalizar_nombre
from handlers import clientes, ubicaciones


@pytest.fixture(autouse=True)
def aws(monkeypatch):
    entorno_aws(monkeypatch, "t_clientes")
    with mock_aws():
        dynamo.reiniciar()
        crear_tabla("t_clientes", "GSI1")
        yield
        dynamo.reiniciar()


def nuevo(nombre="Comercial López", tenant="CLIMALIMA", **extra):
    r = clientes.crear(peticion(ctx(tenant), {"nombre": nombre, **extra}), None)
    assert r["statusCode"] == 201, r["body"]
    return cuerpo(r)


def nueva_ubicacion(cliente_id, tenant="CLIMALIMA"):
    return ubicaciones.crear(peticion(ctx(tenant), {"nombre": "Oficina", "direccion": "Av. 1", "distrito": "Miraflores"}, {"cliente_id": cliente_id}), None)


def test_normalizar_nombre():
    assert normalizar_nombre("  Comercial   LÓPEZ ") == "comercial lopez"


def test_respuesta_sin_claves_internas():
    datos = nuevo(tenant_id="FRIOSUR")
    assert datos["tenant_id"] == "CLIMALIMA"
    assert not {"PK", "SK", "GSI1PK", "GSI1SK", "entity_type"} & datos.keys()


def test_tecnico_no_accede():
    assert clientes.listar(peticion(ctx(rol="TECNICO")), None)["statusCode"] == 403
    assert clientes.crear(peticion(ctx(rol="TECNICO"), {"nombre": "x"}), None)["statusCode"] == 403


def test_nombre_obligatorio():
    assert clientes.crear(peticion(ctx(), {"nombre": "  "}), None)["statusCode"] == 400


def test_lista_ordenada_con_busqueda_sin_tildes_y_aislada():
    nuevo("Zeta")
    nuevo("Álvarez SAC")
    nuevo("Alvarado")
    nuevo("Álvarez de otra empresa", tenant="FRIOSUR")
    nombres = [c["nombre"] for c in cuerpo(clientes.listar(peticion(ctx()), None))["items"]]
    assert nombres == ["Alvarado", "Álvarez SAC", "Zeta"]
    hallados = cuerpo(clientes.listar(peticion(ctx(), query={"q": "ALVAREZ"}), None))["items"]
    assert [c["nombre"] for c in hallados] == ["Álvarez SAC"]


def test_paginacion_por_nombre():
    for n in "ABC":
        nuevo(n)
    uno = cuerpo(clientes.listar(peticion(ctx(), query={"limit": "2"}), None))
    dos = cuerpo(clientes.listar(peticion(ctx(), query={"limit": "2", "cursor": uno["next_cursor"]}), None))
    assert [c["nombre"] for c in uno["items"] + dos["items"]] == ["A", "B", "C"]


def test_cursor_de_otra_empresa_rechazado():
    nuevo("A", tenant="FRIOSUR")
    nuevo("B", tenant="FRIOSUR")
    cursor = cuerpo(clientes.listar(peticion(ctx("FRIOSUR"), query={"limit": "1"}), None))["next_cursor"]
    assert clientes.listar(peticion(ctx(), query={"cursor": cursor}), None)["statusCode"] == 400


def test_otra_empresa_recibe_404():
    c = nuevo()
    ruta = {"cliente_id": c["cliente_id"]}
    assert clientes.detalle(peticion(ctx("FRIOSUR"), ruta=ruta), None)["statusCode"] == 404
    assert clientes.actualizar(peticion(ctx("FRIOSUR"), {"nombre": "x"}, ruta), None)["statusCode"] == 404
    assert ubicaciones.listar(peticion(ctx("FRIOSUR"), ruta=ruta), None)["statusCode"] == 404


def test_actualizar_cambia_orden_e_ignora_tenant():
    c = nuevo("Antes")
    r = clientes.actualizar(peticion(ctx(), {"nombre": "Después", "tenant_id": "FRIOSUR"}, {"cliente_id": c["cliente_id"]}), None)
    assert cuerpo(r)["nombre"] == "Después" and cuerpo(r)["tenant_id"] == "CLIMALIMA"
    assert cuerpo(clientes.listar(peticion(ctx(), query={"q": "despues"}), None))["items"]


def test_creacion_repetida_devuelve_el_mismo_cliente():
    cab = {"Idempotency-Key": "k1"}
    a = clientes.crear(peticion(ctx(), {"nombre": "A"}, headers=cab), None)
    b = clientes.crear(peticion(ctx(), {"nombre": "A"}, headers=cab), None)
    assert cuerpo(a)["cliente_id"] == cuerpo(b)["cliente_id"]
    assert len(cuerpo(clientes.listar(peticion(ctx()), None))["items"]) == 1


def test_misma_clave_con_otros_datos_es_conflicto():
    cab = {"Idempotency-Key": "k1"}
    clientes.crear(peticion(ctx(), {"nombre": "A"}, headers=cab), None)
    r = clientes.crear(peticion(ctx(), {"nombre": "B"}, headers=cab), None)
    assert r["statusCode"] == 409 and cuerpo(r)["error"]["codigo"] == "CLAVE_REUTILIZADA"


def test_la_clave_no_cruza_empresas():
    cab = {"Idempotency-Key": "k1"}
    a = clientes.crear(peticion(ctx(), {"nombre": "A"}, headers=cab), None)
    b = clientes.crear(peticion(ctx("FRIOSUR"), {"nombre": "A"}, headers=cab), None)
    assert cuerpo(a)["cliente_id"] != cuerpo(b)["cliente_id"]


def test_ubicaciones_y_detalle_con_nombre_de_cliente():
    c = nuevo()
    u = cuerpo(nueva_ubicacion(c["cliente_id"]))
    ruta = {"cliente_id": c["cliente_id"], "ubicacion_id": u["ubicacion_id"]}
    d = cuerpo(ubicaciones.detalle(peticion(ctx(), ruta=ruta), None))
    assert d["cliente_nombre"] == "Comercial López" and d["cliente_activo"] is True
    assert [x["ubicacion_id"] for x in cuerpo(ubicaciones.listar(peticion(ctx(), ruta={"cliente_id": c["cliente_id"]}), None))["items"]] == [u["ubicacion_id"]]
    assert ubicaciones.detalle(peticion(ctx("FRIOSUR"), ruta=ruta), None)["statusCode"] == 404


def test_no_agrega_ubicacion_a_cliente_inactivo():
    c = nuevo()
    clientes.actualizar(peticion(ctx(), {"activo": False}, {"cliente_id": c["cliente_id"]}), None)
    assert nueva_ubicacion(c["cliente_id"])["statusCode"] == 409


def test_activo_debe_ser_booleano():
    c = nuevo()
    assert clientes.actualizar(peticion(ctx(), {"activo": "no"}, {"cliente_id": c["cliente_id"]}), None)["statusCode"] == 400


def test_ubicacion_con_coordenadas_elegidas_en_el_mapa():
    c = nuevo()["cliente_id"]
    datos = {"nombre": "Oficina", "direccion": "Av. 1", "distrito": "Miraflores", "lat": -12.12345678, "lng": -77.03}
    r = ubicaciones.crear(peticion(ctx(), datos, {"cliente_id": c}), None)
    assert r["statusCode"] == 201 and cuerpo(r)["lat"] == -12.123457


@pytest.mark.parametrize("extra", [{"lat": -12.1}, {"lat": 91, "lng": 0}, {"lat": "x", "lng": 1}, {"lat": True, "lng": 1}])
def test_coordenadas_invalidas_son_400(extra):
    c = nuevo()["cliente_id"]
    datos = {"nombre": "Oficina", "direccion": "Av. 1", "distrito": "Miraflores", **extra}
    assert ubicaciones.crear(peticion(ctx(), datos, {"cliente_id": c}), None)["statusCode"] == 400
