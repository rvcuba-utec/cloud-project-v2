# Arquitectura: un API Gateway por ambiente, sin ALB

Rama `proyecto-un-apigateway`, derivada de `fix/academy-alb-http-sin-acm-2026-11-17`.

## Qué es y qué no es

- **Un API Gateway REST por ambiente** (dev, test, prod: 3 en total), creado por `infra/shared`. A él se conectan las Lambdas de los 7 microservicios.
- Cada ruta apunta a una Lambda distinta (integración `AWS_PROXY`). Cada microservicio mantiene su stack, sus tablas y sus colas, y se despliega por separado.
- **No hay VPC, VPC Link ni ALB.** Las Lambdas no están dentro de una VPC. Usan DynamoDB, S3, SNS, SQS y Secrets Manager por sus endpoints de servicio.

## Diferencias frente a las otras ramas

| | `main` | rama con ALB | esta rama |
|---|---|---|---|
| API Gateway | uno por microservicio (7 URLs) | uno por ambiente | uno por ambiente |
| Camino a la Lambda | API Gateway → Lambda | API Gateway → VPC Link → ALB → Lambda | API Gateway → Lambda |
| Evento que recibe el handler | API Gateway | ALB (traducido por `alb.py`) | API Gateway |
| Autorizador | `token`, caché 60 s | `REQUEST`, caché 0 | `REQUEST`, caché 0 |
| URLs entre servicios | `ServiceEndpoint` de cada stack | `ApiUrl` único | `ApiUrl` único |
| Errores, logs, secretos, SQS por mensaje | no | sí | sí |

## Qué se quitó de la rama con ALB

- De `infra/shared`: VPC, subredes, grupos de seguridad, VPC Link, ALB, listener y sus salidas (`VpcLinkId`, `AlbArn`, `ListenerArn`, `AlbUrl`).
- `infra/ingreso-privado.cjs` y su uso en los 7 `serverless.yml`.
- `trazora_common/alb.py` y su test. `http.api_handler` ya no traduce eventos de ALB.
- `validar_token.py`: ya no devuelve `identidadAlb` ni rechaza cabeceras `X-Trazora-*`. Lee `Authorization` del evento `REQUEST` (también admite `TOKEN`).
- `scripts/validar_ingreso.py` y `scripts/probar_recorrido_local.py`.
- En `deploy.sh` y `config.example.env`: las zonas de disponibilidad `TRAZORA_AZ_ID_A/B`.

## Qué se conserva

Gateway compartido, autorizador único, `/visitas` compartido, URLs internas unificadas, contrato de error con `request_id`, logs estructurados, pepper en Secrets Manager, consumidores SQS con `ReportBatchItemFailures`, retención de logs por ambiente.

## Frontend

Sin cambios de código. `scripts/amplify.sh` escribe las siete variables `VITE_API_*` con la misma URL, que `scripts/lib.sh` toma del Output `ApiUrl` del stack compartido.

## Orden de despliegue

`infra/shared` primero y después los siete servicios (`./deploy.sh` ya lo hace así).

## Verificación hecha

- `./test.sh`: pruebas de backend en verde (common 132, usuarios 53, clientes 20, tecnicos 23, analitica 39, ordenes 57, agenda 72, partes 53, seed 14).
- Los YAML de `infra/shared` y de los 7 servicios se cargan sin error. El stack compartido ya solo define `ApiTrazora`, `Autorizador`, `Default4XX/5XX`, `Visitas`, `Visita` y `TemaEventos`.

## Pendiente de verificar con credenciales

- `serverless print/package` real (Serverless v4 exige login).
- `python scripts/validar_ambientes.py`.
- Despliegue en `test` y recorrido con la URL `execute-api`: login, 401 sin sesión, aislamiento entre empresas, rutas con parámetros, Analítica y eventos.
- Pruebas de frontend (`npm test`) con las dependencias instaladas.
