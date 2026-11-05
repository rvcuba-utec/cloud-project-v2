# Trazora FSM

SaaS multitenant de gestión de servicios en campo, en AWS: serverless y basado en eventos.

## Requisitos

`node` 20 o superior, `npm`, `python3`, `zip`, `curl` y una sesión de AWS Academy activa.

## Despliegue

```bash
./setup.sh                 # instala AWS CLI y Serverless dentro del proyecto
# Edita config.env y pega las credenciales de Academy en ~/.aws/credentials
npx serverless login       # una vez por máquina
./deploy.sh
```

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
| `./destroy.sh` | Elimina un stage, pidiendo confirmación |
| `scripts/verificar_cuenta.sh` | Comprueba que la cuenta admite el diseño, con recursos temporales |

Si caducan las credenciales, pega las nuevas y repite el comando.

## Pruebas

```bash
.venv/bin/python -m pytest      # backend, sin AWS
(cd frontend && npm test)       # frontend
```

## Restricción de concurrencia

La carga masiva va **directa a DynamoDB con boto3, nunca por API Gateway ni Lambda**. No se hacen pruebas de carga: superar el límite de Lambdas concurrentes puede causar el bloqueo de la cuenta de Academy.

## Diseño

Ver `ideas/implementation-plan-v4.md` e `ideas/implementation-plan-v3.md`.
