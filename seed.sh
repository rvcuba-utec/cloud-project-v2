#!/usr/bin/env bash
# Carga de datos: directa a DynamoDB con boto3, nunca por API Gateway ni Lambda.
# Uso: ./seed.sh [--escala 0.01] [--stage <stage>]
source "$(dirname "$0")/scripts/lib.sh"
[ -f scripts/seed/cargar_datos.py ] || fallo "el generador se construye en la etapa 7."
python3 scripts/seed/cargar_datos.py "$@"
