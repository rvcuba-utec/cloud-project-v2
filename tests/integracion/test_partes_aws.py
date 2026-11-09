"""Atención completa contra AWS real: parte, foto en S3, notificación y finalización."""
import datetime
import json
import os
import time
import urllib.error
import urllib.request
import uuid

import boto3
import pytest

from apoyo import http, url_servicio

TECNICO = "TEC-CLIMALIMA-DEMO"
ORIGEN = "http://localhost:5173"
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 2048 + b"\xff\xd9"


@pytest.fixture(scope="module")
def apis():
    return {s: url_servicio(s) for s in ("clientes", "ordenes", "agenda", "partes", "analitica")}


def utc(fecha, hora):
    instante = datetime.datetime.fromisoformat(f"{fecha}T{hora}:00-05:00")
    return instante.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def formulario(firma, contenido, tipo="image/jpeg"):
    """Igual que el navegador: los campos firmados primero y el archivo al final."""
    limite = uuid.uuid4().hex
    cuerpo = b""
    for nombre, valor in firma["fields"].items():
        cuerpo += f'--{limite}\r\nContent-Disposition: form-data; name="{nombre}"\r\n\r\n{valor}\r\n'.encode()
    cuerpo += f'--{limite}\r\nContent-Disposition: form-data; name="file"; filename="f"\r\nContent-Type: {tipo}\r\n\r\n'.encode()
    return cuerpo + contenido + f"\r\n--{limite}--\r\n".encode(), f"multipart/form-data; boundary={limite}"


def subir_a_s3(firma, contenido):
    cuerpo, tipo = formulario(firma, contenido)
    peticion = urllib.request.Request(firma["url"], data=cuerpo, method="POST", headers={"Content-Type": tipo, "Origin": ORIGEN})
    try:
        with urllib.request.urlopen(peticion, timeout=60) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}
    except urllib.error.HTTPError as e:
        return e.code, {}


@pytest.fixture(scope="module")
def nueva_visita(apis, token_de):
    """Orden nueva con una visita en atención."""
    admin, tecnico = token_de("CLIMALIMA"), token_de("CLIMALIMA", "TECNICO")
    _, _, cliente = http(f"{apis['clientes']}/clientes", "POST", admin, {"nombre": f"Prueba partes {uuid.uuid4().hex[:6]}"})
    _, _, ubicacion = http(f"{apis['clientes']}/clientes/{cliente['cliente_id']}/ubicaciones", "POST", admin,
                           {"nombre": "Local", "direccion": "Av. Prueba", "distrito": "Surco"})

    def crear(dias):
        _, _, orden = http(f"{apis['ordenes']}/ordenes", "POST", admin, {
            "cliente_id": cliente["cliente_id"], "ubicacion_id": ubicacion["ubicacion_id"],
            "tipo_servicio": "REPARACION", "descripcion": "Prueba", "prioridad": "MEDIA",
        })
        lima = datetime.timezone(datetime.timedelta(hours=-5))
        for extra in range(dias, 29):  # Las pruebas repetidas van llenando la agenda del técnico de demo.
            fecha = (datetime.datetime.now(lima).date() + datetime.timedelta(days=extra)).isoformat()
            estado, _, opciones = http(f"{apis['agenda']}/disponibilidad?fecha={fecha}&especialidad=REPARACION&duracion_min=30", token=admin)
            assert estado == 200, opciones
            opcion = next((o for o in opciones["items"] if o["tecnico_id"] == TECNICO), None)
            if opcion and opcion["horarios"]:
                hora = opcion["horarios"][0]
                break
        else:
            pytest.skip("El técnico de demo no tiene horas libres en sus próximas jornadas")
        fin = (datetime.datetime.fromisoformat(f"{fecha}T{hora}:00") + datetime.timedelta(minutes=30)).strftime("%H:%M")
        estado, _, visita = http(f"{apis['agenda']}/visitas", "POST", admin, {
            "orden_id": orden["orden_id"], "tecnico_id": TECNICO, "inicio": utc(fecha, hora), "fin": utc(fecha, fin),
        })
        assert estado == 201, visita
        estado, _, visita = http(f"{apis['agenda']}/visitas/{visita['visita_id']}/iniciar", "POST", tecnico)
        assert estado == 200, visita
        return visita

    return crear


