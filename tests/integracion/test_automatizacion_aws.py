"""Automatizaciones contra AWS real: reasignación por ausencia, cancelación en cascada, mapa y filtros."""
import datetime
import time
import uuid

import pytest

from apoyo import http, url_servicio

TECNICO = "TEC-CLIMALIMA-DEMO"
LIMA = datetime.timezone(datetime.timedelta(hours=-5))


@pytest.fixture(scope="module")
def apis():
    return {s: url_servicio(s) for s in ("clientes", "ordenes", "agenda", "tecnicos", "usuarios")}


def utc(fecha, hora, minutos=0):
    instante = datetime.datetime.fromisoformat(f"{fecha}T{hora}:00-05:00") + datetime.timedelta(minutes=minutos)
    return instante.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def esperar(funcion, segundos=60):
    limite = time.time() + segundos
    while True:
        valor = funcion()
        if valor or time.time() > limite:
            return valor
        time.sleep(2)


@pytest.fixture(scope="module")
def nueva_orden(apis, token_de):
    admin = token_de("CLIMALIMA")
    _, _, cliente = http(f"{apis['clientes']}/clientes", "POST", admin, {"nombre": f"Prueba automática {uuid.uuid4().hex[:6]}"})
    _, _, ubicacion = http(f"{apis['clientes']}/clientes/{cliente['cliente_id']}/ubicaciones", "POST", admin,
                           {"nombre": "Local", "direccion": "Av. Prueba", "distrito": "Surco", "lat": -12.1459, "lng": -76.9916})

    def crear():
        estado, _, orden = http(f"{apis['ordenes']}/ordenes", "POST", admin, {
            "cliente_id": cliente["cliente_id"], "ubicacion_id": ubicacion["ubicacion_id"],
            "tipo_servicio": "REPARACION", "descripcion": "Prueba", "prioridad": "ALTA",
        })
        assert estado == 201, orden
        return orden

    return crear


def programar(apis, token, orden_id, fecha, hora, minutos=30):
    return http(f"{apis['agenda']}/visitas", "POST", token, {
        "orden_id": orden_id, "tecnico_id": TECNICO, "inicio": utc(fecha, hora), "fin": utc(fecha, hora, minutos),
    })


def dia_sin_ausencia(apis, token):
    """El primer día próximo en que el técnico de demo trabaja, otros también, y aún no está ausente."""
    hoy = datetime.datetime.now(LIMA).date()
    for i in range(1, 10):
        fecha = (hoy + datetime.timedelta(days=i)).isoformat()
        _, _, datos = http(f"{apis['agenda']}/disponibilidad?fecha={fecha}&especialidad=REPARACION&duracion_min=30", token=token)
        ids = [o["tecnico_id"] for o in datos.get("items", [])]
        if TECNICO in ids and len(ids) > 1:
            return fecha, next(o for o in datos["items"] if o["tecnico_id"] == TECNICO)["horarios"]
    pytest.skip("No queda un día próximo con el técnico de demo disponible")


@pytest.mark.muta
def test_ausencia_reasigna_sola_al_mejor_tecnico(apis, token_de, nueva_orden):
    admin = token_de("CLIMALIMA")
    fecha, horarios = dia_sin_ausencia(apis, admin)
    orden = nueva_orden()
    estado, _, visita = programar(apis, admin, orden["orden_id"], fecha, horarios[0])
    assert estado == 201, visita

    estado, _, ausencia = http(f"{apis['tecnicos']}/tecnicos/{TECNICO}/ausencias/{fecha}", "PUT", admin, {"motivo": "Prueba de reasignación"})
    assert estado == 201, ausencia

    ruta = f"{apis['agenda']}/visitas/{visita['visita_id']}"
    final = esperar(lambda: (lambda v: v if v["tecnico_id"] != TECNICO or v.get("requiere_reprogramacion") else None)(http(ruta, token=admin)[2]))
    assert final, "Agenda no procesó TecnicoAusente"
    _, _, alertas = http(f"{apis['agenda']}/alertas", token=admin)
    if final.get("requiere_reprogramacion"):
        assert visita["visita_id"] in [a["visita_id"] for a in alertas["pendientes"]]
    else:
        assert final["reasignada_automaticamente"] is True and final["estado"] == "PROGRAMADA"
        assert any(a["visita_id"] == visita["visita_id"] and a["tipo"] == "REASIGNADA" for a in alertas["recientes"])
        # Órdenes registra que fue automática.
        historial = esperar(lambda: [h for h in http(f"{apis['ordenes']}/ordenes/{orden['orden_id']}/historial", token=admin)[2]["items"] if "reasignada sola" in h["detalle"]])
        assert historial, "Órdenes no registró la reasignación"

    # Registrar la misma ausencia otra vez no vuelve a publicar ni a reasignar.
    assert http(f"{apis['tecnicos']}/tecnicos/{TECNICO}/ausencias/{fecha}", "PUT", admin, {"motivo": "x"})[0] == 200


@pytest.mark.muta
def test_cancelar_orden_cancela_sus_visitas_programadas(apis, token_de, nueva_orden):
    admin = token_de("CLIMALIMA")
    fecha = (datetime.datetime.now(LIMA).date() + datetime.timedelta(days=24)).isoformat()
    _, _, datos = http(f"{apis['agenda']}/disponibilidad?fecha={fecha}&especialidad=REPARACION&duracion_min=30", token=admin)
    horarios = next(o for o in datos["items"] if o["tecnico_id"] == TECNICO)["horarios"]
    orden = nueva_orden()
    visitas = [programar(apis, admin, orden["orden_id"], fecha, h)[2] for h in horarios[:2]]
    assert all("visita_id" in v for v in visitas), visitas

    estado, _, cancelada = http(f"{apis['ordenes']}/ordenes/{orden['orden_id']}/cancelar", "POST", admin)
    assert estado == 200 and cancelada["estado"] == "CANCELADA" and cancelada["visitas_canceladas"] == 2, cancelada
    for v in visitas:
        assert http(f"{apis['agenda']}/visitas/{v['visita_id']}", token=admin)[2]["estado"] == "CANCELADA"


def test_mapa_alertas_y_filtros_de_usuarios(apis, token_de):
    admin = token_de("CLIMALIMA")
    estado, _, mapa = http(f"{apis['ordenes']}/ordenes/mapa", token=admin)
    assert estado == 200 and "conteo" in mapa and all({"lat", "lng"} <= p.keys() for p in mapa["puntos"])
    assert http(f"{apis['agenda']}/alertas", token=admin)[0] == 200
    assert http(f"{apis['agenda']}/alertas", token=token_de("CLIMALIMA", "TECNICO"))[0] == 403
    estado, _, admins = http(f"{apis['usuarios']}/usuarios?rol=ADMIN&estado=ACTIVO", token=admin)
    assert estado == 200 and admins["items"] and {u["rol"] for u in admins["items"]} == {"ADMIN"}
    assert http(f"{apis['usuarios']}/usuarios?rol=JEFE", token=admin)[0] == 400
