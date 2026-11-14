# Publicación del frontend en Amplify Hosting, sin conexión a Git.
# La portada estática y la documentación (/docs) van antes que la regla de la SPA: si no, Amplify la reescribiría a index.html.
REGLA_SPA='[{"source":"/presentacion","target":"/presentacion/index.html","status":"200"},{"source":"/presentacion/","target":"/presentacion/index.html","status":"200"},{"source":"/presentacion/index.html","target":"/presentacion/index.html","status":"200"},{"source":"/docs","target":"/docs/index.html","status":"200"},{"source":"/docs/","target":"/docs/index.html","status":"200"},{"source":"/docs/index.html","target":"/docs/index.html","status":"200"},{"source":"</^[^.]+$|\\.(?!(css|gif|ico|jpg|js|png|txt|svg|woff|woff2|ttf|map|json|webp)$)([^.]+$)/>","target":"/index.html","status":"200"}]'
RAMA=main

preparar_amplify() {
  APP_ID="$(app_amplify)"
  if [ "$APP_ID" = "None" ] || [ -z "$APP_ID" ]; then
    paso "Amplify: creando la aplicación"
    APP_ID="$(aws amplify create-app --name "trazora-$STAGE" --platform WEB \
      --custom-rules "$REGLA_SPA" --query 'app.appId' --output text)"
    aws amplify create-branch --app-id "$APP_ID" --branch-name "$RAMA" >/dev/null
  fi
  ORIGEN_FRONTEND="$(url_web "$APP_ID")"
  aws amplify update-app --app-id "$APP_ID" --custom-rules "$REGLA_SPA" >/dev/null   # Reglas al día en cada despliegue.
}

escribir_env_frontend() {
  local s u archivo=frontend/.env.production
  : > "$archivo"
  for s in "${SERVICIOS[@]}"; do
    u="$(url_servicio "$s")"
    if [ -n "$u" ] && [ "$u" != "None" ]; then
      echo "VITE_API_$(echo "$s" | tr '[:lower:]' '[:upper:]')=$u" >> "$archivo"
    fi
  done
}

preparar_docs() {
  # Swagger: genera los specs desde los serverless.yml y publica junto a ellos las URLs reales de cada API.
  paso "Documentación: generando OpenAPI"
  python3 scripts/generar_openapi.py || fallo "no se pudo generar la documentación OpenAPI."
  cp docs/openapi/*.json frontend/public/docs/
  local s u sep="" salida=frontend/public/docs/urls.json
  printf '{' > "$salida"
  for s in "${SERVICIOS[@]}"; do
    u="$(url_servicio "$s" | tr -d '\015')"
    if [ -n "$u" ] && [ "$u" != "None" ]; then
      printf '%s"%s":"%s"' "$sep" "$s" "$u" >> "$salida"; sep=","
    fi
  done
  printf '}
' >> "$salida"
}

publicar_frontend() {
  paso "Frontend: compilando"
  escribir_env_frontend
  preparar_docs
  (cd frontend && npm install --silent --no-audit --no-fund && npm run build) || fallo "falló la compilación del frontend."
  rm -f frontend/dist.zip
  (cd frontend/dist && zip -qr ../dist.zip .)   # el contenido de dist, no la carpeta

  paso "Frontend: publicando en Amplify"
  local job url estado i respuesta
  # JSON y no texto: en Windows la salida de texto de la CLI trae \r y rompe la URL de subida.
  respuesta="$(aws amplify create-deployment --app-id "$APP_ID" --branch-name "$RAMA" --output json)" \
    || fallo "la CLI no pudo publicar. Sube frontend/dist.zip en la consola de Amplify: app trazora-$STAGE, rama $RAMA."
  job="$(printf '%s' "$respuesta" | python3 -c 'import json,sys; print(json.load(sys.stdin)["jobId"])')"
  url="$(printf '%s' "$respuesta" | python3 -c 'import json,sys; print(json.load(sys.stdin)["zipUploadUrl"])')"
  curl --fail -sS -T frontend/dist.zip "$url" || fallo "no se pudo subir el .zip a Amplify."
  aws amplify start-deployment --app-id "$APP_ID" --branch-name "$RAMA" --job-id "$job" >/dev/null
  for i in $(seq 1 60); do
    estado="$(aws amplify get-job --app-id "$APP_ID" --branch-name "$RAMA" --job-id "$job" \
      --query 'job.summary.status' --output text | tr -d '\015')"
    case "$estado" in
      SUCCEED) echo "Publicado: $(url_web "$APP_ID")"; return 0 ;;
      FAILED|CANCELLED) fallo "Amplify terminó en estado $estado (trabajo $job)." ;;
    esac
    sleep 5
  done
  fallo "Amplify no terminó a tiempo (trabajo $job)."
}
