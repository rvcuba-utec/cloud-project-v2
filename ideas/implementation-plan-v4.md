# Trazora FSM: plan de construcción y despliegue (v4)

**Estado:** aprobado (sección 5).
**Alcance:** backend, frontend, despliegue, datos, pruebas y documentación técnica.
**Diseño detallado:** [`implementation-plan-v3.md`](implementation-plan-v3.md) sigue vigente para rutas, datos, eventos y pantallas, incluidos los cambios H1-H22. Este documento prevalece en servicios permitidos, construcción y despliegue.

---

## 1. Servicios que se usan

La regla es no añadir servicios fuera de los materiales, salvo los que el enunciado exige.

| Servicio | Para qué | Respaldo |
|---|---|---|
| Lambda | Lógica de los 7 microservicios | Talleres 3 a 13 |
| API Gateway (REST) | Una API por microservicio | Talleres 3 a 6 |
| DynamoDB | Una persistencia por microservicio | Talleres 1, 2 y 7 |
| S3 | Evidencias | Talleres 6, 7 y 11 |
| SNS | Publicación de eventos | Talleres 10, 11 y 13 |
| SQS con DLQ | Una cola por consumidor | Talleres 12 y 13 |
| EventBridge | Reenvío programado de eventos pendientes | Taller 13 |
| CloudWatch | Logs y Logs Insights | Taller 8 |
| IAM (`LabRole`) | Rol de todas las Lambdas | Taller 5 |
| Serverless Framework / CloudFormation | Despliegue del backend | Talleres 5 a 7 |
| EC2 (MV Desarrollo) | Carga masiva con boto3 | Talleres 5 y 7; indicación del docente |
| **Amplify Hosting** | Publicar el frontend | **No está en los talleres.** Lo exige el enunciado y ya se usó en un proyecto anterior |

**No se usan:**

| Servicio | Motivo |
|---|---|
| **VPC y VPC Link** | **No hacen falta.** VPC Link sirve para que API Gateway llegue a recursos privados dentro de una VPC, como un balanceador. Aquí API Gateway invoca directamente a Lambda, y las Lambdas usan DynamoDB, S3, SNS y SQS sin VPC. |
| ALB y Docker en EC2 | Son del modelo con servidores; este proyecto debe ser serverless. |
| Cognito | No disponible en Academy (taller 4). |
| RDS | Todo el proyecto usa DynamoDB, que el enunciado permite. |
| DynamoDB Streams, TTL, Lambda Layers | Se reemplazaron con piezas vistas en clase o con código. |
| Secrets Manager, Parameter Store | Las contraseñas de demo se generan en local y no se suben a Git. |
| Step Functions, Glue, Athena | No se necesitan para los requisitos del proyecto. |
| Amplify Auth, Gen 2 y Libraries | Añadirían Cognito y roles. Amplify solo publica archivos. |

**Técnicas no vistas, dentro de servicios permitidos:** estas no agregan servicios, pero conviene poder explicarlas en la exposición.

| Técnica | Por qué se mantiene | Alternativa de clase si se requiere |
|---|---|---|
| Lambda Authorizer | Una Lambda de negocio no puede olvidar validar el token | `ValidarTokenAcceso` en cada Lambda (taller 4) |
| Integración proxy | Permite que el frontend reciba códigos HTTP reales | `integration: lambda`, peor para el frontend |
| Transacciones de DynamoDB | Evitan reservas duplicadas. **No tienen sustituto razonable** | Ninguna |
| URL prefirmada de S3 | El navegador sube sin credenciales de AWS y con límite de 5 MB | Subida a través de Lambda, limitada por API Gateway |
| `batch_writer` y paginación | Necesarios con 30 000 registros | Ninguna |
| `lambda.invoke` para el bloqueo | Evita una dependencia circular y una ruta pública | El taller 4 muestra una Lambda llamando a otra |

---

## 2. Cómo será el despliegue para el equipo

