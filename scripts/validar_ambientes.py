"""Ejecuta Serverless print con salidas de CloudFormation ficticias, sin consultar AWS."""
import argparse
import json
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SERVICIOS = ("usuarios", "clientes", "tecnicos", "ordenes", "agenda", "partes", "analitica")
ETAPAS = ("dev", "test", "prod")


def parametros(stage):
    return {
        "cuenta": "000000000000", "restApiId": "api" + stage, "rootId": "raiz" + stage,
        "visitasId": "visitas" + stage, "visitaId": "visita" + stage, "authorizerId": "auth" + stage,
        "topicArn": f"arn:aws:sns:us-east-1:000000000000:{stage}-fsm-eventos",
        "origenFrontend": f"https://{stage}.example.invalid",
    }


def imprimir(cli, node, nombre, stage, salida):
    ruta = RAIZ / ("infra/shared" if nombre == "shared" else "backend/" + nombre)
    valores = parametros(stage)
    args = [node, str(cli), "print", "--stage", stage, "--format", "json"]
    args += [f"--param={k}={v}" for k, v in valores.items()]
    env = {**os.environ, "AWS_EC2_METADATA_DISABLED": "true", "AWS_REGION": "us-east-1",
           "AWS_ACCESS_KEY_ID": "testing", "AWS_SECRET_ACCESS_KEY": "testing", "AWS_SESSION_TOKEN": "testing",
           "SLS_TELEMETRY_DISABLED": "1", "SLS_ORG": os.getenv("SLS_ORG") or "trazoralocal"}
    env.pop("TRAZORA_PEPPER_DEV", None)
    run = subprocess.run(args, cwd=ruta, capture_output=True, text=True, encoding="utf-8", errors="replace",
                         env=env, timeout=100)
    texto = run.stdout
    inicio = next((i for i, line in enumerate(texto.splitlines()) if line.strip() == "{"), None)
    if run.returncode or inicio is None:
        raise RuntimeError(f"Serverless print falló para {nombre}/{stage}. Comprueba la versión y el acceso a Serverless.")
    cfg, _ = json.JSONDecoder().raw_decode("\n".join(texto.splitlines()[inicio:]).lstrip())
    if salida:
        salida.mkdir(parents=True, exist_ok=True)
        (salida / f"{stage}-{nombre}.json").write_text(json.dumps(cfg, indent=2), encoding="utf8")
    return cfg


def exigir(condicion, detalle):
    if not condicion:
        raise ValueError(detalle)


