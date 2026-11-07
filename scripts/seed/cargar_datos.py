"""Carga directa a DynamoDB con boto3 y batch_writer, en un solo proceso.

No usa API Gateway, Lambda, SNS ni S3: escribir en estas tablas no invoca ninguna función, así
que la carga no consume la concurrencia de Lambda de la cuenta de Academy."""
import argparse
import datetime
import pathlib
import time

import boto3

from generador import RAIZ, SERVICIOS, TENANTS, generar_tenant


def fecha_base(stage, semilla, indicada):
    """Se conserva entre ejecuciones: reanudar otro día debe producir los mismos ID."""
    archivo = RAIZ / ".local-env" / f"seed-base-{stage}-{semilla}.txt"
    if indicada:
        return datetime.date.fromisoformat(indicada)
    if archivo.exists():
        return datetime.date.fromisoformat(archivo.read_text().strip())
    hoy = datetime.date.today()
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text(hoy.isoformat())
    return hoy


def tabla_de(stage, servicio):
    return boto3.resource("dynamodb").Table(f"{stage}-t_{servicio}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", default="dev")
    parser.add_argument("--seed", type=int, default=2032)
    parser.add_argument("--escala", type=float, default=1.0)
    parser.add_argument("--base", help="Fecha base AAAA-MM-DD; por defecto, la de la carga anterior o hoy")
    parser.add_argument("--solo", choices=SERVICIOS, help="Cargar un solo servicio")
    parser.add_argument("--dry-run", action="store_true", help="Solo cuenta lo que generaría, sin escribir")
    args = parser.parse_args()

    base = fecha_base(args.stage, args.seed, args.base) if not args.dry_run else datetime.date.today()
    print(f"Stage {args.stage}, semilla {args.seed}, escala {args.escala}, fecha base {base}{' (simulación)' if args.dry_run else ''}")
    servicios = (args.solo,) if args.solo else SERVICIOS
    totales = {s: 0 for s in servicios}
    inicio = time.time()
    for tenant in TENANTS:
        datos = generar_tenant(tenant, args.seed, args.escala, base)
        for servicio in servicios:
            items = datos[servicio]
            totales[servicio] += len(items)
            if not args.dry_run:
                # Un solo escritor por tabla, sin hilos; batch_writer reintenta lo no procesado.
                with tabla_de(args.stage, servicio).batch_writer() as lote:
                    for item in items:
                        lote.put_item(Item=item)
            print(f"  {tenant:<11} {servicio:<10} {len(items):>7} ítems", flush=True)
    print(f"Total: {sum(totales.values())} ítems en {round(time.time() - inicio)} s")
    for servicio, total in totales.items():
        print(f"  {servicio:<10} {total:>7}")
    if pathlib.Path(RAIZ / "scripts/seed/contar.py").exists() and not args.dry_run:
        print("Para el reporte: python3 scripts/seed/contar.py --stage " + args.stage)


if __name__ == "__main__":
    main()