**Objetivo: un solo comando, repetible, y sin editar archivos de cada servicio.**

### Primera vez

```bash
git clone <repositorio> && cd <repositorio>
cp config.example.env config.env   # stage y org de Serverless
serverless login                   # una vez por máquina
# Pegar las credenciales de AWS Academy en ~/.aws/credentials
./deploy.sh
```

Al terminar, muestra:

```text
Web:       https://main.<appId>.amplifyapp.com
Cuentas:   .demo-credentials (fuera de Git)
Pruebas:   12/12 correctas
```

### Comandos

| Comando | Qué hace |
|---|---|
| `./deploy.sh` | Despliega o actualiza todo: backend, frontend, cuentas de demo y pruebas básicas |
| `./deploy.sh backend` | Solo los servicios del backend |
| `./deploy.sh frontend` | Solo compila y publica la web |
| `./deploy.sh ordenes` | Solo un microservicio |
| `./deploy.sh --stage prod` | Lo mismo, en otro stage |
| `./seed.sh --escala 0.01` | Carga una muestra de datos |
| `./seed.sh` | Carga completa y genera el reporte de conteos |
| `./check.sh` | Comprueba que el sistema funciona, sin desplegar |
| `./warmup.sh` | Calienta las Lambdas antes de una demo |
| `./destroy.sh` | Elimina el stage, pidiendo confirmación escribiendo su nombre |

### Qué hace `./deploy.sh`

1. **Comprueba el entorno:** herramientas, sesión de Serverless y credenciales. Si caducaron, lo dice claramente e indica dónde pegar las nuevas.
2. **Crea la app de Amplify**, si no existe, para conocer su dominio.
3. **Despliega el backend** en el orden correcto: compartido → usuarios → clientes, técnicos, analítica → órdenes → agenda → partes.
4. **Genera las variables `VITE_*`** con las URLs reales, compila la web y la publica.
5. **Crea las cuentas de demo**, si no existen, con contraseñas generadas.
6. **Ejecuta las pruebas básicas** y muestra el resultado.

### Por qué es fácil de usar

- **Sin datos fijos de una cuenta:** el ID de cuenta, el rol y las URLs se obtienen automáticamente. Mover la demo a la cuenta de otro integrante es cambiar las credenciales y volver a ejecutar.
- **Se puede repetir sin riesgo:** si falla, se corrige y se ejecuta otra vez; lo que ya está bien no se altera.
- **Errores claros:** si falla, indica el paso y el servicio.
- **Funciona en la MV Desarrollo o en una laptop:** requiere `aws`, `node`, `npm`, `serverless` y `python3`. La carga final se ejecuta en la MV, como pidió el docente.
- **Sin dependencias externas en las Lambdas:** no hay que instalar librerías con `pip` ni usar Docker o plugins.

### Publicación del frontend

- **Método elegido:** compilar en local, crear un `.zip` y publicarlo con la CLI de Amplify. No requiere conectar GitHub ni copiar variables a la consola.
- **Si la CLI no tiene permiso:** el script deja `frontend/dist.zip` listo para subir en la consola de Amplify, con "Deploy without Git".
- **Alternativa con GitHub:** si prefieren publicar con cada `push`, como en el proyecto anterior con sus variables `VITE_*`, se configuran esas variables en Amplify y se añade `amplify.yml`. Es incompatible con publicar por `.zip` en la misma rama, así que hay que elegir uno.

### Puntos que hay que comprobar en su cuenta

| Punto | Por qué | Si falla |
|---|---|---|
| Publicar en Amplify por CLI | Los permisos de la CLI pueden ser distintos a los de la consola | Subir el `.zip` en la consola |
| Tomar `org` de `config.env` | Serverless podría no aceptar variables en ese campo | `deploy.sh` genera ese valor al desplegar |
| Las 10 pruebas de la sección 5.1 del v3 | Autorizador entre stacks, SNS → SQS en YML, EventBridge, S3 y otras | Cada una tiene un plan B en el v3 |

