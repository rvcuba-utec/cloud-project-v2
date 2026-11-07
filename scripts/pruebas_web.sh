#!/usr/bin/env bash
# Recorrido completo en un navegador real contra lo desplegado. El navegador queda en .local-env/.
source "$(dirname "$0")/lib.sh"
source scripts/amplify.sh
comprobar_entorno
preparar_amplify
export STAGE PLAYWRIGHT_BROWSERS_PATH="$LOCAL_ENV/playwright"
cd tests/e2e
[ -d node_modules ] || npm install --silent --no-audit --no-fund
npx playwright install chromium-headless-shell
node recorrido.mjs "$ORIGEN_FRONTEND"
