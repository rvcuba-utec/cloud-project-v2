# Trazora FSM

SaaS multitenant de gestión de servicios en campo, en AWS: serverless y basado en eventos.

## Requisitos

`node` 20 o superior, `npm`, `python3`, `zip`, `curl` y una sesión de AWS Academy activa.

## Despliegue

```bash
./setup.sh
# 1. En config.env: SLS_ORG y SERVERLESS_ACCESS_KEY (app.serverless.com: Settings > Access Keys)
# 2. Pegar las credenciales de AWS Academy en .local-env/home/.aws/credentials
./deploy.sh
```

**Todo queda dentro del proyecto:** AWS CLI, Serverless, Python 3.12, cachés y credenciales están en `.local-env/`, `.venv/` y `node_modules/`, fuera de Git. No se escribe en `~/`. Para quitarlo: `./clean.sh`.

| Comando | Qué hace |
|---|---|
| `./deploy.sh` | Despliega o actualiza todo, y lo comprueba |
| `./deploy.sh backend` | Solo el backend |
| `./deploy.sh frontend` | Solo compila y publica la web |
| `./deploy.sh <servicio>` | Solo un microservicio: `usuarios`, `clientes`, `tecnicos`, `analitica`, `ordenes`, `agenda`, `partes` |
| `./deploy.sh --stage prod` | Lo mismo, en otro stage |
| `./seed.sh --escala 0.01` | Carga una muestra de datos y genera el reporte de conteos |
| `./seed.sh` | Carga completa: más de 30 000 registros por servicio, en 3 empresas. Hazla desde la MV |
| `./seed.sh --dry-run` | Solo cuenta lo que generaría, sin escribir |
| `./check.sh` | Comprueba el sistema sin desplegar |
| `./warmup.sh` | Calienta las Lambdas antes de una demo |
| `./destroy.sh` | Elimina un stage en AWS, pidiendo confirmación |
| `./clean.sh` | Borra las herramientas y credenciales locales; no toca AWS |
| `scripts/verificar_cuenta.sh` | Comprueba que la cuenta admite el diseño, con recursos temporales |

Si caducan las credenciales, pega las nuevas en el mismo archivo y repite el comando.

## Pruebas

```bash
./test.sh                  # backend y frontend, sin AWS
scripts/pruebas_aws.sh     # contra AWS; crea algunos datos de prueba
scripts/pruebas_web.sh     # recorrido completo en un navegador real, instalado dentro del proyecto
```

## Restricción de concurrencia

La carga masiva va **directa a DynamoDB con boto3, nunca por API Gateway ni Lambda**. No se hacen pruebas de carga: superar el límite de Lambdas concurrentes puede causar el bloqueo de la cuenta de Academy.

## Carga de datos

La carga no depende de esta laptop: se puede repetir sin duplicar y reanudar si caduca la sesión, porque los ID solo dependen de la semilla y de la fecha base (guardada en `.local-env/`). Mide primero con `--escala 0.01`.

## Documentación

| Tema | Dónde |
|---|---|
| Arquitectura | `ideas/aws-architecture.md` y `diagrams/trazora-arquitectura-tecnica.drawio` |
| Rutas de la API | `docs/api.md` y `docs/postman/` |
| Datos, claves y patrones de acceso | `docs/datos/` |
| Guion de la demo | `docs/guia-demo.md` |
| Evidencias | `docs/evidencias/` |
| Propuesta y planes | `ideas/` |
