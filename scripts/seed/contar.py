"""Reporte de conteos por servicio, tenant y tipo de entidad. Recorre todas las páginas."""
import argparse
import collections
import datetime

import boto3
from boto3.dynamodb.conditions import Key

from generador import RAIZ, SERVICIOS, TENANTS

TECNICOS = {"INBOX", "OUTBOX", "IDEMP", "MARCA_VISITA", "BLOQUE", "CONTROL_ORDEN", "EMAIL", "EMPRESA", "HISTORIAL"}
MINIMO = 30000


def contar(tabla, tenant):
    conteo = collections.Counter()
    inicio = None
    while True:
        parametros = {
            "KeyConditionExpression": Key("PK").eq(f"TENANT#{tenant}"),
            "ProjectionExpression": "entity_type",
        }
        if inicio:
            parametros["ExclusiveStartKey"] = inicio
        pagina = tabla.query(**parametros)
        conteo.update(i.get("entity_type", "OTRO") for i in pagina.get("Items", []))
        inicio = pagina.get("LastEvaluatedKey")
        if not inicio:
            return conteo


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", default="dev")
    parser.add_argument("--seed", default="2032")
    stage = parser.parse_args().stage
    recurso = boto3.resource("dynamodb")
    lineas = [
        "# Conteos de registros", "",
        f"Generado el {datetime.datetime.now(datetime.timezone.utc):%Y-%m-%d %H:%M} UTC, stage `{stage}`, leyendo DynamoDB con paginación completa.",
        "Se separan los registros de negocio de los ítems técnicos (marcadores, bloques, historial).", "",
        "| Servicio | Tenant | Negocio | Técnicos | Detalle |", "|---|---|---:|---:|---|",
    ]
    resumen = {}
    for servicio in SERVICIOS:
        tabla = recurso.Table(f"{stage}-t_{servicio}")
        for tenant in TENANTS:
            conteo = contar(tabla, tenant)
            negocio = sum(v for k, v in conteo.items() if k not in TECNICOS)
            tecnicos = sum(v for k, v in conteo.items() if k in TECNICOS)
            detalle = ", ".join(f"{k}: {v}" for k, v in sorted(conteo.items()))
            lineas.append(f"| {servicio} | {tenant} | {negocio} | {tecnicos} | {detalle} |")
            resumen[servicio] = resumen.get(servicio, 0) + negocio
    lineas += ["", "| Servicio | Registros de negocio | Mínimo de 30 000 |", "|---|---:|---|"]
    for servicio, total in resumen.items():
        lineas.append(f"| {servicio} | {total} | {'Cumple' if total >= MINIMO else 'No cumple'} |")
    destino = RAIZ / "docs/evidencias/conteos.md"
    destino.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print("\n".join(lineas[-len(resumen) - 2:]))
    print(f"Reporte: {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