def esperar(funcion, segundos=60):
    """Los eventos llegan en segundos: consulta hasta que se cumple o se agota el tiempo."""
    limite = time.time() + segundos
    while True:
        valor = funcion()
        if valor or time.time() > limite:
            return valor
        time.sleep(2)


def metricas_demo(apis, token):
    _, _, datos = http(f"{apis['analitica']}/analitica/tecnicos", token=token)
    return next((m for m in datos["items"] if m["tecnico_id"] == TECNICO), {})


@pytest.mark.muta
def test_atencion_completa_con_foto(apis, token_de, nueva_visita):
    tecnico, admin = token_de("CLIMALIMA", "TECNICO"), token_de("CLIMALIMA")
    visita_id = nueva_visita(dias=21)["visita_id"]
    antes = metricas_demo(apis, admin).get("visitas_completadas_total", 0)
    url = apis["partes"]

    estado, _, parte = http(f"{url}/visitas/{visita_id}/partes", "POST", tecnico)
    assert estado == 201, parte
    assert http(f"{url}/visitas/{visita_id}/partes", "POST", tecnico)[2]["parte_id"] == parte["parte_id"]
    parte_id = parte["parte_id"]

    # Otra empresa no lo ve.
    assert http(f"{url}/partes/{parte_id}", token=token_de("FRIOSUR"))[0] == 404

    estado, _, firma = http(f"{url}/partes/{parte_id}/evidencias", "POST", tecnico, {"content_type": "image/jpeg", "nombre": "f.jpg"})
    assert estado == 201, firma

    # Más de 5 MB: lo rechaza S3, no el navegador.
    estado, _ = subir_a_s3(firma, b"0" * (5 * 1024 * 1024 + 1))
    assert estado == 400

    estado, cabeceras = subir_a_s3(firma, JPEG)
    assert estado == 204
    assert cabeceras.get("access-control-allow-origin") == ORIGEN  # CORS real del bucket

    foto = None
    for _ in range(15):  # La notificación de S3 suele tardar menos de un segundo.
        _, _, detalle = http(f"{url}/partes/{parte_id}", token=tecnico)
        foto = next((e for e in detalle["evidencias"] if e["evidencia_id"] == firma["evidencia_id"]), None)
        if foto and foto["estado"] == "CONFIRMADA":
            break
        time.sleep(2)
    assert foto and foto["estado"] == "CONFIRMADA", "La notificación de S3 no confirmó la evidencia"

    with urllib.request.urlopen(foto["url"], timeout=30) as r:
        assert r.read() == JPEG

    # El objeto no se puede leer sin firma.
    sin_firma = foto["url"].split("?")[0]
    with pytest.raises(urllib.error.HTTPError) as error:
        urllib.request.urlopen(sin_firma, timeout=30)
    assert error.value.code == 403

    estado, _, incompleto = http(f"{url}/partes/{parte_id}/finalizar", "POST", tecnico, {"version": parte["version"]})
    assert estado == 409 and incompleto["error"]["codigo"] == "PARTE_INCOMPLETO"

    estado, _, editado = http(f"{url}/partes/{parte_id}", "PUT", tecnico, {
        "version": parte["version"], "diagnostico": "Filtro obstruido", "tareas": ["Limpieza"], "resultado": "RESUELTO",
    })
    assert estado == 200, editado

    estado, _, final = http(f"{url}/partes/{parte_id}/finalizar", "POST", tecnico, {"version": editado["version"]})
    assert estado == 200 and final["estado"] == "FINALIZADO", final
    estado, _, repetido = http(f"{url}/partes/{parte_id}/finalizar", "POST", tecnico, {"version": editado["version"]})
    assert estado == 200 and repetido["finalizado_en"] == final["finalizado_en"]
    assert http(f"{url}/visitas/{visita_id}/partes", "POST", tecnico)[0] == 409
    assert http(f"{url}/partes/{parte_id}/evidencias", "POST", tecnico, {"content_type": "image/png"})[0] == 409

    # El coordinador lo consulta desde la orden.
    estado, _, lista = http(f"{url}/partes?orden_id={final['orden_id']}", token=admin)
    assert estado == 200 and [p["parte_id"] for p in lista["items"]] == [parte_id]

    # Los eventos cierran el ciclo: Agenda termina la visita y Órdenes deriva su estado.
    ruta_visita = f"{apis['agenda']}/visitas/{visita_id}"
    assert esperar(lambda: http(ruta_visita, token=admin)[2]["estado"] == "FINALIZADA"), "Agenda no aplicó ParteFinalizado"
    ruta_orden = f"{apis['ordenes']}/ordenes/{final['orden_id']}"
    assert esperar(lambda: http(ruta_orden, token=admin)[2]["estado"] == "PENDIENTE_DE_CIERRE"), "Órdenes no derivó el estado"
    _, _, historial = http(f"{ruta_orden}/historial", token=admin)
    tipos = [h["tipo"] for h in historial["items"]]
    assert {"VisitaCompletada", "PARTE_FINALIZADO"} <= set(tipos), tipos

    assert esperar(lambda: metricas_demo(apis, admin).get("visitas_completadas_total", 0) == antes + 1), "Analítica no contó la visita"

    estado, _, cerrada = http(f"{ruta_orden}/cerrar", "POST", admin)
    assert estado == 200 and cerrada["estado"] == "CERRADA", cerrada


