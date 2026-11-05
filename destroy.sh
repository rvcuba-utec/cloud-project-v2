#!/usr/bin/env bash
# Elimina todo un stage. Pide confirmación escribiendo su nombre.
while [ $# -gt 0 ]; do case "$1" in --stage) export STAGE_CLI="$2"; shift 2 ;; *) shift ;; esac; done
source "$(dirname "$0")/scripts/lib.sh"
comprobar_entorno
echo "Se eliminarán todos los recursos del stage '$STAGE': APIs, Lambdas, tablas con sus datos, evidencias y la web."
read -r -p "Escribe el nombre del stage para confirmar: " RESPUESTA
[ "$RESPUESTA" = "$STAGE" ] || fallo "cancelado."
aws s3 rm "s3://trazora-evidencias-$STAGE-$CUENTA" --recursive 2>/dev/null || true
for (( i=${#SERVICIOS[@]}-1; i>=0; i-- )); do
  s="${SERVICIOS[$i]}"
  [ -f "backend/$s/serverless.yml" ] || continue
  paso "Eliminando $s"
  (cd "backend/$s" && serverless remove --stage "$STAGE" --param="origenFrontend=https://localhost") || echo "Aviso: no se pudo eliminar $s"
done
(cd infra/shared && serverless remove --stage "$STAGE") || echo "Aviso: no se pudo eliminar el stack compartido"
APP="$(app_amplify)"
[ "$APP" = None ] || [ -z "$APP" ] || aws amplify delete-app --app-id "$APP" >/dev/null
echo "Stage '$STAGE' eliminado."
