#!/usr/bin/env bash
# Despliega stacks desechables, comprueba la cuenta y los elimina al terminar.
export STAGE_CLI=verif
source "$(dirname "$0")/lib.sh"
comprobar_entorno
limpiar() {
  paso "Eliminando los stacks de verificación"
  aws s3 rm "s3://trazora-verif-$CUENTA" --recursive >/dev/null 2>&1 || true
  (cd infra/verificacion/pruebas && serverless remove --stage verif) || echo "Aviso: revisa el stack trazora-verif-verif"
  (cd infra/verificacion/autorizador && serverless remove --stage verif) || echo "Aviso: revisa el stack trazora-verif-auth-verif"
}
trap limpiar EXIT
paso "Desplegando el autorizador"
(cd infra/verificacion/autorizador && serverless deploy --stage verif)
paso "Desplegando las pruebas"
(cd infra/verificacion/pruebas && serverless deploy --stage verif)
paso "Comprobando"
python3 scripts/verificar_cuenta.py
