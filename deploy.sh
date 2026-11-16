#!/usr/bin/env bash
# Uso: ./deploy.sh [todo|backend|frontend|<servicio>] [--stage <stage>]
OBJETIVO=todo
while [ $# -gt 0 ]; do
  case "$1" in
    --stage) export STAGE_CLI="$2"; shift 2 ;;
    *) OBJETIVO="$1"; shift ;;
  esac
done
source "$(dirname "$0")/scripts/lib.sh"
source scripts/amplify.sh

desplegar_servicio() {
  local s=$1 args=(--stage "$STAGE")
  [ -f "backend/$s/serverless.yml" ] || return 0
  paso "Backend: $s"
  [ "$s" = partes ] && args+=(--param="origenFrontend=$ORIGEN_FRONTEND")
  (cd "backend/$s" && serverless deploy "${args[@]}") || fallo "falló el despliegue de '$s'. Corrige y vuelve a ejecutar."
}

desplegar_backend() {
  paso "Backend: recursos compartidos"
  local args=(--stage "$STAGE" --param="certificadoAlb=$CERTIFICADO_ALB" --param="dominioAlb=$DOMINIO_ALB")
  if [[ -n "${TRAZORA_AZ_ID_A:-}" ]]; then args+=(--param="azIdA=$TRAZORA_AZ_ID_A" --param="azIdB=$TRAZORA_AZ_ID_B"); fi
  (cd infra/shared && serverless deploy "${args[@]}") || fallo "falló el stack compartido."
  sincronizar_comun
  local s
  for s in "${SERVICIOS[@]}"; do desplegar_servicio "$s"; done
}

if [[ "$OBJETIVO" == todo || "$OBJETIVO" == backend ]]; then
  if [[ -n "${TRAZORA_AZ_ID_A:-}${TRAZORA_AZ_ID_B:-}" || "$AWS_REGION" != us-east-1 ]]; then
    [[ -n "${TRAZORA_AZ_ID_A:-}" && -n "${TRAZORA_AZ_ID_B:-}" && "$TRAZORA_AZ_ID_A" != "$TRAZORA_AZ_ID_B" ]] ||
      fallo "define TRAZORA_AZ_ID_A y TRAZORA_AZ_ID_B con dos AZ distintas que admitan VPC Link V2."
  fi
  var_cert="TRAZORA_ALB_CERT_ARN_${STAGE^^}"
  var_dns="TRAZORA_ALB_DOMINIO_${STAGE^^}"
  CERTIFICADO_ALB="${!var_cert:-}"
  DOMINIO_ALB="${!var_dns:-}"
  [[ -n "$CERTIFICADO_ALB" && -n "$DOMINIO_ALB" ]] || fallo "define $var_cert y $var_dns en config.env para el listener HTTPS."
fi

comprobar_entorno
preparar_amplify      # define APP_ID y ORIGEN_FRONTEND

case "$OBJETIVO" in
  todo)     desplegar_backend; publicar_frontend ;;
  backend)  desplegar_backend ;;
  frontend) publicar_frontend ;;
  *)
    printf '%s\n' "${SERVICIOS[@]}" | grep -qx "$OBJETIVO" || fallo "objetivo desconocido: $OBJETIVO"
    sincronizar_comun; desplegar_servicio "$OBJETIVO"
    ;;
esac

if [ "$OBJETIVO" = todo ]; then
  if [ -f scripts/seed/bootstrap_admins.py ] && [ -f backend/usuarios/serverless.yml ]; then
    paso "Cuentas de demo"
    python3 scripts/seed/bootstrap_admins.py --stage "$STAGE"
  fi
  ./check.sh --stage "$STAGE"
fi
paso "Listo"
echo "Web: $(url_web "$APP_ID")"
[ -f .demo-credentials ] && echo "Cuentas: .demo-credentials (fuera de Git)"
exit 0
