"""Recorre los siete servicios con las plantillas de dev empaquetadas por validar_ingreso.py y Moto."""
import argparse
import importlib
import io
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta
from fnmatch import fnmatchcase
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import quote_plus, urlsplit
from zoneinfo import ZoneInfo

import boto3
import requests
from moto import mock_aws

from validar_ambientes import RAIZ, SERVICIOS, exigir, parametros
from validar_ingreso import propiedades


class IngresoLocal:
    def __init__(self, plantillas):
        self.funciones = {}
        self.rutas = []
        self.colas = {}
        self.sqs = boto3.client("sqs")
        sns = boto3.client("sns")
        ddb = boto3.client("dynamodb")
        autorizador, = propiedades(plantillas["shared"], "ApiGateway::Authorizer").values()
        uri = autorizador["AuthorizerUri"]["Fn::Sub"]
        self.nombre_autorizador = uri.removesuffix("/invocations").rsplit(":function:", 1)[1]
        nombre_tema = plantillas["shared"]["TemaEventos"]["Properties"]["TopicName"]
        self.tema = sns.create_topic(Name=nombre_tema)["TopicArn"]
        for servicio in SERVICIOS:
            recursos = plantillas[servicio]
            for tabla in propiedades(recursos, "DynamoDB::Table").values():
                ddb.create_table(**tabla)
            for f in propiedades(recursos, "Lambda::Function").values():
                self.funciones[f["FunctionName"]] = f
            reglas = propiedades(recursos, "ElasticLoadBalancingV2::ListenerRule")
            for mid, metodo in propiedades(recursos, "ApiGateway::Method").items():
                if metodo["HttpMethod"] == "OPTIONS":
                    continue
                regla, = (reglas[k] for k in recursos[mid]["DependsOn"] if k in reglas)
                condiciones = {c["Field"]: c for c in regla["Conditions"]}
                patron, = condiciones["path-pattern"]["PathPatternConfig"]["RegexValues"]
                verbo, = condiciones["http-request-method"]["HttpRequestMethodConfig"]["Values"]
                grupo = recursos[regla["Actions"][0]["TargetGroupArn"]["Ref"]]["Properties"]
                funcion = recursos[grupo["Targets"][0]["Id"]["Fn::GetAtt"][0]]["Properties"]["FunctionName"]
                self.rutas.append((regla["Priority"], verbo, re.compile(patron), metodo, funcion))
            for sub in propiedades(recursos, "SNS::Subscription").values():
                cola_id = sub["Endpoint"]["Fn::GetAtt"][0]
                cola = self.sqs.create_queue(QueueName=recursos[cola_id]["Properties"]["QueueName"])["QueueUrl"]
                arn = self.sqs.get_queue_attributes(QueueUrl=cola, AttributeNames=["QueueArn"])["Attributes"]["QueueArn"]
                sns.subscribe(TopicArn=self.tema, Protocol="sqs", Endpoint=arn,
                              Attributes={"FilterPolicy": json.dumps(sub["FilterPolicy"])})
                mapping, = (m for m in propiedades(recursos, "Lambda::EventSourceMapping").values()
                            if m["EventSourceArn"] == sub["Endpoint"] and m.get("Enabled", True))
                self.colas[cola] = recursos[mapping["FunctionName"]["Fn::GetAtt"][0]]["Properties"]["FunctionName"]
        self.rutas.sort(key=lambda regla: regla[0])
        partes = plantillas["partes"]
        bucket = partes["S3BucketEvidencias"]["Properties"]
        boto3.client("s3").create_bucket(Bucket=bucket["BucketName"])
        evento_s3, = bucket["NotificationConfiguration"]["LambdaConfigurations"]
        self.destino_s3 = partes[evento_s3["Function"]["Fn::GetAtt"][0]]["Properties"]["FunctionName"]

    def invocar(self, nombre, event):
        funcion = self.funciones[nombre]
        env = dict(funcion["Environment"]["Variables"])
        if "TOPIC_ARN" in env:
            env["TOPIC_ARN"] = self.tema
        modulo, handler = funcion["Handler"].replace("/", ".").rsplit(".", 1)
        with patch.dict(os.environ, env):
            codigo = importlib.import_module(f"backend.{env['SERVICE_NAME']}.{modulo}")
            return getattr(codigo, handler)(event, None)

    def enviar(self, verbo, ruta, token="", datos=None):
        from apoyo_pruebas import evento_alb

        url = urlsplit(ruta)
        path = "/dev" + url.path
        _, _, _, metodo, destino = next(r for r in self.rutas if r[1] == verbo and r[2].fullmatch(path))
        headers = {"Authorization": ["Bearer " + token]} if token else {}
        identidad = None
        if metodo["AuthorizationType"] == "CUSTOM":
            api_id = parametros("dev")["restApiId"]
            arn = f"arn:aws:execute-api:us-east-1:000000000000:{api_id}/dev/{verbo}{url.path}"
            auth = self.invocar(self.nombre_autorizador, {
                "type": "REQUEST", "methodArn": arn, "headers": {k: v[0] for k, v in headers.items()},
            })
            permiso, = auth["policyDocument"]["Statement"]
            exigir(permiso["Effect"] == "Allow" and permiso["Action"] == "execute-api:Invoke"
                   and fnmatchcase(arn, permiso["Resource"]), "El autorizador no permitió la ruta de la prueba")
            origen = metodo["Integration"]["RequestParameters"]["integration.request.header.X-Trazora-Identity"]
            identidad = auth["context"][origen.removeprefix("context.authorizer.")]
        query = {}
        for campo in url.query.split("&") if url.query else []:
            clave, _, valor = campo.partition("=")
            query.setdefault(clave, []).append(valor)
        return self.invocar(destino, evento_alb(verbo, path, identidad, headers=headers, query=query, body=datos))

    def transporte_http(self, request, timeout=None):
        # Reenvía también las llamadas síncronas reales de interno.llamar al API de esta prueba.
        url = urlsplit(request.full_url)
        origen = f"{parametros('dev')['restApiId']}.execute-api.us-east-1.amazonaws.com"
        exigir(url.netloc == origen and url.path.startswith("/dev/"), "Destino inesperado en prueba local")
        ruta = url.path.removeprefix("/dev") + ("?" + url.query if url.query else "")
        token = request.get_header("Authorization", "").removeprefix("Bearer ")
        r = self.enviar(request.get_method(), ruta, token, json.loads(request.data) if request.data else None)
        data = io.BytesIO(r["body"].encode())
        if r["statusCode"] >= 400:
            raise HTTPError(request.full_url, r["statusCode"], "Servicio local", {}, data)
        return data

    def api(self, verbo, ruta, token="", datos=None, esperado=200):
        r = self.enviar(verbo, ruta, token, datos)
        exigir(r["statusCode"] == esperado, f"{verbo} {ruta}: se esperaba {esperado}, llegó {r['statusCode']}")
        return json.loads(r["body"])

    def procesar_colas(self):
        for _ in range(20):
            recibidos = 0
            for cola, funcion in self.colas.items():
                mensajes = self.sqs.receive_message(QueueUrl=cola, MaxNumberOfMessages=10).get("Messages", [])
                for m in mensajes:
                    r = self.invocar(funcion, {"Records": [{"messageId": m["MessageId"], "body": m["Body"]}]})
                    exigir(r == {"batchItemFailures": []}, "Falló el consumidor " + funcion)
                    self.sqs.delete_message(QueueUrl=cola, ReceiptHandle=m["ReceiptHandle"])
                recibidos += len(mensajes)
            if recibidos == 0:
                return
        raise AssertionError("Las colas locales siguen generando eventos")


