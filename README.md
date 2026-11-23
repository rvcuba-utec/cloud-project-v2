# Trazora FSM

SaaS multitenant de gestión de servicios en campo (*field service management*), en AWS: serverless y basado en eventos. Un coordinador crea órdenes y programa visitas; el técnico las atiende desde el celular, registra el parte con fotos, y la orden y la agenda se actualizan solas.

## Qué incluye

| Parte | Detalle |
|---|---|
| Backend | Siete microservicios Lambda (`usuarios`, `clientes`, `tecnicos`, `analitica`, `ordenes`, `agenda`, `partes`) detrás de **un solo API Gateway REST por ambiente**, con DynamoDB por servicio |
| Eventos | Colas SQS con sus DLQ: `ordenes`, `agenda` y `analitica` se actualizan por eventos (p. ej. al finalizar un parte, la visita pasa a Finalizada y la orden a Por cerrar) |
| Frontend | React + Vite + TypeScript, Tailwind y TanStack Query, publicado en AWS Amplify. Fechas en DD/MM/AAAA y textos en español |
| Roles | `ADMIN` (usuarios), `COORDINADOR` (órdenes, clientes, agenda, panel) y `TECNICO` (Mi día, atención de visitas, fotos) |
| Multitenant | Cada empresa (`CLIMALIMA`, `FRIOSUR`, `TECNINORTE`) ve solo sus datos; el código de empresa va en el inicio de sesión |

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
| `./warmup.sh` | Reactiva los disparadores SQS (Academy los apaga al cerrar el laboratorio) y calienta las Lambdas. Úsalo siempre tras reiniciar el laboratorio |
| `./destroy.sh` | Elimina un stage en AWS, pidiendo confirmación |
| `./clean.sh` | Borra las herramientas y credenciales locales; no toca AWS |
| `scripts/verificar_cuenta.sh` | Comprueba que la cuenta admite el diseño, con recursos temporales |

Si caducan las credenciales, pega las nuevas en el mismo archivo y repite el comando.

## Ambientes desplegados y acceso

Los tres ambientes están desplegados (22/11/2026) con esta versión: un solo API Gateway por ambiente, tablas, bucket, colas y web propios. Cada uno tiene la carga completa de datos (más de 30 000 registros de negocio por servicio). Los datos son los mismos en los tres, porque la semilla no depende del ambiente, pero cada ambiente los guarda en sus propias tablas y es independiente de los otros.

| Ambiente | Web (Amplify) | API |
|---|---|---|
| `dev` | https://main.d2zgo6pqtrwczf.amplifyapp.com | https://h7az8rww6b.execute-api.us-east-1.amazonaws.com/dev |
| `test` | https://main.dlbo1sbvowvke.amplifyapp.com | https://szciqmek93.execute-api.us-east-1.amazonaws.com/test |
| `prod` | https://main.d3l65ifqp12a1w.amplifyapp.com | https://l900waylcd.execute-api.us-east-1.amazonaws.com/prod |

Los conteos de cada ambiente están en `docs/evidencias/conteos-dev.md`, `conteos-test.md` y `conteos-prod.md`. `test` y `prod` exigen el secreto `trazora/<stage>/usuarios/password-pepper` en Secrets Manager antes de crear las cuentas de demo (ver `docs/SECRETS_MANAGER_ACADEMY.md`).

Los siete microservicios comparten la URL de la API. Las URLs cambian si se destruye y se vuelve a desplegar el stage. Para otro stage, los comandos llevan `--stage`, por ejemplo `./warmup.sh --stage prod`.

## Cuentas de demo

Para entrar a la web de cada ambiente, en el login se escribe el **código de empresa**, el correo y la contraseña. Hay tres empresas (CLIMALIMA, FRIOSUR, TECNINORTE) y cada una tiene tres roles: `ADMIN` (usuarios), `COORDINADOR` (órdenes, clientes, agenda, panel) y `TECNICO` (Mi día, visitas y partes, pensado para celular). Cada empresa solo ve sus propios datos. Las contraseñas son distintas en cada ambiente.

Cuentas sugeridas para una revisión rápida: el coordinador de CLIMALIMA para el flujo completo y el técnico de CLIMALIMA para la atención de visitas.

