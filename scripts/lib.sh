# Funciones comunes de los comandos. Se carga con `source`.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source "$ROOT/scripts/entorno.sh"
[ -f config.env ] || { echo "ERROR: falta config.env. Ejecuta ./setup.sh primero." >&2; exit 1; }
# shellcheck disable=SC1091
source config.env
STAGE="${STAGE_CLI:-${STAGE:-dev}}"
export AWS_REGION="${REGION:-us-east-1}" AWS_DEFAULT_REGION="${REGION:-us-east-1}" SLS_ORG="${SLS_ORG:-}"
[ -z "${SERVERLESS_ACCESS_KEY:-}" ] || export SERVERLESS_ACCESS_KEY

# Orden con dependencias resueltas: cada servicio solo usa URLs de los anteriores.
SERVICIOS=(usuarios clientes tecnicos analitica ordenes agenda partes)

paso()  { printf '\n==> %s\n' "$*"; }
fallo() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

comprobar_entorno() {
  local c
  for c in aws node npm serverless python3 zip curl; do
    command -v "$c" >/dev/null || fallo "falta '$c'. Ejecuta ./setup.sh."
  done
  [ "$SLS_ORG" != "cambiar-por-tu-org" ] && [ -n "$SLS_ORG" ] || fallo "define SLS_ORG en config.env."
  [ -n "${SERVERLESS_ACCESS_KEY:-}" ] || [ -f "$HOME/.serverlessrc" ] || fallo "define SERVERLESS_ACCESS_KEY en config.env."
  local salida
  if ! salida="$(aws sts get-caller-identity --query Account --output text 2>&1)"; then
    case "$salida" in
      *ExpiredToken*|*expired*) fallo "las credenciales de AWS Academy caducaron. Pega las nuevas en $AWS_SHARED_CREDENTIALS_FILE" ;;
      *) fallo "no hay credenciales válidas de AWS. Pégalas en $AWS_SHARED_CREDENTIALS_FILE ($salida)" ;;
    esac
  fi
  CUENTA="$salida"
  echo "Cuenta ...${CUENTA: -4}, región $AWS_REGION, stage $STAGE"
}

sincronizar_comun() {
  local s
  for s in "${SERVICIOS[@]}"; do
    [ -d "backend/$s" ] || continue
    rm -rf "backend/$s/trazora_common"
    cp -r backend/common/trazora_common "backend/$s/trazora_common"
  done
}

url_servicio() {
  aws cloudformation describe-stacks --stack-name "api-$1-$STAGE" \
    --query "Stacks[0].Outputs[?OutputKey=='ServiceEndpoint'].OutputValue | [0]" --output text 2>/dev/null || true
}

app_amplify() {
  aws amplify list-apps --query "apps[?name=='trazora-$STAGE'].appId | [0]" --output text
}

url_web() { echo "https://main.$1.amplifyapp.com"; }

# AWS Academy deshabilita los disparadores SQS -> Lambda al apagar el laboratorio, y CloudFormation
# no lo corrige al volver a desplegar. Sin ellos los eventos se quedan en las colas.
CONSUMIDORES=(ordenes agenda analitica)

disparadores_apagados() {
  local s uuid
  for s in "${CONSUMIDORES[@]}"; do
    for uuid in $(aws lambda list-event-source-mappings --function-name "api-$s-$STAGE-consumidor" \
        --query "EventSourceMappings[?State!='Enabled'].UUID" --output text 2>/dev/null); do
      [ "$uuid" = None ] || echo "$s:$uuid"
    done
  done
}

reactivar_disparadores() {
  local par
  for par in $(disparadores_apagados); do
    aws lambda update-event-source-mapping --uuid "${par#*:}" --enabled >/dev/null && echo "Reactivado: consumidor de ${par%%:*}"
  done
}
