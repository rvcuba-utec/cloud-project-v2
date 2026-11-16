#!/usr/bin/env bash
# Pruebas locales, sin AWS. Cada servicio corre en su proceso porque todos tienen `handlers/`.
set -uo pipefail
cd "$(dirname "$0")"
source scripts/entorno.sh
export AWS_ACCESS_KEY_ID=testing AWS_SECRET_ACCESS_KEY=testing AWS_SESSION_TOKEN=testing
export AWS_EC2_METADATA_DISABLED=true AWS_DEFAULT_REGION=us-east-1
unset AWS_PROFILE STAGE PASSWORD_PEPPER_SECRET
FALLOS=0
for d in backend/common backend/usuarios backend/clientes backend/tecnicos backend/analitica backend/ordenes backend/agenda backend/partes scripts/seed; do
  [ -d "$d/tests" ] || continue
  echo "== $d"; python -m pytest "$d/tests" || FALLOS=1
done
echo "== frontend"; (cd frontend && npm test --silent) || FALLOS=1
[ "$FALLOS" -eq 0 ] && echo "Todas las pruebas pasaron." || { echo "Hay pruebas con fallos."; exit 1; }
