# Funciones comunes de los comandos. Se carga con `source`.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[ -f config.env ] || { echo "ERROR: falta config.env. Ejecuta ./setup.sh primero." >&2; exit 1; }
# shellcheck disable=SC1091
source config.env
STAGE="${STAGE_CLI:-${STAGE:-dev}}"
export AWS_REGION="${REGION:-us-east-1}" AWS_DEFAULT_REGION="${REGION:-us-east-1}" SLS_ORG="${SLS_ORG:-}"
export PATH="$ROOT/.venv/bin:$ROOT/node_modules/.bin:$PATH"

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
  local salida
  if ! salida="$(aws sts get-caller-identity --query Account --output text 2>&1)"; then
    case "$salida" in
      *ExpiredToken*|*expired*) fallo "las credenciales de AWS Academy caducaron. Pega las nuevas en ~/.aws/credentials." ;;
      *) fallo "no hay credenciales válidas de AWS: $salida" ;;
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
