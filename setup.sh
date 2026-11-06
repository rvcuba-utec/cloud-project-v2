#!/usr/bin/env bash
# Instala las herramientas dentro del proyecto. No escribe en el ~/ real ni modifica el sistema.
set -euo pipefail
cd "$(dirname "$0")"
UV_REAL="$(command -v uv || true)"
source scripts/entorno.sh
if [ -n "$UV_REAL" ]; then
  "$UV_REAL" venv --quiet --allow-existing --managed-python --python 3.12 .venv
  "$UV_REAL" pip install --quiet --python .venv/bin/python -r requirements-dev.txt
else
  python3 -m venv .venv
  .venv/bin/pip install --quiet --no-cache-dir -r requirements-dev.txt
fi
npm install --silent --no-audit --no-fund
(cd frontend && npm install --silent --no-audit --no-fund)
[ -f config.env ] || cp config.example.env config.env
cat <<MSG
Listo. Falta:
  1. Editar config.env: SLS_ORG y SERVERLESS_ACCESS_KEY.
  2. Pegar las credenciales de AWS Academy en:
     $AWS_SHARED_CREDENTIALS_FILE
Para eliminar todo lo instalado: ./clean.sh
MSG
