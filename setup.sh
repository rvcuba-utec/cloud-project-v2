#!/usr/bin/env bash
# Instala las herramientas dentro del proyecto (.venv y node_modules). No modifica el sistema.
set -euo pipefail
cd "$(dirname "$0")"
if command -v uv >/dev/null; then
  uv venv --quiet --allow-existing --python 3.12 .venv
  uv pip install --quiet --python .venv/bin/python -r requirements-dev.txt
else
  python3 -m venv .venv
  .venv/bin/pip install --quiet -r requirements-dev.txt
fi
npm install --silent --no-audit --no-fund
[ -d frontend ] && (cd frontend && npm install --silent --no-audit --no-fund)
[ -f config.env ] || cp config.example.env config.env
echo "Listo. Edita config.env y pega las credenciales de AWS Academy en ~/.aws/credentials."
