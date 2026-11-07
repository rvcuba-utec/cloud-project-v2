#!/usr/bin/env bash
# Pruebas locales, sin AWS. Cada servicio corre en su proceso porque todos tienen `handlers/`.
set -uo pipefail
cd "$(dirname "$0")"
source scripts/entorno.sh
FALLOS=0
for d in backend/common backend/usuarios backend/clientes backend/tecnicos backend/analitica backend/ordenes backend/agenda backend/partes scripts/seed; do
  [ -d "$d/tests" ] || continue
  echo "== $d"; python -m pytest "$d/tests" || FALLOS=1
done
echo "== frontend"; (cd frontend && npm test --silent) || FALLOS=1
[ "$FALLOS" -eq 0 ] && echo "Todas las pruebas pasaron." || { echo "Hay pruebas con fallos."; exit 1; }
