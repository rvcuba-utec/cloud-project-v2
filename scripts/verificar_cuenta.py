"""Comprueba en la cuenta real las piezas del diseño. No usa carga: pocas peticiones, en secuencia."""
import io
import json
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone

import boto3

STAGE = "verif"
TOKEN = "token-de-verificacion"
cf = boto3.client("cloudformation")
resultados = []


def salidas(pila):
    datos = cf.describe_stacks(StackName=pila)["Stacks"][0].get("Outputs", [])
    return {s["OutputKey"]: s["OutputValue"] for s in datos}


def peticion(url, metodo="GET", cabeceras=None, datos=None):
    req = urllib.request.Request(url, method=metodo, headers=cabeceras or {}, data=datos)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def comprobar(numero, nombre, funcion):
    print(f"[{numero}] {nombre} ...", flush=True)
    try:
        detalle = funcion()
        resultados.append((numero, nombre, "CORRECTO", detalle or ""))
    except Exception as error:  # Cada prueba es independiente: un fallo no detiene las demás.
        resultados.append((numero, nombre, "FALLO", f"{type(error).__name__}: {error}"[:300]))
    print(f"    {resultados[-1][2]} {resultados[-1][3]}", flush=True)


def esperar(condicion, segundos, intervalo=5):
    limite = time.time() + segundos
    while time.time() < limite:
        valor = condicion()
        if valor:
            return valor
        time.sleep(intervalo)
    return None


cuenta = boto3.client("sts").get_caller_identity()["Account"]
pila = salidas(f"trazora-verif-{STAGE}")
API = pila["ServiceEndpoint"]
tabla = boto3.resource("dynamodb").Table(f"{STAGE}-t_verificacion")
existe = lambda sk: "Item" in tabla.get_item(Key={"PK": "VERIF", "SK": sk})
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def amplify():
    cliente = boto3.client("amplify")
    app = cliente.create_app(name=f"trazora-verif-{int(time.time())}", platform="WEB")["app"]["appId"]
    try:
        cliente.create_branch(appId=app, branchName="main")
        despliegue = cliente.create_deployment(appId=app, branchName="main")
        memoria = io.BytesIO()
        with zipfile.ZipFile(memoria, "w") as z:
            z.writestr("index.html", "<h1>Verificación de Trazora</h1>")
        estado, _, _ = peticion(despliegue["zipUploadUrl"], "PUT", datos=memoria.getvalue())
        assert estado == 200, f"subida HTTP {estado}"
        cliente.start_deployment(appId=app, branchName="main", jobId=despliegue["jobId"])

        def terminado():
            valor = cliente.get_job(appId=app, branchName="main", jobId=despliegue["jobId"])["job"]["summary"]["status"]
            return valor if valor in ("SUCCEED", "FAILED", "CANCELLED") else None

        final = esperar(terminado, 120)
        assert final == "SUCCEED", f"trabajo {final}"
        url = f"https://main.{app}.amplifyapp.com"
        codigo = esperar(lambda: peticion(url)[0] == 200, 60)
        assert codigo, "la URL no respondió 200"
        return "publica por CLI y la web responde"
    finally:
        cliente.delete_app(appId=app)


def autorizador():
    assert peticion(f"{API}/protegido")[0] == 401, "sin token debe dar 401"
    estado, cabeceras, _ = peticion(f"{API}/protegido", cabeceras={"Authorization": "Bearer malo"})
    assert estado == 401, f"token malo dio {estado}"
    assert cabeceras.get("Access-Control-Allow-Origin") == "*" or cabeceras.get("access-control-allow-origin") == "*", "401 sin CORS"
    estado, _, cuerpo = peticion(f"{API}/protegido", cabeceras=AUTH)
    assert estado == 200, f"token válido dio {estado}: {cuerpo[:200]}"
    assert json.loads(cuerpo)["tenant_id"] == "VERIF"
    estado, _, _ = peticion(f"{API}/protegido", "POST", cabeceras=AUTH)  # Caché: otro método, misma política
    assert estado == 200, f"con caché dio {estado}"
    return "401 con CORS, contexto y caché entre rutas"


def cors_previo():
    estado, cabeceras, _ = peticion(f"{API}/protegido", "OPTIONS", cabeceras={
        "Origin": "https://ejemplo.amplifyapp.com",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,idempotency-key,content-type",
    })
    permitidas = {k.lower(): v for k, v in cabeceras.items()}.get("access-control-allow-headers", "")
    assert estado == 200, f"OPTIONS dio {estado}"
    assert "idempotency-key" in permitidas.lower(), f"permitidas: {permitidas}"
    return "permite Idempotency-Key"


def transaccion_e_invoke():
    estado, _, cuerpo = peticion(f"{API}/protegido", cabeceras=AUTH)
    assert estado == 200, cuerpo[:200]
    datos = json.loads(cuerpo)
    assert datos["invocacion"] == {"recibido": "ok"}, datos
    assert existe("TX#1") and existe("TX#2")
    return "TransactWriteItems y lambda.invoke con LabRole"