### dev: https://main.d2zgo6pqtrwczf.amplifyapp.com

| Empresa (código) | Rol | Correo | Contraseña |
|---|---|---|---|
| CLIMALIMA | ADMIN | `admin@climalima.example.com` | `ig5Iu0oQyZNtB1itSzWe` |
| CLIMALIMA | COORDINADOR | `coordinador@climalima.example.com` | `gN0mZfajnsZ55NbG4Yt2` |
| CLIMALIMA | TECNICO | `tecnico@climalima.example.com` | `GWqrmXhSjDVu_N0qEyJA` |
| FRIOSUR | ADMIN | `admin@friosur.example.com` | `rOSonZzsDKKe-UiQs6f7` |
| FRIOSUR | COORDINADOR | `coordinador@friosur.example.com` | `JDSLIXk41rmNkDImeOQw` |
| FRIOSUR | TECNICO | `tecnico@friosur.example.com` | `PWF3aUANz7NMa7vdvbRV` |
| TECNINORTE | ADMIN | `admin@tecninorte.example.com` | `mwIH3jPGP9OKMmqVBBI7` |
| TECNINORTE | COORDINADOR | `coordinador@tecninorte.example.com` | `jkgXi9iflWAu9iDsKIJV` |
| TECNINORTE | TECNICO | `tecnico@tecninorte.example.com` | `2iTFKSy3AreoT45ZHeTi` |

### test: https://main.dlbo1sbvowvke.amplifyapp.com

| Empresa (código) | Rol | Correo | Contraseña |
|---|---|---|---|
| CLIMALIMA | ADMIN | `admin@climalima.example.com` | `WPMRqjVJ02JZr78Rq6kM` |
| CLIMALIMA | COORDINADOR | `coordinador@climalima.example.com` | `HuO5d_kY8oad2sSc6Xgw` |
| CLIMALIMA | TECNICO | `tecnico@climalima.example.com` | `7bSh9MP8eX8bKp6qKUa8` |
| FRIOSUR | ADMIN | `admin@friosur.example.com` | `WFJt35TbMqDHrh62zPFx` |
| FRIOSUR | COORDINADOR | `coordinador@friosur.example.com` | `Co3rXAG62b1mX--9V_Id` |
| FRIOSUR | TECNICO | `tecnico@friosur.example.com` | `l1WFYGg9L7czus51Ui_z` |
| TECNINORTE | ADMIN | `admin@tecninorte.example.com` | `5ejv1T8_ynpQJzvN00Sb` |
| TECNINORTE | COORDINADOR | `coordinador@tecninorte.example.com` | `JKlxWmHBF7dOAc9lHppG` |
| TECNINORTE | TECNICO | `tecnico@tecninorte.example.com` | `1bCNleU39ASEVPBqbz0g` |

### prod: https://main.d3l65ifqp12a1w.amplifyapp.com

| Empresa (código) | Rol | Correo | Contraseña |
|---|---|---|---|
| CLIMALIMA | ADMIN | `admin@climalima.example.com` | `xqku2ikMHqSlE7mygrNI` |
| CLIMALIMA | COORDINADOR | `coordinador@climalima.example.com` | `Qj6XJwWLxLGYmr15cBiJ` |
| CLIMALIMA | TECNICO | `tecnico@climalima.example.com` | `hFSP_ybUyDaQ-DjKoL-U` |
| FRIOSUR | ADMIN | `admin@friosur.example.com` | `m8Y_HqCI851S5Wjtz1xw` |
| FRIOSUR | COORDINADOR | `coordinador@friosur.example.com` | `hRQGaq_QUIJcJ6IxN_MK` |
| FRIOSUR | TECNICO | `tecnico@friosur.example.com` | `QmTs9vd2gnY8RgrPylER` |
| TECNINORTE | ADMIN | `admin@tecninorte.example.com` | `h0Vi-Jd3O4e6unDxP_1x` |
| TECNINORTE | COORDINADOR | `coordinador@tecninorte.example.com` | `bVXt0GTJRGeDp3j_sC4p` |
| TECNINORTE | TECNICO | `tecnico@tecninorte.example.com` | `2jtalaedHFX_XNe5BWXX` |

