"""Agenda contra AWS real. La concurrencia usa 5 hilos como máximo: comprueba reglas, no es una prueba de carga."""
import datetime
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from apoyo import http, url_servicio

HILOS = 5
TECNICO = "TEC-CLIMALIMA-DEMO"


@pytest.fixture(scope="module")
def apis():
    return {s: url_servicio(s) for s in ("clientes", "ordenes", "agenda", "tecnicos")}


def manana_mas(dias):
    lima = datetime.timezone(datetime.timedelta(hours=-5))
    return (datetime.datetime.now(lima).date() + datetime.timedelta(days=dias)).isoformat()


def utc(fecha, hora):
    return (datetime.datetime.fromisoformat(f"{fecha}T{hora}:00-05:00").astimezone(datetime.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture(scope="module")
def nueva_orden(apis, token_de):
    token = token_de("CLIMALIMA")
    _, _, cliente = http(f"{apis['clientes']}/clientes", "POST", token, {"nombre": f"Prueba agenda {uuid.uuid4().hex[:6]}"})
    _, _, ubicacion = http(f"{apis['clientes']}/clientes/{cliente['cliente_id']}/ubicaciones", "POST", token,
                           {"nombre": "Local", "direccion": "Av. Prueba", "distrito": "Surco"})

    def crear():
        estado, _, orden = http(f"{apis['ordenes']}/ordenes", "POST", token, {
            "cliente_id": cliente["cliente_id"], "ubicacion_id": ubicacion["ubicacion_id"],
            "tipo_servicio": "REPARACION", "descripcion": "Prueba", "prioridad": "MEDIA",
        })
        assert estado == 201, orden
        return orden["orden_id"]

    return crear


def dia_y_hora(apis, token, desde_dias, duracion=60):
    """El primer día desde `desde_dias` en que el técnico de demo tiene una hora libre: las pruebas
    repetidas van llenando su agenda."""
    for dias in range(desde_dias, 29):
        fecha = manana_mas(dias)
        estado, _, datos = http(f"{apis['agenda']}/disponibilidad?fecha={fecha}&especialidad=REPARACION&duracion_min={duracion}", token=token)
        assert estado == 200, datos
        opcion = next((o for o in datos["items"] if o["tecnico_id"] == TECNICO), None)
        if opcion and opcion["horarios"]:
            return fecha, opcion["horarios"][-1]
    pytest.skip("El técnico de demo no tiene horas libres en sus próximas jornadas")


def programar(apis, token, orden, fecha, hora, fin_hora):
    return http(f"{apis['agenda']}/visitas", "POST", token, {
        "orden_id": orden, "tecnico_id": TECNICO, "inicio": utc(fecha, hora), "fin": utc(fecha, fin_hora),
    })


def fin_de(hora):
    h = int(hora[:2]) + 1
    return f"{h:02d}:{hora[3:]}"


@pytest.mark.muta
def test_reserva_concurrente_confirma_exactamente_una(apis, token_de, nueva_orden):
    token = token_de("CLIMALIMA")
    fecha, hora = dia_y_hora(apis, token, 20)
    ordenes = [nueva_orden() for _ in range(HILOS)]  # Órdenes distintas: compiten solo por el bloque.

    with ThreadPoolExecutor(max_workers=HILOS) as hilos:
        resultados = list(hilos.map(lambda o: programar(apis, token, o, fecha, hora, fin_de(hora)), ordenes))

    estados = sorted(r[0] for r in resultados)
    assert estados.count(201) == 1, resultados
    assert estados.count(409) == HILOS - 1, resultados
    codigos = {r[2]["error"]["codigo"] for r in resultados if r[0] == 409}
    assert codigos <= {"HORARIO_OCUPADO", "CONFLICTO_CONCURRENTE"}


@pytest.mark.muta
def test_recorrido_de_visita_y_aislamiento(apis, token_de, nueva_orden):
    token = token_de("CLIMALIMA")
    tecnico = token_de("CLIMALIMA", "TECNICO")
    ajeno = token_de("FRIOSUR")
    orden = nueva_orden()
    fecha, hora = dia_y_hora(apis, token, 21)

    estado, _, visita = programar(apis, token, orden, fecha, hora, fin_de(hora))
    assert estado == 201, visita
    ruta = f"{apis['agenda']}/visitas/{visita['visita_id']}"
    assert visita["cliente_nombre"].startswith("Prueba agenda") and visita["tecnico_nombre"]

    # El horario ya no se ofrece y otra empresa no ve la visita
    _, _, datos = http(f"{apis['agenda']}/disponibilidad?fecha={fecha}&especialidad=REPARACION&duracion_min=60", token=token)
    opcion = next(o for o in datos["items"] if o["tecnico_id"] == TECNICO)
    assert hora not in opcion["horarios"]
    assert http(ruta, token=ajeno)[0] == 404

    # Mis visitas: el técnico la ve con el destino, y no puede pedir las de otro
    _, _, mias = http(f"{apis['agenda']}/visitas?fecha={fecha}&tecnico_id=OTRO", token=tecnico)
    assert visita["visita_id"] in [v["visita_id"] for v in mias["items"]]
    assert mias["items"][0]["direccion"] == "Av. Prueba"

    # Cerrar la orden con una visita activa se rechaza (cancelarla cancela sus visitas: ver test_automatizacion_aws)
    estado, _, error = http(f"{apis['ordenes']}/ordenes/{orden}/cerrar", "POST", token)
    assert estado == 409, error

    # Reprogramar con versión antigua falla y conserva lo anterior
    assert http(f"{ruta}/reprogramar", "POST", token, {"inicio": visita["inicio"], "fin": visita["fin"], "version": 99})[0] == 409

    # Iniciar bloquea la cancelación normal
    estado, _, iniciada = http(f"{ruta}/iniciar", "POST", tecnico)
    assert estado == 200 and iniciada["estado"] == "EN_ATENCION"
    assert http(f"{ruta}/cancelar", "POST", token)[0] == 409
    # Con una visita en atención, cancelar la orden se rechaza y la orden no queda a medias
    estado, _, error = http(f"{apis['ordenes']}/ordenes/{orden}/cancelar", "POST", token)
    # Según si ya llegó VisitaIniciada a Órdenes, lo detiene el estado de la orden o el bloqueo de Agenda.
    assert estado == 409 and error["error"]["codigo"] in ("ESTADO_NO_PERMITE", "VISITA_EN_ATENCION"), error
    _, _, detalle = http(f"{apis['ordenes']}/ordenes/{orden}", token=token)
    assert detalle["estado"] not in ("CANCELADA", "CIERRE_EN_PROCESO")


@pytest.mark.muta
def test_cancelar_visita_libera_el_horario_y_permite_cancelar_la_orden(apis, token_de, nueva_orden):
    token = token_de("CLIMALIMA")
    orden = nueva_orden()
    fecha, hora = dia_y_hora(apis, token, 22)
    estado, _, visita = programar(apis, token, orden, fecha, hora, fin_de(hora))
    assert estado == 201, visita

    ruta = f"{apis['agenda']}/visitas/{visita['visita_id']}/cancelar"
    assert http(ruta, "POST", token)[0] == 200
    assert http(ruta, "POST", token)[0] == 200  # Repetir no vuelve a restar

    estado, _, cancelada = http(f"{apis['ordenes']}/ordenes/{orden}/cancelar", "POST", token)
    assert estado == 200 and cancelada["estado"] == "CANCELADA", cancelada

    # La orden bloqueada ya no admite visitas
    estado, _, error = programar(apis, token, orden, fecha, hora, fin_de(hora))
    assert estado == 409, error


@pytest.mark.muta
def test_cierre_concurrente_con_reserva_nunca_ambos(apis, token_de, nueva_orden):
    token = token_de("CLIMALIMA")
    orden = nueva_orden()
    fecha, hora = dia_y_hora(apis, token, 23)

    with ThreadPoolExecutor(max_workers=2) as hilos:
        cancelacion = hilos.submit(http, f"{apis['ordenes']}/ordenes/{orden}/cancelar", "POST", token)
        reserva = hilos.submit(programar, apis, token, orden, fecha, hora, fin_de(hora))
    estado_cancelar, estado_reservar = cancelacion.result()[0], reserva.result()[0]
    assert not (estado_cancelar == 200 and estado_reservar == 201), (cancelacion.result(), reserva.result())