def publicar(accion, tipo, identificador):
    boto3.client("sns").publish(
        TopicArn=pila["TopicArn"],
        Message=json.dumps({"accion": accion, "id": identificador}),
        MessageAttributes={"event_type": {"DataType": "String", "StringValue": tipo}},
    )


def sns_sqs():
    publicar("guardar", "Aceptado", "A")
    publicar("guardar", "Ignorado", "B")
    assert esperar(lambda: existe("SQS#A"), 60), "el mensaje aceptado no llegó"
    time.sleep(10)
    assert not existe("SQS#B"), "el filtro dejó pasar un mensaje"
    return "fan-out con filtro por event_type, declarado en YML"


def dlq():
    publicar("fallar", "Fallido", "C")
    sqs = boto3.client("sqs")

    def en_dlq():
        r = sqs.receive_message(QueueUrl=pila["ColaFallidosUrl"], WaitTimeSeconds=5)
        return bool(r.get("Messages"))

    assert esperar(en_dlq, 150), "el mensaje no llegó a la DLQ"
    return "mensaje fallido en la DLQ tras los reintentos"


def s3_prefirmado():
    estado, _, cuerpo = peticion(f"{API}/firmar", "POST", cabeceras=AUTH)
    assert estado == 200, cuerpo[:200]
    firma = json.loads(cuerpo)

    previo, cabeceras, _ = peticion(firma["url"], "OPTIONS", cabeceras={
        "Origin": "https://ejemplo.amplifyapp.com", "Access-Control-Request-Method": "POST",
    })
    assert previo == 200, f"CORS del bucket: HTTP {previo}"

    def subir(tamano):
        with tempfile.NamedTemporaryFile(suffix=".jpg") as archivo:
            archivo.write(b"0" * tamano)
            archivo.flush()
            orden = ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "-X", "POST"]
            for clave, valor in firma["fields"].items():
                orden += ["--form-string", f"{clave}={valor}"]
            orden += ["-F", f"file=@{archivo.name};type=image/jpeg", firma["url"]]
            return subprocess.run(orden, capture_output=True, text=True, timeout=60).stdout

    excedido = subir(2 * 1024 * 1024)
    assert excedido in ("400", "403"), f"el límite de tamaño no se aplicó: HTTP {excedido}"
    correcto = subir(1024)
    assert correcto == "204", f"subida válida: HTTP {correcto}"
    return "POST prefirmado, CORS y límite de tamaño"


def notificacion_s3():
    assert esperar(lambda: existe("S3#1"), 45), "la Lambda no recibió la notificación"
    item = tabla.get_item(Key={"PK": "VERIF", "SK": "S3#1"})["Item"]
    assert item["tenant"] == "VERIF"
    return "notificación S3 con bucket en provider.s3"


def eventbridge():
    assert esperar(lambda: existe("EVENTBRIDGE#1"), 130), "la regla no invocó la Lambda"
    return "evento schedule declarado en YML"


def concurrencia():
    ajustes = boto3.client("lambda").get_account_settings()["AccountLimit"]
    return f"límite de concurrencia: {ajustes['ConcurrentExecutions']}"


comprobar(0, "Amplify sin Git, por CLI", amplify)
comprobar(1, "Autorizador en otro stack", autorizador)
comprobar(2, "CORS previo con Idempotency-Key", cors_previo)
comprobar(3, "Transacciones y lambda.invoke", transaccion_e_invoke)
comprobar(4, "SNS a SQS con filtro", sns_sqs)
comprobar(5, "SQS a Lambda con DLQ", dlq)
comprobar(6, "S3: POST prefirmado y CORS", s3_prefirmado)
comprobar(7, "S3: notificación a Lambda", notificacion_s3)
comprobar(8, "EventBridge programado", eventbridge)
comprobar(9, "Límite de concurrencia", concurrencia)

fecha = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
lineas = [
    "# Verificación de la cuenta de AWS Academy", "", f"Región: `{os.environ.get('AWS_REGION')}`. Ejecutada: {fecha}.", "",
    "| # | Prueba | Resultado | Detalle |", "|---|---|---|---|",
]
lineas += [f"| {n} | {a} | {r} | {str(d).replace(cuenta, '<cuenta>').replace('|', '/')} |" for n, a, r, d in resultados]
lineas += ["", "**Manual:** comprobar si la API y la web responden con el laboratorio detenido."]
os.makedirs("docs/evidencias", exist_ok=True)
with open("docs/evidencias/verificacion-cuenta.md", "w", encoding="utf-8") as salida:
    salida.write("\n".join(lineas) + "\n")

fallos = [r for r in resultados if r[2] != "CORRECTO"]
print(f"\n{len(resultados) - len(fallos)}/{len(resultados)} correctas. Informe: docs/evidencias/verificacion-cuenta.md")
raise SystemExit(1 if fallos else 0)