---

## 3. Qué voy a construir

```text
config.example.env   deploy.sh   seed.sh   check.sh   warmup.sh   destroy.sh   README.md
infra/shared/        # tema SNS
backend/
  common/            # identidad, errores, logs, eventos, DynamoDB, llamadas internas
  usuarios/  clientes/  tecnicos/  ordenes/  agenda/  partes/  analitica/
frontend/            # React + Vite + TypeScript
scripts/             # pasos internos de los comandos y generador de datos
tests/               # integración y recorrido completo
docs/                # API, datos, evidencias
```

### Etapas

Cada etapa termina desplegada y comprobada en AWS, no solo en local.

| # | Qué se construye | Cómo se comprueba |
|---|---|---|
| 0 | Verificación de la cuenta y comandos de despliegue con un servicio mínimo | Las 10 pruebas; `./deploy.sh` publica una página en Amplify |
| 1 | MS0 Usuarios, autorizador, librería común; login web | Dos empresas inician sesión; acceso cruzado rechazado |
| 2 | MS1 Clientes, MS2 Técnicos, MS3 Órdenes; sus pantallas | Crear una orden desde la web, con validación entre servicios |
| 3 | MS4 Agenda; agenda y Mis visitas | N reservas simultáneas sobre AWS: solo una se confirma |
| 4 | MS5 Partes y S3; pantalla de atención | Subida real de una foto desde el navegador; más de 5 MB se rechaza |
| 5 | SNS, SQS, DLQ y EventBridge | Un parte actualiza visita y orden; los duplicados no alteran datos; un fallo forzado se recupera |
| 6 | MS6 Analítica, sugerencia de técnico, panel y dashboard | Métricas correctas; Agenda funciona aunque Analítica falle |
| 7 | Generador de datos y carga | Reporte con al menos 30 000 registros por servicio y 3 tenants |
| 8 | Pantallas restantes, adaptación al celular, manejo de errores | Lista de la sección 9.6 del v3, en la URL de Amplify |
| 9 | Toda la matriz de pruebas, despliegue limpio y guion de demo | Sección 7 del v3; `./deploy.sh` en un stage nuevo funciona a la primera |
| 10 | README, datos, API y actualización de propuesta, arquitectura y diagrama | Los documentos coinciden con lo desplegado |

### Pruebas

| Tipo | Herramienta | Qué cubre |
|---|---|---|
| Unitarias y de componentes | pytest y moto | Reglas de negocio, permisos, aislamiento e idempotencia, sin gastar créditos |
| Integración | pytest contra AWS | Concurrencia, eventos, S3 y autorizador reales |
| Frontend | Vitest | Cliente HTTP, errores y fechas |
| Recorrido completo | `./check.sh` y colección de Postman | Flujo de la demo con 2 tenants; evidencia para el informe |

pytest, moto y Vitest son herramientas locales: **no se despliegan ni añaden servicios a AWS.**

---

## 4. Cómo usaría su consola de AWS

**Qué necesito:**

1. **Credenciales de AWS Academy en `~/.aws/credentials` de esta máquina**, pegadas por ustedes, no en el chat. Las usaré por CLI.
2. **`serverless login`**, ejecutado por ustedes, porque abre el navegador.
3. **Renovar las credenciales cuando caduquen.** Duran unas 4 horas: si caducan, me detengo y aviso.

**Límites que voy a respetar:**

| Tema | Regla |
|---|---|
| Recursos | Solo creo y modifico los del proyecto: `api-*`, `dev-t_*`, `trazora-*`. No toco nada más de la cuenta. |
| Entorno | Trabajo en `dev`. La carga completa y otros stages solo con su autorización. |
| Eliminación | `./destroy.sh` y borrados de datos solo si me lo piden. |
| Costo | Reviso el saldo con ustedes antes de la carga y mido con una muestra del 1 %. |
| Secretos | Credenciales y contraseñas fuera de Git, de los logs y de mis mensajes. |
| Git | Trabajo en la rama `renzo` y hago commit solo si me autorizan. El repositorio debe quedar público para la entrega, sin secretos en el historial. |

