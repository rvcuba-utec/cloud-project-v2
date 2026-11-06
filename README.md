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
| `./seed.sh --escala 0.01` | Carga una muestra de datos |
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
```

## Restricción de concurrencia

La carga masiva va **directa a DynamoDB con boto3, nunca por API Gateway ni Lambda**. No se hacen pruebas de carga: superar el límite de Lambdas concurrentes puede causar el bloqueo de la cuenta de Academy.

## Diseño

Ver `ideas/implementation-plan-v4.md` e `ideas/implementation-plan-v3.md`.
