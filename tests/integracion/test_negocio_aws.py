"""Clientes, técnicos y órdenes contra AWS real, en secuencia."""
import uuid

import pytest

from apoyo import http
from apoyo import url_servicio


@pytest.fixture(scope="module")
def apis():
    return {s: url_servicio(s) for s in ("clientes", "tecnicos", "ordenes")}


def test_listas_aisladas_y_sin_token(apis, token_de):
    assert http(f"{apis['clientes']}/clientes")[0] == 401
    estado, _, datos = http(f"{apis['ordenes']}/ordenes?tenant_id=FRIOSUR", token=token_de("CLIMALIMA"))
    assert estado == 200
    assert {o["tenant_id"] for o in datos["items"]} <= {"CLIMALIMA"}


def test_tecnico_no_entra_a_clientes_ni_ordenes(apis, token_de):
    token = token_de("CLIMALIMA", "TECNICO")
    assert http(f"{apis['clientes']}/clientes", token=token)[0] == 403
    assert http(f"{apis['ordenes']}/ordenes", token=token)[0] == 403


def test_tecnico_ve_su_perfil_y_no_el_de_otro(apis, token_de):
    token = token_de("CLIMALIMA", "TECNICO")
    assert http(f"{apis['tecnicos']}/tecnicos/TEC-CLIMALIMA-DEMO", token=token)[0] == 200
    assert http(f"{apis['tecnicos']}/tecnicos/TEC-OTRO", token=token)[0] == 403


def test_jornadas_de_demo_disponibles(apis, token_de):
    import datetime
    import zoneinfo
    fecha = datetime.datetime.now(zoneinfo.ZoneInfo("America/Lima")).date().isoformat()
    estado, _, datos = http(f"{apis['tecnicos']}/tecnicos/disponibles?fecha={fecha}&especialidad=REPARACION", token=token_de("CLIMALIMA"))
    assert estado == 200
    assert "TEC-CLIMALIMA-DEMO" in [t["tecnico_id"] for t in datos["items"]]
    assert all(t["tenant_id"] == "CLIMALIMA" for t in datos["items"])


@pytest.mark.muta
def test_recorrido_cliente_orden_entre_servicios(apis, token_de):
    token = token_de("CLIMALIMA")
    estado, _, cliente = http(f"{apis['clientes']}/clientes", "POST", token, {"nombre": f"Prueba {uuid.uuid4().hex[:6]}"})
    assert estado == 201, cliente
    estado, _, ubicacion = http(
        f"{apis['clientes']}/clientes/{cliente['cliente_id']}/ubicaciones", "POST", token,
        {"nombre": "Oficina", "direccion": "Av. Prueba 123", "distrito": "Miraflores"},
    )
    assert estado == 201, ubicacion

    datos = {
        "cliente_id": cliente["cliente_id"], "ubicacion_id": ubicacion["ubicacion_id"],
        "tipo_servicio": "REPARACION", "descripcion": "No enfría", "prioridad": "ALTA",
    }
    clave = {"Idempotency-Key": str(uuid.uuid4())}
    estado, _, orden = http(f"{apis['ordenes']}/ordenes", "POST", token, datos, clave)
    assert estado == 201, orden
    assert orden["cliente_nombre"] == cliente["nombre"] and orden["direccion"] == "Av. Prueba 123"

    # Repetir devuelve la misma orden
    _, _, repetida = http(f"{apis['ordenes']}/ordenes", "POST", token, datos, clave)
    assert repetida["orden_id"] == orden["orden_id"]

    # FríoSur no la ve aunque conozca el ID, ni puede usar ese cliente
    ajeno = token_de("FRIOSUR")
    assert http(f"{apis['ordenes']}/ordenes/{orden['orden_id']}", token=ajeno)[0] == 404
    estado, _, error = http(f"{apis['ordenes']}/ordenes", "POST", ajeno, datos)
    assert estado == 404, error

    # Cambio de prioridad con control de versión
    ruta = f"{apis['ordenes']}/ordenes/{orden['orden_id']}"
    assert http(ruta, "PATCH", token, {"prioridad": "BAJA", "version": 1})[0] == 200
    assert http(ruta, "PATCH", token, {"prioridad": "ALTA", "version": 1})[0] == 409
    _, _, historial = http(f"{ruta}/historial", token=token)
    assert historial["items"][-1]["tipo"] == "ORDEN_CREADA"
