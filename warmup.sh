#!/usr/bin/env bash
# Una petición secuencial por API, para evitar arranques en frío durante la demo.
while [ $# -gt 0 ]; do case "$1" in --stage) export STAGE_CLI="$2"; shift 2 ;; *) shift ;; esac; done
source "$(dirname "$0")/scripts/lib.sh"
for s in "${SERVICIOS[@]}"; do
  u="$(url_servicio "$s")"
  [ -n "$u" ] && [ "$u" != None ] || continue
  curl -s -o /dev/null -m 15 -H 'Authorization: Bearer calentamiento' "$u/$s" || true
  echo "Calentado: $s"
done