@pytest.mark.muta
def test_evento_sin_publicar_llega_con_el_barrido_y_el_duplicado_no_cambia_nada(apis, token_de, nueva_visita):
    """Simula que la Lambda murió entre guardar y publicar: el evento queda solo en el OUTBOX."""
    admin = token_de("CLIMALIMA")
    visita = nueva_visita(dias=23)
    stage = os.environ.get("STAGE", "dev")
    evento = {
        "event_id": str(uuid.uuid4()), "event_type": "ParteFinalizado", "schema_version": 1, "tenant_id": "CLIMALIMA",
        "aggregate_type": "PARTE", "aggregate_id": f"PAR-{uuid.uuid4()}", "aggregate_version": 2,
        "occurred_at": "2026-11-27T13:30:00Z", "correlation_id": visita["orden_id"],
        "data": {"parte_id": "PAR-prueba", "visita_id": visita["visita_id"], "orden_id": visita["orden_id"],
                 "tecnico_id": TECNICO, "resultado": "RESUELTO",
                 "finalizado_en": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
    }
    tabla = boto3.resource("dynamodb").Table(f"{stage}-t_partes")
    clave = {"PK": "TENANT#CLIMALIMA", "SK": f"OUTBOX#{evento['event_id']}"}
    tabla.put_item(Item={**clave, "entity_type": "OUTBOX", "evento": evento})

    boto3.client("lambda").invoke(FunctionName=f"api-partes-{stage}-barrerOutbox", Payload=b"{}")
    assert "Item" not in tabla.get_item(Key=clave, ConsistentRead=True)

    ruta_visita = f"{apis['agenda']}/visitas/{visita['visita_id']}"
    assert esperar(lambda: http(ruta_visita, token=admin)[2]["estado"] == "FINALIZADA"), "El barrido no entregó el evento"
    ruta_orden = f"{apis['ordenes']}/ordenes/{visita['orden_id']}"
    assert esperar(lambda: http(ruta_orden, token=admin)[2]["estado"] == "PENDIENTE_DE_CIERRE")

    # El mismo evento otra vez: la visita no vuelve a restar del contador.
    agenda = boto3.resource("dynamodb").Table(f"{stage}-t_agenda")
    control = {"PK": "TENANT#CLIMALIMA", "SK": f"CONTROL_ORDEN#{visita['orden_id']}"}
    temas = boto3.client("cloudformation").describe_stacks(StackName=f"trazora-shared-{stage}")["Stacks"][0]["Outputs"]
    boto3.client("sns").publish(
        TopicArn=next(o["OutputValue"] for o in temas if o["OutputKey"] == "TopicArn"),
        Message=json.dumps(evento),
        MessageAttributes={"event_type": {"DataType": "String", "StringValue": "ParteFinalizado"},
                           "tenant_id": {"DataType": "String", "StringValue": "CLIMALIMA"}},
    )
    time.sleep(10)
    assert agenda.get_item(Key=control, ConsistentRead=True)["Item"]["visitas_activas"] == 0
    _, _, historial = http(f"{ruta_orden}/historial", token=admin)
    assert [h["tipo"] for h in historial["items"]].count("PARTE_FINALIZADO") == 1
