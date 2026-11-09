#!/usr/bin/env bash
# Todas las pruebas contra AWS. Crean algunos datos de prueba; check.sh solo ejecuta las de lectura.
source "$(dirname "$0")/lib.sh"
comprobar_entorno
export STAGE
python3 -m pytest tests/integracion "$@"
