"""Inventario de solo lectura del laboratorio. Imprime conteos y códigos, nunca valores."""
import argparse
import json
import sys

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

ETAPAS = ("dev", "test", "prod")
SERVICIOS = ("usuarios", "clientes", "tecnicos", "ordenes", "agenda", "partes", "analitica")
CONFIG = Config(connect_timeout=3, read_timeout=5, retries={"total_max_attempts": 1})


def estado(llamada):
    try:
        return llamada()
    except ClientError as exc:
        return {"error": exc.response["Error"]["Code"]}
    except (BotoCoreError, OSError) as exc:
        return {"error": type(exc).__name__}


def revisar(sesion, stage, probar_secreto=False):
    def cliente(nombre):
        return sesion.client(nombre, config=CONFIG)

    def inventario(nombre, operacion, campo, patron, extra=None):
        paginas = cliente(nombre).get_paginator(operacion).paginate(**(extra or {}))
        return sum(1 for pag in paginas for item in pag.get(campo, []) if patron(item))

    lambda_api = cliente("lambda")
    secrets = cliente("secretsmanager")
    prefijo = f"{stage}-"
    nombres = {f"api-{s}-{stage}" for s in SERVICIOS} | {f"trazora-shared-{stage}"}
    nombre_secreto = f"trazora/{stage}/usuarios/password-pepper"
    def secreto():
        secrets.describe_secret(SecretId=nombre_secreto)
        if probar_secreto:
            secrets.get_secret_value(SecretId=nombre_secreto)
        return "lectura verificada" if probar_secreto else "metadatos disponibles"

    def mappings(servicio):
        paginas = lambda_api.get_paginator("list_event_source_mappings").paginate(
            FunctionName=f"api-{servicio}-{stage}-consumidor")
        return [m["State"] for pag in paginas for m in pag["EventSourceMappings"]
                if m["EventSourceArn"].endswith(f":{stage}-q-{servicio}")]
    def propiedad():
        conteos = {"apis_rest": 0, "temas": 0, "colas": 0}
        cf = cliente("cloudformation")
        for pag in cf.get_paginator("list_stacks").paginate():
            for stack in pag["StackSummaries"]:
                if stack["StackName"] not in nombres or stack["StackStatus"] == "DELETE_COMPLETE":
                    continue
                for lote in cf.get_paginator("list_stack_resources").paginate(StackName=stack["StackId"]):
                    for recurso in lote["StackResourceSummaries"]:
                        tipo = recurso["ResourceType"]
                        if tipo == "AWS::ApiGateway::RestApi":
                            conteos["apis_rest"] += 1
                        elif tipo == "AWS::SNS::Topic":
                            conteos["temas"] += 1
                        elif tipo == "AWS::SQS::Queue":
                            conteos["colas"] += 1
        return conteos

    return {
        "propiedad_cloudformation": estado(propiedad),
        "stacks": estado(lambda: inventario("cloudformation", "list_stacks", "StackSummaries",
            lambda x: x["StackName"] in nombres and x["StackStatus"] != "DELETE_COMPLETE")),
        "lambdas": estado(lambda: inventario("lambda", "list_functions", "Functions",
            lambda x: any(x["FunctionName"].startswith(n + "-") for n in nombres))),
        "tablas": estado(lambda: inventario("dynamodb", "list_tables", "TableNames", lambda x: x.startswith(prefijo + "t_"))),
        "temas": estado(lambda: inventario("sns", "list_topics", "Topics", lambda x: x["TopicArn"].endswith(":" + prefijo + "fsm-eventos"))),
        "colas": estado(lambda: inventario("sqs", "list_queues", "QueueUrls", lambda x: True, {"QueueNamePrefix": prefijo + "q-"})),
        "mappings": {s: estado(lambda s=s: mappings(s)) for s in ("agenda", "ordenes", "analitica")},
        "secreto_usuarios": estado(secreto),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=ETAPAS, action="append")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--probar-lectura-secreto", action="store_true")
    args = parser.parse_args()
    sesion = boto3.Session(region_name=args.region)
    identidad = estado(lambda: bool(sesion.client("sts", config=CONFIG).get_caller_identity()["Account"]))
    if identidad is not True:
        print(json.dumps({"sesion": identidad}))
        return 1
    print(json.dumps({"sesion": "válida", "region": args.region,
                      "stages": {s: revisar(sesion, s, args.probar_lectura_secreto)
                                 for s in (args.stage or ETAPAS)}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