`./deploy.sh` crea estas cuentas con `scripts/seed/bootstrap_admins.py` y las guarda también en `.demo-credentials` (fuera de Git). Cambian si se vuelve a crear el stage; para regenerarlas: `python3 scripts/seed/bootstrap_admins.py --stage <stage>`.

## Pruebas

```bash
./test.sh                  # backend y frontend (45 pruebas de vitest), sin AWS
python scripts/validar_ambientes.py  # resuelve los stacks de dev, test y prod sin consultar AWS (requiere login de Serverless)
scripts/pruebas_aws.sh     # contra AWS; crea algunos datos de prueba
scripts/pruebas_web.sh     # recorrido completo en un navegador real, instalado dentro del proyecto
```

Pruebas de navegador con Playwright en `tests/e2e/` (`cd tests/e2e && npm install`; las credenciales salen de `.demo-credentials`):

| Script | Qué hace |
|---|---|
| `recorrido.mjs <url-web>` | Flujo completo: crea una orden, programa la visita, el técnico la atiende en móvil con foto, finaliza el parte y el coordinador cierra la orden |
| `flujo.mjs <url-web> <url-api> <carpeta>` | Unas 50 comprobaciones de la interfaz: login, permisos por rol, órdenes, clientes, agenda, técnico en móvil y usuarios |
| `exploratorio.mjs <url-web> <url-api> <carpeta>` | Recorre todas las pantallas por rol y tamaño, y registra errores de consola, respuestas 4xx/5xx, desborde horizontal y tiempos |
| `verificar.mjs <url-web> <carpeta>` | Comprueba las correcciones de usabilidad (fechas, avisos en español, validaciones, móvil) |

Para el frontend: `cd frontend && npm run dev` (local), `npm test` y `npm run lint`.

## Restricción de concurrencia

La carga masiva va **directa a DynamoDB con boto3, nunca por API Gateway ni Lambda**. No se hacen pruebas de carga: superar el límite de Lambdas concurrentes puede causar el bloqueo de la cuenta de Academy.

## Carga de datos

La carga no depende de esta laptop: se puede repetir sin duplicar y reanudar si caduca la sesión, porque los ID solo dependen de la semilla y de la fecha base (guardada en `.local-env/`). Mide primero con `--escala 0.01`.

## Arquitectura del backend

La [auditoría de los siete servicios](docs/AUDITORIA_BACKEND_AWS_ACADEMY.md) compara el laboratorio consultado con la configuración de la rama. Cada ambiente tiene **un solo API Gateway REST**, creado por el stack compartido, al que se conectan directamente las Lambdas de los siete microservicios (sin VPC, VPC Link ni ALB). La [guía de ambientes](docs/AMBIENTES_DEV_TEST_PROD.md) describe las rutas, el autorizador y el orden de despliegue.

**Migración de stacks existentes:** esta versión se desplegó sobre un stage `dev` limpio, tras destruir el anterior con `./destroy.sh`. Si un ambiente ya tiene la versión anterior, inspecciona los change sets antes de ejecutar `./deploy.sh`, porque los servicios dejan de crear su propio gateway. Ver [ambientes](docs/AMBIENTES_DEV_TEST_PROD.md).

## Limitaciones conocidas

- **Disparadores SQS:** AWS Academy los apaga al cerrar el laboratorio. Sin ellos las visitas y las órdenes no se actualizan tras finalizar un parte. Ejecuta `./warmup.sh` tras cada reinicio.
- **Primer acceso lento:** la primera carga tras un rato sin uso tarda unos 7 s por el arranque en frío de las Lambdas; `./warmup.sh` las calienta.
- **Historial de la orden:** aún no registra la programación de visitas ni los cambios de prioridad.
- **Clientes:** el sistema no impide crear dos clientes con el mismo nombre.
- Las ausencias de técnicos no se pueden eliminar desde la API.

## Documentación

| Tema | Dónde |
|---|---|
| Arquitectura y ambientes | `docs/AMBIENTES_DEV_TEST_PROD.md` |
| Rutas de la API | `docs/api.md` y `docs/postman/` |
| Datos, claves y patrones de acceso | `docs/datos/` |
| Guion de la demo | `docs/guia-demo.md` |
| Evidencias | `docs/evidencias/` |
| Propuesta y planes | `ideas/` |
