#!/usr/bin/env bash
# Carga de datos: directa a DynamoDB con boto3, nunca por API Gateway ni Lambda.
# Uso: ./seed.sh [--escala 0.01] [--stage <stage>]
source "$(dirname "$0")/scripts/lib.sh"
python3 scripts/seed/cargar_datos.py --stage "$STAGE" "$@" || exit 1
case " $* " in
  *" --dry-run "*) ;;
  *) python3 scripts/seed/contar.py --stage "$STAGE" ;;
esac