def recorrido(local, cuentas):
    def login(tenant, rol):
        return local.api("POST", "/auth/login", datos=cuentas[tenant, rol])["token"]

    coordinador = login("CLIMALIMA", "COORDINADOR")
    tecnico = login("CLIMALIMA", "TECNICO")
    otra_empresa = login("FRIOSUR", "COORDINADOR")
    cliente = local.api("POST", "/clientes", coordinador, {"nombre": "Cliente de prueba"}, 201)["cliente_id"]
    sede = local.api("POST", f"/clientes/{cliente}/ubicaciones", coordinador,
                     {"nombre": "Local", "direccion": "Av. Prueba", "distrito": "Surco"}, 201)
    datos_orden = {"cliente_id": cliente, "ubicacion_id": sede["ubicacion_id"], "tipo_servicio": "REPARACION",
                  "prioridad": "MEDIA", "descripcion": "Equipo de prueba"}
    orden = local.api("POST", "/ordenes", coordinador, datos_orden, 201)
    ruta_orden = "/ordenes/" + orden["orden_id"]
    local.api("GET", ruta_orden, otra_empresa, esperado=404)

    lima = ZoneInfo("America/Lima")
    fecha = (datetime.now(lima).date() + timedelta(days=1)).isoformat()
    opciones = local.api("GET", f"/disponibilidad?fecha={fecha}&especialidad=REPARACION&duracion_min=30", coordinador)
    candidato = next(t for t in opciones["items"] if t["tecnico_id"] == "TEC-CLIMALIMA-DEMO")
    inicio = datetime.fromisoformat(f"{fecha}T{candidato['horarios'][0]}:00").replace(tzinfo=lima)

    def programar(orden_id, hora):
        formato = "%Y-%m-%dT%H:%M:%SZ"
        desde = hora.astimezone(ZoneInfo("UTC"))
        return local.api("POST", "/visitas", coordinador, {"orden_id": orden_id, "tecnico_id": candidato["tecnico_id"],
                         "inicio": desde.strftime(formato), "fin": (desde + timedelta(minutes=30)).strftime(formato)}, 201)

    visita = programar(orden["orden_id"], inicio)
    ruta_visita = "/visitas/" + visita["visita_id"]
    local.procesar_colas()
    local.api("POST", ruta_visita + "/iniciar", tecnico)
    parte = local.api("POST", ruta_visita + "/partes", tecnico, esperado=201)
    ruta_parte = "/partes/" + parte["parte_id"]
    firma = local.api("POST", ruta_parte + "/evidencias", tecnico, {"nombre": "visita.jpg", "content_type": "image/jpeg"}, 201)
    imagen = b"\xff\xd8\xff\xe0" + b"0" * 2048 + b"\xff\xd9"
    subida = requests.post(firma["url"], data=firma["fields"], files={"file": ("visita.jpg", imagen, "image/jpeg")}, timeout=4)
    exigir(200 <= subida.status_code < 300, "Falló la subida multipart a S3 simulado")
    clave = firma["fields"]["key"]
    local.invocar(local.destino_s3, {"Records": [{"s3": {"object": {"key": quote_plus(clave)}}}]})
    foto, = local.api("GET", ruta_parte, tecnico)["evidencias"]
    exigir(foto["estado"] == "CONFIRMADA" and requests.get(foto["url"], timeout=4).content == imagen, "Evidencia sin confirmar")

    editado = local.api("PUT", ruta_parte, tecnico, {"version": parte["version"], "diagnostico": "Filtro",
                        "tareas": ["Limpieza"], "resultado": "RESUELTO"})
    final = local.api("POST", ruta_parte + "/finalizar", tecnico, {"version": editado["version"]})
    exigir(final["estado"] == "FINALIZADO", "Parte sin finalizar")
    local.procesar_colas()
    exigir(local.api("GET", ruta_visita, coordinador)["estado"] == "FINALIZADA", "Visita sin finalizar")
    exigir(local.api("GET", ruta_orden, coordinador)["estado"] == "PENDIENTE_DE_CIERRE", "Orden sin actualizar")
    historial = local.api("GET", ruta_orden + "/historial", coordinador)["items"]
    exigir({"VisitaCompletada", "PARTE_FINALIZADO"} <= {h["tipo"] for h in historial}, "Historial incompleto")
    cerrada = local.api("POST", ruta_orden + "/cerrar", coordinador)
    exigir(cerrada["estado"] == "CERRADA", "Orden sin cerrar")
    local.procesar_colas()
    periodo_cierre = datetime.fromisoformat(cerrada["terminada_en"].replace("Z", "+00:00")).astimezone(lima).strftime("%Y-%m")
    for periodo, contador in [(fecha[:7], "visitas_completadas"), (periodo_cierre, "ordenes_cerradas")]:
        ruta = "/analitica/dashboard?periodo=" + periodo
        exigir(local.api("GET", ruta, coordinador)[contador] == 1, "Métrica incorrecta " + contador)
        exigir(local.api("GET", ruta, otra_empresa)[contador] == 0, "Métrica de otra empresa " + contador)

    # Segunda orden de la demo: la ausencia reasigna las visitas y la cancelación libera ambas.
    siguiente = inicio + timedelta(days=1)
    dia = siguiente.date().isoformat()
    suplente = local.api("POST", "/tecnicos", coordinador, {"nombre": "Suplente", "especialidades": ["REPARACION"]}, 201)
    local.api("PUT", f"/tecnicos/{suplente['tecnico_id']}/jornadas/{dia}", coordinador,
              {"intervalos": [{"inicio": "08:00", "fin": "12:00"}]})
    segunda = local.api("POST", "/ordenes", coordinador, datos_orden, 201)
    visitas = [programar(segunda["orden_id"], siguiente + timedelta(minutes=m)) for m in (0, 30)]
    local.procesar_colas()
    local.api("PUT", f"/tecnicos/{candidato['tecnico_id']}/ausencias/{dia}", coordinador, {"motivo": "Ausencia de prueba"}, 201)
    local.procesar_colas()
    rutas = ["/visitas/" + v["visita_id"] for v in visitas]
    for ruta in rutas:
        actual = local.api("GET", ruta, coordinador)
        exigir(actual["tecnico_id"] == suplente["tecnico_id"] and actual["reasignada_automaticamente"], "Faltó reasignar una visita")
    avisos = local.api("GET", "/alertas", coordinador)["recientes"]
    exigir({v["visita_id"] for v in visitas} <= {a["visita_id"] for a in avisos if a["tipo"] == "REASIGNADA"}, "Faltó un aviso")
    cancelada = local.api("POST", f"/ordenes/{segunda['orden_id']}/cancelar", coordinador)
    exigir(cancelada["estado"] == "CANCELADA" and cancelada["visitas_canceladas"] == 2, "Cancelación incompleta")
    local.procesar_colas()
    exigir(all(local.api("GET", ruta, coordinador)["estado"] == "CANCELADA" for ruta in rutas), "Visitas aún programadas")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plantillas", type=Path, help="Directorio de salida de validar_ingreso.py --salida")
    args = parser.parse_args()
    stacks = {n: json.loads((args.plantillas / f"dev-{n}.json").read_text(encoding="utf-8"))["Resources"]
              for n in ("shared", *SERVICIOS)}
    sys.path[:0] = [str(RAIZ), str(RAIZ / "backend/common"), *(str(RAIZ / "backend" / s) for s in SERVICIOS)]
    from seed import bootstrap_admins
    from trazora_common import interno

    env = {"AWS_DEFAULT_REGION": "us-east-1", "AWS_ACCESS_KEY_ID": "testing", "AWS_SECRET_ACCESS_KEY": "testing",
           "AWS_SESSION_TOKEN": "testing", "AWS_EC2_METADATA_DISABLED": "true", "AWS_SHARED_CREDENTIALS_FILE": os.devnull,
           "AWS_CONFIG_FILE": os.devnull, "AWS_IGNORE_CONFIGURED_ENDPOINT_URLS": "true",
           "TRAZORA_PEPPER_DEV": "", "PASSWORD_PEPPER_SECRET": ""}
    with (patch.dict(os.environ, env), patch("socket.socket.connect", side_effect=AssertionError("Conexión de red inesperada")),
          mock_aws(), tempfile.TemporaryDirectory() as tmp):
        os.environ.pop("AWS_PROFILE", None)
        os.environ.pop("AWS_DEFAULT_PROFILE", None)
        local = IngresoLocal(stacks)
        with patch.object(bootstrap_admins, "ARCHIVO", Path(tmp) / "cuentas"), patch.object(sys, "argv", ["bootstrap", "--stage", "dev"]):
            bootstrap_admins.main()
            cuentas = {(tenant, rol): {"tenant_id": tenant, "email": email, "password": pw}
                       for _, tenant, email, pw, rol in bootstrap_admins.leer_guardadas()}
        with patch.object(interno, "invocar", local.invocar), patch("urllib.request.urlopen", local.transporte_http):
            recorrido(local, cuentas)
    print("Recorrido local OK. Evidencia confirmada, visita finalizada, orden cerrada y métricas aisladas por empresa.")
    print("Ausencia y cancelación OK. Dos visitas reasignadas al suplente y después canceladas.")


if __name__ == "__main__":
    main()