def verificar(stage, configs):
    datos = parametros(stage)
    compartido = configs["shared"]["resources"]
    recursos = compartido["Resources"]
    exigir(sum(r["Type"] == "AWS::ApiGateway::RestApi" for r in recursos.values()) == 1, "Gateway compartido")
    exigir(recursos["ApiTrazora"]["Properties"]["Name"] == "trazora-" + stage, "Nombre de gateway")
    exigir(recursos["TemaEventos"]["Properties"]["TopicName"] == stage + "-fsm-eventos", "Nombre SNS")
    url = f'https://{datos["restApiId"]}.execute-api.us-east-1.amazonaws.com/{stage}'
    rutas, tablas, colas, secretos, lambdas, productores = set(), set(), set(), set(), set(), set()
    for nombre in SERVICIOS:
        cfg = configs[nombre]
        provider = cfg["provider"]
        env = provider["environment"]
        exigir(provider["stage"] == env["STAGE"] == stage and env["SERVICE_NAME"] == nombre, nombre)
        exigir(provider["logRetentionInDays"] == (14 if stage == "prod" else 7), "Retención de logs")
        exigir(provider["apiGateway"]["restApiId"] == datos["restApiId"], "Gateway de " + nombre)
        if nombre in {"agenda", "partes"}:
            exigir(provider["apiGateway"]["restApiResources"] == {
                "/visitas": datos["visitasId"], "/visitas/{visita_id}": datos["visitaId"]}, "Rutas de visitas")
        for clave, valor in env.items():
            if clave.endswith("_URL"):
                exigir(valor == url, clave)
            if clave.endswith("_FN"):
                exigir("-" + stage + "-" in valor, clave)
            if clave == "TOPIC_ARN":
                exigir(valor == datos["topicArn"], clave)
        for item in cfg["resources"]["Resources"].values():
            props = item.get("Properties", {})
            tipo = item["Type"]
            if tipo == "AWS::DynamoDB::Table":
                exigir(props["TableName"].startswith(stage + "-t_"), "Tabla sin stage")
                tablas.add(props["TableName"])
            if tipo == "AWS::SQS::Queue":
                cola = props["QueueName"]
                exigir(cola.startswith(stage + "-q-"), cola)
                if cola.endswith("-dlq"):
                    exigir(props["MessageRetentionPeriod"] == 1209600, cola)
                else:
                    exigir(props["RedrivePolicy"]["maxReceiveCount"] == 5, cola)
                colas.add(cola)
        for funcion, spec in cfg["functions"].items():
            lambdas.add(f'{cfg["service"]}-{stage}-{funcion}')
            secreto = spec.get("environment", {}).get("PASSWORD_PEPPER_SECRET")
            if secreto is not None:
                exigir(nombre == "usuarios" and funcion in {"crear", "login"}, "Acceso inesperado a secretos")
                exigir(secreto == ("" if stage == "dev" else f"trazora/{stage}/usuarios/password-pepper"), "Secreto de otro stage")
                if secreto:
                    secretos.add(secreto)
            for trigger in spec.get("events", []):
                if "sqs" in trigger:
                    exigir(trigger["sqs"]["functionResponseType"] == "ReportBatchItemFailures", nombre)
                if "schedule" in trigger:
                    productores.add(nombre)
                if "http" in trigger:
                    http = trigger["http"]
                    ruta = (http["method"].upper(), http["path"])
                    exigir(ruta not in rutas, "Ruta repetida " + str(ruta))
                    rutas.add(ruta)
                    if ruta != ("POST", "auth/login"):
                        exigir(http["authorizer"]["authorizerId"] == datos["authorizerId"], str(ruta))
    bucket = configs["partes"]["provider"]["s3"]["evidencias"]
    exigir(bucket["name"] == f"trazora-evidencias-{stage}-000000000000", "Bucket")
    origenes = bucket["corsConfiguration"]["CorsRules"][0]["AllowedOrigins"]
    exigir(datos["origenFrontend"] in origenes and ("http://localhost:5173" in origenes) == (stage != "prod"), "Orígenes S3")
    exigir(len(tablas) == 8 and len(colas) == 6 and productores == {"agenda", "tecnicos", "ordenes", "partes"}, "Inventario")
    print(f"{stage}: 1 API, {len(rutas)} rutas, {len(lambdas)} Lambda, 8 tablas, 3 colas + 3 DLQ, 4 barridos")
    return tablas | colas | secretos | lambdas | {url, bucket["name"], datos["topicArn"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", type=Path, default=RAIZ / "node_modules/serverless/run.js")
    parser.add_argument("--node", default=shutil.which("node") or "node")
    parser.add_argument("--salida", type=Path)
    args = parser.parse_args()
    cli = args.cli.resolve()
    vistos = set()
    for stage in ETAPAS:
        nombres = ("shared", *SERVICIOS)
        with ThreadPoolExecutor(max_workers=3) as pool:
            configs = dict(zip(nombres, pool.map(lambda s: imprimir(cli, args.node, s, stage, args.salida), nombres)))
        exclusivos = verificar(stage, configs)
        exigir(not vistos.intersection(exclusivos), "Hay nombres compartidos entre ambientes")
        vistos.update(exclusivos)


if __name__ == "__main__":
    main()
