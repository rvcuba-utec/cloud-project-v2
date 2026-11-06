#!/usr/bin/env bash
# Borra del proyecto las herramientas, credenciales locales y builds. No toca nada en AWS.
set -euo pipefail
cd "$(dirname "$0")"
echo "Se borrarán: .local-env/ (incluye credenciales) .venv/ node_modules/ frontend/node_modules/ frontend/dist/ frontend/dist.zip"
read -r -p "Escribe 'borrar' para confirmar: " RESPUESTA
[ "$RESPUESTA" = borrar ] || { echo "Cancelado."; exit 1; }
rm -rf .local-env .venv node_modules frontend/node_modules frontend/dist frontend/dist.zip
find backend -mindepth 2 -maxdepth 2 -type d -name trazora_common -not -path 'backend/common/*' -exec rm -rf {} +
find . -type d -name .serverless -not -path './.git/*' -exec rm -rf {} +
echo "Listo. config.env se conserva; ./setup.sh vuelve a instalar todo. Los recursos en AWS no cambian."