---

## 5. Decisiones aprobadas

| # | Decisión | Resultado |
|---|---|---|
| 1 | Cambios H1-H22 del v3 | Aprobados. Se actualizarán la propuesta y el diagrama. |
| 2 | Publicación del frontend | `.zip` por CLI. El código vive en `frontend/`, dentro del mismo repositorio. |
| 3 | Técnicas no vistas | Se mantienen salvo que sean fácilmente sustituibles por lo visto en clase (sección 6). |
| 4 | Repositorio | Uno solo. |
| 5 | Perfiles de MS0 | Se cargan 30 000 inactivos, **directo a DynamoDB y nunca por Lambda** (sección 7). |
| 6 | Git | Commits locales por etapa en `renzo`. **Sin `push`.** |
| 7 | Informe y PowerPoint | Por ahora, solo contenido y evidencias en `docs/`. |

## 6. Revisión de técnicas no vistas

Criterio: se reemplaza lo que tiene un equivalente de clase con costo bajo y sin perder un requisito.

| Técnica | Resultado | Motivo |
|---|---|---|
| `BatchGetItem` | **Se reemplaza por `get_item`** [CLASE, taller 3] | Con 50 técnicos son como máximo 100 lecturas por consulta de disponibilidad: es aceptable y además simplifica el código, porque no hay que gestionar claves sin procesar. |
| Lambda Authorizer | Se mantiene | El código sería fácil de cambiar, pero el patrón de clase añade una invocación de Lambda por cada petición, incluidas las internas, sin caché. Dada la advertencia sobre concurrencia (sección 7), el autorizador con caché es más seguro. |
| Integración proxy | Se mantiene | Solo implica omitir `integration: lambda`, y da códigos HTTP reales al frontend. |
| Transacciones | Se mantienen | Sin equivalente en clase; la reserva sin duplicados depende de ellas. |
| URL prefirmada | Se mantiene | Subir a través de Lambda no admite imágenes de 5 MB: en base64 superan los 6 MB de carga de Lambda, y además consumiría concurrencia. |
| `batch_writer` | Se mantiene | Es la forma directa de carga que pidió el docente, sin Lambda. |
| Paginación | Se mantiene | Imprescindible con 30 000 registros. |
| `lambda.invoke` | Se mantiene | La relación entre Lambdas aparece en el taller 4. |
| PBKDF2 | Se mantiene | Los talleres no muestran cómo guardar contraseñas. |

## 7. Límite de concurrencia de AWS Academy

El docente advirtió que sobrecargar el límite de Lambdas concurrentes puede hacer que baneen la cuenta. Se trata como restricción dura.

| Regla | Aplicación |
|---|---|
| **Carga masiva sin Lambda** | `batch_writer` desde la MV, en un solo proceso, directo a DynamoDB. Sin API Gateway, Lambda ni eventos. |
| **La carga no dispara nada** | Sin Streams, escribir en DynamoDB no invoca ninguna Lambda. La carga no publica en SNS ni escribe en S3. |
| **Sin pruebas de carga** | Las pruebas de concurrencia usan 5 hilos como máximo, solo para verificar reservas y cierre. |
| **Consumidores limitados** | SQS con `batchSize: 1` y `maximumConcurrency: 2`. |
| **Tareas programadas moderadas** | El barrido corre cada 5 minutos, no cada minuto. |
| **Calentamiento moderado** | `warmup.sh` hace una petición secuencial por API. |
| **Frontend** | Consulta periódica cada 2 s durante 30 s como máximo, solo tras finalizar un parte. |
| **Comprobación inicial** | La verificación lee el límite real con `aws lambda get-account-settings`. |
