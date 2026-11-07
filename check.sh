#!/usr/bin/env bash
# Comprueba el sistema desplegado, sin desplegar nada.
while [ $# -gt 0 ]; do case "$1" in --stage) export STAGE_CLI="$2"; shift 2 ;; *) shift ;; esac; done
source "$(dirname "$0")/scripts/lib.sh"
comprobar_entorno
ERRORES=0
for s in "${SERVICIOS[@]}"; do
  [ -f "backend/$s/serverless.yml" ] || continue
  u="$(url_servicio "$s")"
  if [ -z "$u" ] || [ "$u" = None ]; then echo "FALLO  $s: no está desplegado"; ERRORES=$((ERRORES+1)); continue; fi
  c="$(curl -s -o /dev/null -w '%{http_code}' -X OPTIONS "$u/" || true)"
  echo "OK     $s: $u (HTTP $c)"
done
APAGADOS="$(disparadores_apagados)"
if [ -n "$APAGADOS" ]; then
  echo "FALLO  eventos: consumidores deshabilitados ($(echo $APAGADOS | tr ' ' ',')). Ejecuta ./warmup.sh --stage $STAGE para reactivarlos."
  ERRORES=$((ERRORES+1))
else
  echo "OK     eventos: los 3 consumidores SQS están activos"
fi
APP="$(app_amplify)"
if [ "$APP" != None ] && [ -n "$APP" ]; then
  c="$(curl -s -o /dev/null -w '%{http_code}' "$(url_web "$APP")" || true)"
  if [ "$c" = 200 ]; then echo "OK     web: $(url_web "$APP")"; else echo "FALLO  web: HTTP $c"; ERRORES=$((ERRORES+1)); fi
fi
export STAGE
if [ -f backend/usuarios/serverless.yml ] && [ -f .demo-credentials ]; then
  python3 -m pytest tests/integracion -m "not muta" || ERRORES=$((ERRORES+1))
fi
[ "$ERRORES" -eq 0 ] || fallo "$ERRORES comprobaciones fallaron."
echo "Todas las comprobaciones pasaron."
