"""Alinea el índice por estado de las órdenes terminadas con su fecha de término.

Desde esta versión, una orden CERRADA o CANCELADA guarda GSI1SK = "<terminada_en>#<orden_id>": así el
mapa encuentra "las cerradas en los últimos 14 días". Las órdenes terminadas antes (o cargadas con la
semilla anterior) conservaban la fecha de creación. Este script las corrige directo en DynamoDB, como la
carga de datos (sin pasar por API Gateway ni Lambda). Se puede repetir: solo toca las desalineadas.

    python scripts/migrar_ordenes_terminadas.py --stage dev [--dry-run]
"""
import argparse
import pathlib
import re
from concurrent.futures import ThreadPoolExecutor

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

RAIZ = pathlib.Path(__file__).resolve().parents[1]
TERMINALES = ("CERRADA", "CANCELADA")
HILOS = 8


def tenants():
    texto = (RAIZ / "backend" / "serverless.common.yml").read_text(encoding="utf-8")
    return re.search(r"^tenants:\s*(\S+)", texto, re.M).group(1).split(",")


def desalineadas(tabla, tenant, estado):
    inicio = None
    while True:
        parametros = {"IndexName": "GSI1", "KeyConditionExpression": Key("GSI1PK").eq(f"TENANT#{tenant}#ESTADO#{estado}")}
        if inicio:
            parametros["ExclusiveStartKey"] = inicio
        pagina = tabla.query(**parametros)
        for orden in pagina.get("Items", []):
            esperado = f"{orden.get('terminada_en')}#{orden['orden_id']}"
            if orden.get("terminada_en") and orden["GSI1SK"] != esperado:
                yield orden, esperado
        inicio = pagina.get("LastEvaluatedKey")
        if not inicio:
            return


def corregir(tabla, orden, esperado):
    try:
        tabla.update_item(
            Key={"PK": orden["PK"], "SK": orden["SK"]},
            UpdateExpression="SET GSI1SK = :s",
            # Si la orden cambió mientras tanto, no se pisa nada.
            ConditionExpression="estado = :e AND terminada_en = :t",
            ExpressionAttributeValues={":s": esperado, ":e": orden["estado"], ":t": orden["terminada_en"]},
        )
        return True
    except ClientError as error:
        if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise


def main():
    argumentos = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    argumentos.add_argument("--stage", default="dev")
    argumentos.add_argument("--dry-run", action="store_true", help="Solo cuenta, sin escribir")
    opciones = argumentos.parse_args()
    tabla = boto3.resource("dynamodb").Table(f"{opciones.stage}-t_ordenes")
    total = 0
    for tenant in tenants():
        for estado in TERMINALES:
            pendientes = list(desalineadas(tabla, tenant, estado))
            corregidas = 0
            if pendientes and not opciones.dry_run:
                with ThreadPoolExecutor(HILOS) as hilos:
                    corregidas = sum(hilos.map(lambda par: corregir(tabla, *par), pendientes))
            print(f"{tenant} {estado}: {len(pendientes)} desalineadas" + ("" if opciones.dry_run else f", {corregidas} corregidas"))
            total += len(pendientes)
    print(f"Total: {total}" + (" (sin escribir)" if opciones.dry_run else ""))


if __name__ == "__main__":
    main()
