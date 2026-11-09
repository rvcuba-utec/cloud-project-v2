# Trazora FSM: plan de implementación v2 (backend, infraestructura y pruebas)

Versión 2 de [`implementation-plan.md`](implementation-plan.md).
**Basado en:** [`proposal.md`](proposal.md), [`aws-architecture.md`](aws-architecture.md), [`guidelines.md`](../guidelines/guidelines.md) y los 13 talleres de `materials/`
**Fuera de alcance:** frontend, a cargo de otro integrante. La sección 4 define lo que el backend le entrega.

## Cómo leer este plan

Cada decisión técnica lleva una etiqueta según su origen:

| Etiqueta | Significado |
|---|---|
| **[CLASE]** | Se usa tal como se vio en los talleres. |
| **[CLASE+]** | Parte de lo visto en clase, con un ajuste que se explica. |
| **[NO EN MATERIALES]** | No aparece en `materials/`. Puede deberse a que se verá más adelante en el curso, a que lo exige el enunciado o a que aporta una ventaja clara. |

"Taller N" se refiere al archivo `materials/N-*.pdf`; por ejemplo, el taller 4 es `4-serverless-1.pdf`.

Cuando lleguen nuevos talleres, hay que compararlos con este plan. Si el docente enseña otra forma razonable de hacer lo mismo, conviene adoptarla.

### Qué cambia en la v2

Se añadieron los talleres 12 (SQS y DLQ) y 13 (SNS → SQS → Lambda con filtro, EventBridge). Con ellos, SQS, la DLQ y el fan-out SNS → SQS pasan a **[CLASE]**. La v2 también recorta lo que más complejidad añadía sin ser necesario.

| Cambio | Efecto |
|---|---|
| **Se descarta el outbox con DynamoDB Streams** | Los eventos se publican con `sns.publish` directo tras guardar (taller 10). Desaparecen 3 Lambdas publicadoras, los bloques `StreamSpecification` y `stream` del YML, los ítems `OUTBOX` y `republicar_outbox.py`. |
| **Se descarta `ReportBatchItemFailures`** | Los consumidores usan `batchSize: 1` y lanzan excepción; la DLQ recoge el mensaje (taller 12). |
| **Se descarta `RawMessageDelivery`** | Los consumidores parsean `json.loads(body['Message'])`, como en el taller 13. |
| **Se descartan TTL, alarmas de CloudWatch y GitHub Actions** | Eran opcionales y no aportan a los mínimos del enunciado. |
| **SQS y DLQ pasan a [CLASE]** | La prueba 3 de F0 deja de ser bloqueante: solo hay que comprobar que se puede declarar en el YML. |
| **Pruebas de F0: de 10 a 8** | Se eliminan Streams y TTL. |

El detalle de cada elemento que sigue siendo **[NO EN MATERIALES]**, con los archivos que cambian, está en la sección 2.2.

---

## 1. Situación actual

**El repositorio solo contiene documentos: todavía no hay código.**

**Peso en la rúbrica:** backend 8, diagrama 2 y avance 3. Es decir, 13 de 20 puntos dependen directa o parcialmente de este plan.

Varias fases pueden avanzar en paralelo según el reparto de la propuesta (sección 16.1). La dependencia que no se puede saltar es **F0 → F1 → resto**, porque todos los servicios necesitan el autorizador y la librería común.

---

## 2. Qué se vio en clase y qué falta

### 2.1. Cubierto por los materiales

| Necesidad del proyecto | Qué se vio | Taller |
|---|---|---|
| Tablas multitenant | `tenant_id` como clave de partición, ID como clave de ordenamiento, claves compuestas con `#` | 1, 2 |
| Índices secundarios | Concepto de GSI y LSI, con ejemplo de GSI | 2 |
| CRUD en Python | Lambda con Python 3.12, boto3 y `query`, `put_item`, `update_item`, `get_item` | 3 |
| API REST | API Gateway REST con CORS, pruebas con Postman | 3 |
| Seguridad | `t_usuarios`, `t_tokens_acceso`, token UUID con expiración, cabecera `Authorization`. Cognito **no** está disponible en Academy | 4 |
| Despliegue | Serverless Framework, `org`, `role: .../LabRole`, `serverless login` | 5 |
| Stages y rendimiento | `--stage dev/test/prod`, memoria de Lambda, `curl` | 6 |
| Variables y recursos | UUID, `environment`, tablas en `resources` con nombre por stage (`dev-t_comentarios`), `sls remove` | 7 |
| S3 | Buckets y objetos desde Lambda; bucket declarado en `serverless.yml` (ejercicio propuesto) | 6, 7 |
| Observabilidad | Logs JSON con `print`, formato `tipo`/`log_datos`, Logs Insights, filtros por `tenant_id` | 8 |
| Dependencias | `pip3 install -r requirements.txt -t .` y `package.include` | 9 |
| SNS | Tema estándar, `publish` con `MessageAttributes` y filtro por atributo | 10 |
| S3 orientado a eventos | Notificación S3 a Lambda, tenant extraído de la clave del objeto, publicación en SNS | 11 |
| SQS | Cola estándar, envío desde Lambda, lectura desde Lambda, Lambda disparada por la cola | 12 |
| Cola de errores (DLQ) | DLQ con `maxReceiveCount` (2 en clase); el mensaje fallido llega a la DLQ tras los reintentos | 12 |
| Fan-out SNS → SQS | Cola suscrita al tema con política de filtro por atributo (`tenant_id`); la Lambda lee `json.loads(body['Message'])` | 13 |
| CORS de las respuestas de error | Casillas "Default 4XX / Default 5XX" al habilitar CORS en API Gateway | 12 |

El taller de web scraping (9) no aporta funcionalidad a este proyecto, salvo la forma de empaquetar dependencias. El patrón SQL (RDS, Single Database Multiple Schemas) no aplica porque todo el proyecto usa DynamoDB. El uso de EventBridge del taller 13 (disparar una Lambda cada minuto) tampoco aplica: aquí los eventos nacen de acciones de negocio.

### 2.2. No cubierto por los materiales

Leyenda: **PY** = código Python, **YML** = `serverless.yml`, **JSON** = forma de los ítems o documentos de política embebidos.

| Elemento | ¿Por qué se necesita? | Dónde cambia | Lambda o servicio nuevo |
|---|---|---|---|
| **`TransactWriteItems` y escrituras condicionadas** | Evitar dobles reservas y efectos duplicados (núcleo de Agenda) | PY: `agenda/handlers/` (crear, reprogramar, cancelar), `partes/handlers/finalizar.py`, `ordenes/handlers/crear.py`, `usuarios/handlers/crear.py` y el helper `common/trazora_common/dynamo.py`. Usa el cliente de bajo nivel, con valores tipados | Ninguna |
| **Lambda Authorizer** | Autorización centralizada | PY: `usuarios/handlers/validar_token.py` (devuelve un documento de política IAM) y `common/auth.py`. YML: función en `usuarios/serverless.yml` sin evento `http`, y bloque `authorizer:` en cada evento `http` de los 7 servicios | 1 Lambda nueva (`validarToken`) |
| **Integración proxy de API Gateway** | Códigos HTTP reales | PY: todos los handlers y `common/respuesta.py` (`event['body']` llega como texto, la respuesta lleva `statusCode`, cabeceras y `body`). YML: solo se omite `integration: lambda` | Ninguna |
| **`generate_presigned_post` y CORS del bucket** | Subida directa desde el navegador con tope de 5 MB | PY: `partes/handlers/evidencias.py`. YML: `AWS::S3::Bucket` con `CorsConfiguration` y bloqueo de acceso público en `partes/serverless.yml`. **Frontend:** envía un POST `multipart/form-data` con los `fields` devueltos | Ninguna |
| **Paginación con `LastEvaluatedKey`** | Listar y contar más allá de 1 MB | PY: `common/trazora_common/dynamo.py` (cursor en base64) y los handlers `listar`. **Frontend:** usa `limit` y `cursor` | Ninguna |
| **`batch_writer`** | Carga masiva pedida por el docente | PY: `scripts/seed/cargar_datos.py`, que corre en la MV | Ninguna: no se despliega |
| **`lambda.invoke` entre Lambdas** | Romper el ciclo Agenda ↔ Órdenes (H1) | PY: `ordenes/handlers/cerrar.py` y `cancelar.py`. YML: variable de entorno con el nombre de la función en `ordenes/serverless.yml` | 1 Lambda nueva (`bloquearOrden`, sin evento) |
| **Recursos SQS, `QueuePolicy` y suscripción en el YML** | El enunciado exige SQS y Serverless. La clase los creó por consola | YML en MS3, MS4 y MS6, en `resources:`: 2 `AWS::SQS::Queue` (cola y DLQ con `RedrivePolicy`), `AWS::SQS::QueuePolicy` (JSON que permite a `sns.amazonaws.com` enviar, con condición `aws:SourceArn`) y `AWS::SNS::Subscription` con `FilterPolicy` (JSON). En `functions:`, un evento `sqs` con `batchSize: 1` | 3 Lambdas consumidoras. Un stack nuevo `infra/shared` con solo el tema SNS |
| **Idempotencia con `INBOX#` y `IDEMP#`** | Mensajes duplicados y creaciones repetidas | PY: `common/trazora_common/eventos.py` y `ordenes/handlers/crear.py`. JSON: nuevos tipos de ítem. **Frontend:** envía `Idempotency-Key` | Ninguna |
| **PBKDF2 con `hashlib`** | Guardar contraseñas de forma segura | PY: `usuarios/handlers/login.py` y `crear.py` | Ninguna |
| **`BatchGetItem`** | Evitar N+1 en `GET /tecnicos/disponibles` (H2) | PY: `tecnicos/handlers/disponibles.py` | Ninguna |
| **`GatewayResponse` con CORS** | CORS en los 401 y 403 (H12). Es el equivalente en YML de las casillas "Default 4XX/5XX" del taller 12 | YML: `resources:` de los 7 servicios | Ninguna |
| **pytest y moto** | Pruebas automatizadas | PY: `*/tests/*.py`, `requirements-dev.txt`, `pytest.ini`. Solo local: el patrón `!tests/**` lo excluye del paquete | Ninguna |
| **Amplify Hosting** | Lo exige el enunciado | A cargo de frontend | |

**Descartado en la v2** (estaba en la v1 como [NO EN MATERIALES]):

| Elemento | Por qué se descarta | Qué lo reemplaza |
|---|---|---|
| **DynamoDB Streams y outbox** | Es lo más caro fuera de lo visto: 3 Lambdas, YML de Streams, ítems `OUTBOX` y un script de recuperación | `sns.publish` directo tras guardar, como en el taller 10. Limitación en 6.F5 |
| **`ReportBatchItemFailures`** | No hace falta con lotes de 1 | `batchSize: 1` y excepción; la DLQ recoge el mensaje (taller 12) |
| **`RawMessageDelivery`** | El taller 13 parsea el sobre de SNS | `json.loads(body['Message'])` |
| **TTL de DynamoDB** | La expiración ya se comprueba en el código | Comprobación en el código |
| **Alarmas de CloudWatch y GitHub Actions** | Opcionales | pytest local; revisar la DLQ a mano |

### 2.3. Dónde este plan se aparta de lo visto en clase

Todas estas decisiones tienen ventaja concreta. Si el docente prefiere la forma vista en clase, la columna de plan B indica cómo volver a ella.

| # | Clase | Este plan | Ventaja | Costo | Plan B |
|---|---|---|---|---|---|
| 1 | Cada Lambda invoca `ValidarTokenAcceso` | **Lambda Authorizer** (ya decidido en la propuesta) | Una Lambda de negocio no puede olvidar la validación; el `tenant_id` llega desde un contexto confiable; hay caché | Configuración entre stacks | Patrón de clase, reutilizando la misma función `validar_token()` |
| 2 | `integration: lambda`: `statusCode` en el cuerpo y HTTP siempre 200 | **Integración proxy** (la predeterminada del framework) | El frontend recibe 400/401/403/404/409 reales, como pide la sección 8.3 de la propuesta | `body` llega como texto y hay que parsearlo | Ninguno necesario |
| 3 | `put_item` simple | **Transacciones y condiciones** | Dos personas no pueden reservar el mismo bloque | El doble de consumo de escritura | Sin plan B: es el núcleo de Agenda |
| 4 | `print(event)` en logs | **Logs JSON de clase, sin imprimir el evento completo** | `event` contiene el token de `Authorization`, y la propuesta prohíbe registrarlo | Ninguno | |
| 5 | Las diapositivas no muestran cómo se guarda la contraseña | **PBKDF2-HMAC-SHA256 con `hashlib`** | Es derivación robusta, está en la librería estándar y no requiere compilar dependencias | Login más lento: ajustar iteraciones y memoria (taller 6) | |
| 6 | Se publica en SNS directamente desde la Lambda (taller 10) | **Igual, tras guardar** | Es lo visto en clase; no añade Lambdas | No hay garantía transaccional si la Lambda falla entre guardar y publicar | Ver F5: la repetición idempotente del POST vuelve a publicar |

**Dónde este plan se acerca a la clase, respecto de la propuesta:**

- **Token opaco UUID con sesión en DynamoDB [CLASE]:** cierra la decisión abierta de la sección 9.1. Es lo visto en el taller 4, permite revocar sesiones y no requiere gestionar claves de firma. Se mantiene `t_sesiones`. Único ajuste: guardar el SHA-256 del token en lugar del token en claro.
- **Confirmación de evidencia con notificación S3 [CLASE]:** ver H6.
- **Publicación de eventos, SNS → SQS → Lambda y DLQ [CLASE]:** talleres 10, 12 y 13. Sustituye al outbox de la propuesta (sección 12.4), que se descarta.
- **Stages y nombres [CLASE]:** `dev-t_clientes`, `api-clientes-dev-listar`.

---

## 3. Problemas detectados en la propuesta

Son problemas que conviene resolver antes de programar, porque cambiarlos con 180 000 registros cargados obliga a recargar. Los cambios que afecten a contratos deben reflejarse en `proposal.md`, `aws-architecture.md` y el `.drawio`.

| # | Problema | Consecuencia | Solución propuesta |
|---|---|---|---|
| **H1** | **Dependencia circular de despliegue:** Agenda necesita la URL de Órdenes, y Órdenes la de Agenda para el bloqueo. | `${cf:...}` no se puede resolver en ninguno de los dos órdenes. | `bloquearOrden` se invoca con **`lambda.invoke`** por nombre determinista (`api-agenda-${stage}-bloquearOrden`), sin ruta pública. También resuelve "solo acepta llamadas de Órdenes" sin un secreto adicional. Reemplaza `POST /control-ordenes/{id}/bloqueo`. El diagrama del taller 4 muestra una Lambda llamando a otra. |
| **H2** | **N+1 llamadas al sugerir técnico:** con 50 técnicos por tenant, la sugerencia haría más de 100 llamadas HTTP encadenadas (perfil, jornadas y métricas por técnico). | Riesgo de superar el límite de 29 s de API Gateway. | Añadir `GET /tecnicos/disponibles?fecha=&especialidad=` (con `BatchGetItem` de jornadas y ausencias) y usar el `GET /analitica/tecnicos` que ya existe. En Agenda, cambiar la clave a `BLOQUE#<fecha_lima>#<tec>#<inicio_utc>` para leer los bloques del día con una sola consulta. |
| **H3** | **Clave de Analítica ineficiente:** con `TECNICO#TEC-001#METRICAS` y `TECNICO#TEC-001#DIA#...`, un ranking de 50 técnicos recorre unos 10 050 ítems por tenant. | Ranking lento y costoso. | Usar `METRICAS#<tec>` y `DIA#<fecha>#<tec>`. Dos consultas por prefijo devuelven como máximo 50 ítems cada una. |
| **H4** | **Tasas guardadas como valor fijo:** no se puede aplicar un incremento atómico a `tasa_resolucion_primer_intento` ni a `tiempo_promedio_atencion_min`. | Contadores incorrectos. | Guardar numeradores y denominadores (`primer_intento_resueltos`, `primer_intento_total`, `suma_minutos`, `n`) y calcular las tasas al leer. |
| **H5** | **Doble conteo:** `ParteFinalizado` y `VisitaCompletada` alimentan la misma tasa (sección 12.1). | Métricas duplicadas. | Actualizar los contadores **solo con `VisitaCompletada`**, y quitar `ParteFinalizado` del filtro de `q-analitica`. |
| **H6** | **El límite de 5 MB no se puede aplicar con un PUT prefirmado**, y la propuesta exige validarlo en el mecanismo de carga. | Se podrían subir archivos de cualquier tamaño. | Usar **`generate_presigned_post` con `content-length-range`** [NO EN MATERIALES]. Además, la notificación S3 a Lambda del taller 11 [CLASE] confirma la evidencia automáticamente y revisa tamaño y tipo. `POST /evidencias/{id}/confirmar` queda como respaldo idempotente. |
| **H7** | **Órdenes y visitas 1 a 1 en el generador (10 000 de cada una), incompatible con revisitas:** una orden cerrada con una sola visita `REQUIERE_REVISITA` es incoherente. | Datos inconsistentes y métricas sin variación. | Generar unas **10 600 visitas y 10 600 partes por tenant**: las 600 extra son segundas visitas. Se sigue superando el mínimo. |
| **H8** | **Falta `numero_visita_orden` en el control de Agenda:** los eventos lo necesitan (sección 12.2), pero `CONTROL_ORDEN` solo tiene `visitas_activas`. | MS6 no distingue revisitas. | Añadir `visitas_total` a `CONTROL_ORDEN`, incrementado dentro de la misma transacción. |
| **H9** | **Primer administrador:** `POST /usuarios` requiere un administrador, pero al inicio no existe ninguno. | Bloqueo inicial. | `scripts/seed/bootstrap_admins.py` crea un administrador por tenant, con contraseñas tomadas de variables de entorno. |
| **H10** | **Unicidad de correo por tenant:** un GSI no garantiza unicidad. | Cuentas duplicadas por concurrencia. | Ítem marcador `EMAIL#<email>` creado en la misma transacción con `attribute_not_exists`. El login lo lee directamente, sin GSI. |
| **H11** | **La caché del autorizador puede bloquear rutas válidas:** la política se guarda por token; si solo permite la ruta actual, las demás reciben 403 durante el TTL. | Errores 403 intermitentes. | El autorizador devuelve una política con comodín sobre la API. Los permisos por rol se comprueban en cada Lambda. |
| **H12** | **Errores sin CORS:** los 401 y 403 generados por API Gateway no llevan cabeceras CORS. | El navegador muestra error de CORS en lugar de "sesión vencida". | Declarar `GatewayResponse` con CORS en cada `serverless.yml`. |
| **H13** | **MS0 duplica la validación de token:** la propuesta dice que sus rutas validan "dentro del servicio". | Dos caminos de autorización que mantener. | Usar el autorizador también en las rutas de MS0, excepto `login`. No hay autollamada: API Gateway lo invoca igual que a los demás. |
| **H14** | **`GET /visitas/{visita_id}`** aparece en las llamadas internas, pero no en la tabla principal de rutas (sección 8.3). | Contrato incompleto. | Añadirla. Un técnico solo puede consultar sus propias visitas. |

**Decisiones abiertas que este plan propone cerrar:**

| Decisión | Propuesta |
|---|---|
| Región | `us-east-1`, la que más aparece en los talleres. Confirmar en F0. |
| Token | Opaco, con sesión (sección 2.3). |
| Volumen de MS0 | **Cargar 30 000 perfiles inactivos y sin credenciales de todos modos.** Cuesta muy poco y elimina el riesgo si el docente responde tarde o que sí cuentan. Preguntar igualmente. |
| Caché del autorizador | 60 s. Se documenta que una revocación puede tardar hasta 60 s en surtir efecto. |
| Publicación de eventos | `sns.publish` directo tras guardar (taller 10). Reemplaza el outbox de la sección 12.4 de la propuesta; hay que reflejarlo en `proposal.md`, `aws-architecture.md` y el `.drawio`. |

---

## 4. Lo que el backend entrega a frontend

Se entrega desde F1 y se mantiene actualizado:

1. **URLs por stage:** `scripts/exportar_env.sh <stage>` genera un `.env` con las 7 URLs a partir de `sls info` o las salidas de CloudFormation.
2. **Contrato:** colección de Postman [CLASE] en `docs/api/`, con ejemplos de éxito y de error de cada ruta.
3. **Formato de error único:** `{"error": {"codigo": "HORARIO_OCUPADO", "mensaje": "...", "detalle": {}}}`.
4. **Autenticación:** cabecera `Authorization: Bearer <token>`; el 401 indica que hay que volver a iniciar sesión.
5. **Idempotencia:** los POST de creación aceptan la cabecera `Idempotency-Key` (UUID generado una vez por intento).
6. **Paginación:** `?limit=&cursor=`; la respuesta devuelve `next_cursor`, un `LastEvaluatedKey` opaco.
7. **Subida de evidencia:** la respuesta incluye `url` y `fields` para un POST `multipart/form-data` a S3 (H6).
8. **Consistencia eventual:** tras finalizar un parte, el frontend consulta periódicamente la orden hasta ver el cambio.
9. **CORS:** `*` durante el desarrollo; al final, el dominio de Amplify en API Gateway y en el bucket.

**Para coordinar:** el enunciado pide "automatizar todo el despliegue". Hay que acordar con quien lleva frontend si Amplify se declara también como recurso (`AWS::Amplify::App`) o se documenta como paso manual. Declararlo requiere un token de GitHub que no debe quedar en el repositorio.

---

## 5. F0: verificación de AWS Academy y base del repositorio

### 5.1. Verificar el laboratorio antes de escribir código

Varias piezas del diseño no se vieron en clase y **no hay garantía de que Academy las permita**. Esta prueba evita descubrir un bloqueo cuando ya sea tarde. Se hace con un stack desechable en la cuenta que se usará para la demo.

| # | Qué comprobar | Si falla |
|---|---|---|
| 1 | Autorizador declarado en otro stack, con su permiso de invocación | Patrón de clase: `ValidarTokenAcceso` desde cada Lambda |
| 2 | **SNS → SQS declarado en el YML** (tema en `infra/shared`, cola, DLQ con `RedrivePolicy`, `QueuePolicy` y suscripción con filtro) y entrega de un mensaje de prueba | Los talleres 12 y 13 demuestran que funciona por consola. Crear las colas como en clase y documentarlo. **Consultar al docente si falla el YML** |
| 3 | SQS → Lambda con `batchSize: 1`, tiempo de visibilidad de 6 veces el timeout y mensaje fallido en la DLQ | Ajustar el tiempo de visibilidad; el taller 12 usa la consola |
| 4 | Notificación S3 a Lambda con el bucket creado por el framework (evitar `existing: true`, que crea una Lambda auxiliar con rol propio) | Solo `POST /evidencias/{id}/confirmar` |
| 5 | `generate_presigned_post` con LabRole y CORS del bucket | PUT prefirmado y validar el tamaño al confirmar |
| 6 | `lambda.invoke` entre Lambdas con LabRole | Ruta interna con un secreto en variable de entorno |
| 7 | Límite de concurrencia: `aws lambda get-account-settings` | Limitar con `maximumConcurrency` en los consumidores |
| 8 | Duración de la sesión y si la API sigue respondiendo con el laboratorio detenido | Iniciar el laboratorio antes de cada demo |

**Dos riesgos operativos que hay que decidir primero:**

- **Una sola cuenta "dueña" del despliegue.** Cada alumno tiene su propia cuenta de Academy, así que los datos y las URLs de la demo viven en una sola. El equipo debe elegir cuál.
- **Las credenciales duran 4 horas (taller 5).** Cada sesión empieza por actualizar `~/.aws/credentials`. La carga masiva debe poder reanudarse (F6) y la demo debe iniciarse con el laboratorio ya activo.

También hay que confirmar con quien lleva frontend que Amplify funciona en esa misma cuenta.

### 5.2. Estructura del repositorio

Sigue la sección 15.1 de la propuesta, con los siguientes añadidos:

```text
backend/
  common/trazora_common/   # auth, errores, respuesta, logs, ids, claves, eventos, dynamo, http_interno
  usuarios/  clientes/  tecnicos/  ordenes/  agenda/  partes/  analitica/
    serverless.yml
    handlers/              # una función por ruta o evento; solo traduce HTTP y dominio
    dominio/               # reglas puras, sin boto3, fáciles de probar
    tests/
infra/shared/serverless.yml   # tema SNS fsm-eventos
scripts/
  deploy_all.sh  remove_all.sh  exportar_env.sh  sync_common.sh
  seed/
tests/
  integracion/  e2e/
docs/
  api/  datos/  evidencias/
```

**Decisiones de base:**

- **Python 3.12 y boto3 [CLASE].** Sin dependencias externas en las Lambdas: boto3 ya viene en el entorno y `hashlib` y `urllib` son estándar. Así no hace falta `pip -t .` ni plugins, y los paquetes quedan pequeños (mejor arranque en frío, taller 6).
- **Librería común copiada al desplegar [CLASE+].** `sync_common.sh` copia `backend/common/trazora_common` a cada servicio antes de `sls deploy`; las copias se excluyen de Git. Es más simple que Lambda Layers [NO EN MATERIALES], cuyos ARN versionados complican el despliegue entre stacks.
- **Librería común limitada a lo técnico:** identidad, errores, logs y formato de evento. Las reglas de negocio se quedan en cada servicio.
- **Un repositorio común.** El enunciado pide "enlaces públicos a repositorios", y un único repositorio cumple. Los talleres usaban uno por API; esa separación agregaría trabajo sin beneficio aquí.

### 5.3. Plantilla de `serverless.yml`

```yaml
org: <org-del-equipo>                 # [CLASE] taller 5
service: api-clientes

provider:
  name: aws
  runtime: python3.12                 # [CLASE]
  region: us-east-1
  stage: ${opt:stage, 'dev'}          # [CLASE] taller 6
  timeout: 25                         # API Gateway corta a los 29 s; clase usa 30
  memorySize: 256                     # ajustar con Logs Insights, taller 6 y 8
  iam:
    role: arn:aws:iam::${aws:accountId}:role/LabRole   # [CLASE+] no depende de la cuenta
  environment:                        # [CLASE] taller 7
    TABLE_NAME: ${sls:stage}-t_clientes

custom:
  authorizer:                         # [NO EN MATERIALES] sección 2.3
    arn: arn:aws:lambda:${aws:region}:${aws:accountId}:function:api-usuarios-${sls:stage}-validarToken
    type: token
    identitySource: method.request.header.Authorization
    resultTtlInSeconds: 60

package:
  patterns: ['!tests/**', '!**/__pycache__/**']

functions:
  listar:
    handler: handlers/listar.lambda_handler
    events:
      - http:                         # [CLASE] API REST; sin integration: lambda (proxy)
          path: clientes
          method: get
          cors: true
          authorizer: ${self:custom.authorizer}

resources:
  Resources:
    TablaClientes:                    # [CLASE] taller 7
      Type: AWS::DynamoDB::Table
      Properties:
        TableName: ${self:provider.environment.TABLE_NAME}
        BillingMode: PAY_PER_REQUEST
        AttributeDefinitions:
          - { AttributeName: PK, AttributeType: S }
          - { AttributeName: SK, AttributeType: S }
        KeySchema:
          - { AttributeName: PK, KeyType: HASH }
          - { AttributeName: SK, KeyType: RANGE }
    Default4XX:                       # H12
      Type: AWS::ApiGateway::GatewayResponse
      Properties:
        RestApiId: { Ref: ApiGatewayRestApi }
        ResponseType: DEFAULT_4XX
        ResponseParameters:
          gatewayresponse.header.Access-Control-Allow-Origin: "'*'"
          gatewayresponse.header.Access-Control-Allow-Headers: "'*'"
```

La clase usa `tenant_id` como clave de partición. La propuesta usa `PK = TENANT#<id>`, y es el mismo Patrón 1 del taller 1. Esto concentra cada tenant en una partición: el taller 2 recomienda alta cardinalidad, pero con unos 10 MB por tenant no hay problema de capacidad. Se documenta como limitación consciente, tal como hace la propuesta (sección 10.1).

### 5.4. Orden de despliegue

Con H1 resuelto, las dependencias forman un grafo sin ciclos:

```text
infra/shared → usuarios → clientes, tecnicos, analitica → ordenes → agenda → partes
```

`scripts/deploy_all.sh <stage>` ejecuta `sync_common.sh` y luego `sls deploy --stage <stage>` en ese orden [CLASE]. Las URLs se leen con `${cf:api-clientes-${sls:stage}.ServiceEndpoint}`.

Serverless Compose [NO EN MATERIALES] haría esto mismo de forma declarativa, pero un script es más simple de entender y explicar en la exposición. No se usa.

### 5.5. Librería común

| Módulo | Contenido |
|---|---|
| `auth.py` | `obtener_contexto(event)` lee `usuario_id`, `tenant_id` y `rol` **solo** de `requestContext.authorizer`. `requiere_rol(...)`. |
| `respuesta.py` | Respuesta proxy con CORS y serialización de `Decimal` (boto3 no acepta `float` y devuelve `Decimal`). |
| `errores.py` | Excepciones con código HTTP y decorador `@api_handler` con `try/except` [CLASE, taller 8]. |
| `logs.py` | `{"tipo": "INFO|ERROR", "tenant_id": ..., "correlation_id": ..., "log_datos": {...}}` [CLASE, taller 8], sin token ni `password_hash`. |
| `eventos.py` | Crea el evento de la sección 12.2 de la propuesta y lo publica con `sns.publish` (con `MessageAttributes`, taller 10); lee mensajes SQS con `json.loads(body['Message'])` (taller 13); registro `INBOX#`. |
| `dynamo.py` | Paginación con cursor, transacciones con reintento e idempotencia (`IDEMP#<clave>`). |
| `http_interno.py` | Llamada a otro servicio con `urllib`, reenviando el token del usuario, con timeout y traducción de errores. |

**Regla para todo el equipo:** `tenant_id` nunca se lee del body, de la ruta ni de la query. Se comprobará con una prueba de arquitectura (sección 7.1).

**Salida de F0:** las pruebas de la sección 5.1 tienen resultado, `sls deploy` de un servicio mínimo funciona, y pytest corre en local.

---

## 6. Implementación por fases

### F1. MS0 Usuarios y autorizador

**Es la pieza crítica:** todos los demás servicios dependen de ella.

1. Tablas: `t_usuarios` (`PK`, `SK`, con marcador `EMAIL#`, H10) y `t_sesiones` (`token_hash`, `expira_en`; la expiración se comprueba en el código).
2. `POST /auth/login` (público):
   - Comprueba cuenta, `estado` y contraseña con PBKDF2 y `hmac.compare_digest`.
   - Genera un UUID4 [CLASE, taller 7] y guarda su SHA-256 con expiración de 8 horas.
   - Devuelve el mismo error para "usuario inexistente" y "contraseña incorrecta".
3. `validarToken` (autorizador de tipo TOKEN):
   - Lee la sesión y comprueba la expiración en el código.
   - Lee el usuario y comprueba que siga activo.
   - Devuelve `Allow` con comodín y `context` = `usuario_id`, `tenant_id`, `rol` (H11).
4. `POST /usuarios`, `GET /usuarios`, `GET /usuarios/me`, `PATCH /usuarios/{id}`, todas con el autorizador (H13). Nunca devuelven `password_hash`.
5. Regla: un `PATCH` no puede cambiar `tenant_id` ni permitir que un usuario eleve su propio rol. Desactivar un usuario revoca sus sesiones.
6. `bootstrap_admins.py` (H9) y `exportar_env.sh`.
7. Ajustar las iteraciones de PBKDF2 y la memoria del login midiendo con Logs Insights [CLASE, talleres 6 y 8].

**Salida:** login de ClimaLima y FríoSur; el token de una empresa no sirve para operar en la otra; sin token responde 401. Pruebas de MS0 en verde.

### F2. MS1 Clientes, MS2 Técnicos y MS3 Órdenes

**MS1 Clientes**

- Rutas de la sección 8.3. Búsqueda por prefijo con un GSI: `TENANT#X#CLIENTE` + `nombre_normalizado#id`.
- Los clientes con historial se desactivan; no se borran.

**MS2 Técnicos**

- Rutas de la sección 8.3, más `GET /tecnicos/disponibles` (H2).
- Jornadas y ausencias con claves `JORNADA#<tec>#<fecha>` y `AUSENCIA#<tec>#<fecha>`.

**MS3 Órdenes (parte síncrona)**

- Crear orden con validación en Clientes e idempotencia (transacción con `IDEMP#`).
- Si la misma clave llega con otro contenido, responde 409.
- Listar con 2 GSI: `TENANT#X#ESTADO#<estado>` y `TENANT#X#CLIENTE#<id>`, ordenados por `creada_en#id`.
- `PATCH` de prioridad con control de versión. `cerrar` y `cancelar` se completan en F3, cuando exista el bloqueo.

**Salida:** crear una orden con un cliente de otro tenant falla (tratado como 404); repetir una creación devuelve la misma orden.

### F3. MS4 Agenda

**Es el servicio con más riesgo técnico.** Conviene que `dominio/` sea código puro, para probarlo sin AWS.

1. `dominio/bloques.py`: duraciones en múltiplos de 30 min y máximo 4 h, cálculo de bloques con el extremo final excluido, y diferencia entre reservas antiguas y nuevas.
2. `dominio/estados.py`: transiciones de la sección 11.5.
3. `POST /visitas` con **`TransactWriteItems`** [NO EN MATERIALES] que incluye:
   - La visita.
   - Un bloque por cada 30 min con `attribute_not_exists`.
   - `CONTROL_ORDEN` con `acepta_programaciones = true`, sumando `visitas_activas` y `visitas_total` (H8).
4. Antes de la transacción: validar orden y técnico vía HTTP, y crear el control de forma idempotente. Después de la transacción: publicar el evento de visita programada (sección 12 de la propuesta) con `eventos.publicar(...)`.
5. Reprogramar: como máximo 8 bloques nuevos + 8 liberados + 2 ítems = 18, dentro del límite de 100 por transacción. Conserva los bloques compartidos y comprueba `version`.
6. Cancelar: libera bloques y resta del contador; una repetición no vuelve a restar.
7. `iniciar` solo por el técnico asignado.
8. `GET /visitas`, `GET /visitas/{id}` (H14), con GSI por técnico y por orden.
9. `GET /disponibilidad`, y con `sugerir=true`:
   - Filtros obligatorios: `GET /tecnicos/disponibles` y bloques del día (H2).
   - Orden: `GET /analitica/tecnicos`, con timeout de 2 s; si falla, usa el orden predeterminado y omite la justificación.
10. `bloquearOrden`, solo para `lambda.invoke` (H1): condición `visitas_activas = 0` e idempotente por `operacion_id`.
11. Volver a MS3 y completar `cerrar` y `cancelar` (secciones 11.8 y 11.9). Si la respuesta es desconocida, la orden se mantiene en `CIERRE_EN_PROCESO` y se reintenta.

**Salida:** ejecutando 2 reservas simultáneas sobre AWS real, solo una se confirma; una reprogramación fallida conserva la reserva original.

### F4. MS5 Partes y S3

1. Bucket privado declarado en `serverless.yml` [CLASE, taller 7]: bloqueo de acceso público, CORS y nombre `trazora-evidencias-${stage}-${aws:accountId}`.
2. `POST /visitas/{id}/partes` y `PUT /partes/{id}`, validando en Agenda que la visita esté `EN_ATENCION` y asignada a ese técnico.
3. `POST /partes/{id}/evidencias` con `generate_presigned_post` [NO EN MATERIALES]: clave generada por el backend, JPEG o PNG, máximo 5 MB, 5 minutos de validez.
4. Lambda `onEvidenciaSubida` activada por S3 [CLASE, taller 11]: obtiene el tenant de la clave con `split('/')[1]`, igual que en clase; revisa con `head_object` y marca `CONFIRMADA`.
5. `POST /evidencias/{id}/confirmar` como respaldo idempotente.
6. `GET /partes/{id}`: verifica el permiso y genera URLs temporales de lectura.
7. `POST /partes/{id}/finalizar`: transacción con el parte y el marcador único `MARCA_VISITA#<visita>`; después, publica `ParteFinalizado` con un `event_id` derivado del parte. Si se reintenta, devuelve el mismo resultado **y vuelve a publicar el mismo `event_id`** (los consumidores son idempotentes por `INBOX#`), lo que recupera una publicación fallida. Otro parte para esa visita responde 409.

**Salida:** subir una foto real, verla con una URL temporal y comprobar que un archivo de más de 5 MB se rechaza.

### F5. Eventos (publicación directa) y MS6 Analítica

**Infraestructura**

1. `infra/shared`: tema SNS **estándar** `fsm-eventos` [CLASE, taller 10]. Stack sin Lambdas.
2. Cada consumidor (MS3, MS4 y MS6) declara en su `serverless.yml` su cola, su DLQ, su `QueuePolicy` y su suscripción [CLASE en concepto, talleres 12 y 13; NO EN MATERIALES en YML]. Así, cada servicio controla su filtro.
   - Filtro por `event_type`. También se envía `tenant_id` como atributo, igual que en los talleres 10 y 13.
   - Sin `RawMessageDelivery`: el consumidor lee `json.loads(body['Message'])`, como en el taller 13.
   - Tiempo de visibilidad de 6 veces el timeout de la Lambda; `maxReceiveCount: 3` (la clase usa 2; se sube uno por posibles conflictos de transacción).
   - Evento `sqs` con `batchSize: 1`. Si el handler falla, lanza la excepción: SQS reintenta y, agotados los intentos, el mensaje pasa a la DLQ (taller 12).

**Publicación (MS3, MS4 y MS5)**

3. `eventos.publicar(...)` en `trazora_common` hace `sns.publish` con `MessageAttributes` (`event_type`, `tenant_id`), como en el taller 10. Los handlers lo llaman **después** de guardar.
4. **Limitación conocida:** si la Lambda falla entre guardar y publicar, el evento no se publica. Se mitiga así:
   - Un fallo de publicación se registra como `ERROR` con el `event_id`.
   - Repetir el `POST` idempotente (finalizar parte, programar visita) vuelve a publicar el mismo `event_id`.
   - Los consumidores son idempotentes por `INBOX#`, así que un duplicado no cambia los contadores.
   - Se documenta en el informe como limitación frente al outbox de la propuesta.

**Consumidores**

5. Mismo patrón: transacción con `INBOX#<event_id>` + efecto de negocio. Si el `INBOX` ya existe, el efecto se omite.
6. **MS4:** `ParteFinalizado` lleva la visita a `FINALIZADA` y resta de `visitas_activas`. Después publica `VisitaCompletada` con `resultado`, `numero_visita_orden` y duración, con un `event_id` derivado del `event_id` de entrada. Si el `INBOX` ya existía, **se omite el efecto pero se vuelve a publicar `VisitaCompletada`**: así una publicación fallida se recupera con el reintento de SQS. Si la visita ya cambió, registra el conflicto.
7. **MS3:** mantiene en la orden un resumen por visita y deriva el estado con una **función pura** `derivar_estado(resumen)`. Un evento con `aggregate_version` menor o igual se ignora, porque SQS estándar no garantiza el orden.
8. **MS6:** incrementos atómicos con `ADD`, según H3, H4 y H5. `maximumConcurrency` bajo, para reducir conflictos de transacción sobre el contador del tenant. API de solo lectura, limitada a administrador y coordinador.

**Salida:** finalizar un parte actualiza visita, orden y métricas en segundos; el mismo mensaje enviado 2 veces no cambia los contadores; un mensaje inválido termina en la DLQ.

### Avance del 30 %

El enunciado no define cómo se calcula ese porcentaje. Se propone mostrar:

- Los 7 servicios desplegados en `dev` con `deploy_all.sh`.
- El recorrido crear orden → sugerir → reservar → iniciar → parte con foto → eventos → cerrar, en Postman o con el frontend si ya está disponible.
- Rechazo de acceso cruzado entre 2 tenants.
- Logs Insights filtrando por `tenant_id` [CLASE].
- Diagrama actualizado y plan de carga.

**Plan si algo no funciona para el avance:** si SNS → SQS no se puede declarar en el YML, crear las colas por consola como en los talleres 12 y 13, documentarlo y consultar al docente. La publicación ya es directa (taller 10), así que no hay un plan B de publicación.

### F6. Generador y carga masiva

**Requisito previo:** las claves y los GSI quedan **congelados** antes de la carga final. Cambiar una clave reemplaza la tabla y obliga a repetir la carga.

1. `scripts/seed/cargar_datos.py` con `--stage`, `--seed`, `--escala`, `--dry-run` y `--solo <servicio>`.
2. Pruebas progresivas: primero `--escala 0.01` y después escala completa en `test` o `prod`.
3. Usar los mismos constructores de claves que el backend (`trazora_common`). Así el generador no se desincroniza y rellena también los atributos de los GSI.
4. IDs deterministas, derivados de la semilla: se puede repetir la carga sin duplicar registros, lo que permite **reanudar** si la sesión de 4 horas termina a la mitad.
5. Ejecutar en la MV Desarrollo con `batch_writer` [NO EN MATERIALES] y directo a DynamoDB, **sin API Gateway ni Lambda**, como pidió el docente. La carga no publica eventos.

**Volúmenes por tenant** (ajustados con H7):

| Servicio | Registros de negocio | Total para 3 tenants |
|---|---|---:|
| MS0 Usuarios | 10 000 perfiles inactivos sin credenciales, más cuentas de demo | ≥ 30 000 |
| MS1 Clientes | 10 000 clientes, más sus ubicaciones | ≥ 30 000 |
| MS2 Técnicos | 50 técnicos y 10 000 jornadas | 30 150 |
| MS3 Órdenes | 10 000 cerradas y 20 programadas | 30 060 |
| MS4 Agenda | ~10 600 visitas finalizadas y 20 programadas | ~31 860 |
| MS5 Partes | ~10 600 partes finalizados | ~31 800 |
| MS6 Analítica | 50 métricas, 10 000 snapshots diarios y snapshots mensuales | ≥ 30 150 |

**Reglas de coherencia:**

- **Fechas:** las jornadas y los snapshots cubren los mismos 200 días, con parte hacia el futuro, para que existan jornadas durante la demo.
- **Resultados:** las primeras visitas se distribuyen en `RESUELTO`, `REQUIERE_REVISITA` y `NO_ATENDIDO`. Toda orden cerrada termina con una visita `RESUELTO`.
- **Agenda:** solo las visitas programadas crean bloques y `CONTROL_ORDEN`, con contadores coherentes. Los bloques no cuentan para el mínimo.
- **Analítica:** se calcula a partir de lo ya generado, no al azar, para que los números cuadren con Agenda y Órdenes.
- **Evidencias:** los partes históricos no llevan referencias a archivos inexistentes.

**Reporte:** `scripts/seed/contar.py` recorre todas las páginas y genera `docs/evidencias/conteos.md`, por servicio, tenant y tipo de entidad, separando negocio de ítems técnicos. Incluye fecha, semilla y stage.

**Costo:** con pago por uso, medir primero con `--escala 0.01`. Cada GSI multiplica las escrituras, así que no se debe añadir ninguno sin una consulta que lo justifique. Consultar el saldo de Academy antes y después.

**Salida:** tres tenants con el volumen exigido; la consola y el reporte coinciden.

### F7. Endurecimiento

1. Ejecutar toda la matriz de la sección 7 con los datos completos.
2. Comprobar que las listas responden paginadas con 30 000 registros y medir tiempos.
3. Probar los fallos a propósito:
   - Apuntar temporalmente la URL de Analítica a un destino inválido y comprobar que Agenda sigue funcionando.
   - Enviar un mensaje inválido y verlo en la DLQ.
   - Hacer fallar la publicación a propósito (ARN del tema inválido en una variable de entorno), comprobar que el error queda en logs y que repetir el `POST` de finalizar vuelve a publicar sin duplicar efectos.
4. Revisar en Logs Insights que no aparezcan tokens ni contraseñas.
5. Guardar las consultas [CLASE, taller 8] en `docs/evidencias/logs-insights.md`: errores por servicio, duración y memoria por Lambda, y eventos por `correlation_id`.
6. Despliegue limpio: `deploy_all.sh` en un stage nuevo, para comprobar que es reproducible. Luego retirarlo con `sls remove` [CLASE, taller 7].

### F8. Documentación del backend y ensayo

1. **Diagrama de arquitectura (2 pts):** actualizar `.drawio`, `aws-architecture.md` y `proposal.md` con H1, H5, H6, la notificación S3 y la publicación directa en lugar del outbox (sección 12.4 de la propuesta). Debe coincidir con lo desplegado.
2. **Diseño de datos por microservicio:** estructura JSON, claves y patrones de acceso, en `docs/datos/`. El enunciado pide JSON para NoSQL; no hace falta diagrama entidad-relación.
3. **Secciones de backend del informe:** arquitectura, seguridad multitenant, eventos, despliegue, carga y conteos, pruebas y limitaciones (incluido el caso de LabRole).
4. **README:** prerrequisitos, despliegue, carga y demo, con comandos reales ya probados.
5. **Comprobar el repositorio público:** sin credenciales en el historial, con `.gitignore` para `.env` y `credentials`.
6. **Ensayo completo** del guion de la sección 18 de la propuesta, partiendo de un laboratorio recién iniciado. Medir el tiempo que toma actualizar credenciales y tener todo listo.

---

## 7. Estrategia de pruebas

### 7.1. Niveles

| Nivel | Herramienta | Qué prueba | Cuándo |
|---|---|---|---|
| **Unitario** | pytest [NO EN MATERIALES] | Reglas puras: bloques, estados, `derivar_estado`, ranking, hash, formato de evento | En cada cambio |
| **Componente** | pytest + moto [NO EN MATERIALES] | Handlers con eventos API Gateway simulados: aislamiento, permisos, idempotencia, transacciones, `INBOX` | En cada cambio |
| **Arquitectura** | pytest | Revisar el código: ningún handler lee `tenant_id` del body, path o query; ningún servicio usa la tabla de otro | En cada cambio |
| **Integración** | pytest contra stage `test` | AWS real: autorizador, SNS/SQS, S3, concurrencia con hilos | Al terminar cada fase |
| **E2E** | pytest o Postman/`curl` [CLASE] | Recorrido completo con 2 tenants | Antes de cada entrega |

**Por qué moto:** ofrece pruebas rápidas sin gastar créditos ni depender de la sesión de 4 horas. **Limitación:** no reproduce concurrencia real ni permisos de LabRole. Por eso la reserva concurrente y los flujos de eventos también se prueban sobre AWS.

Las pruebas se ejecutan en local. El despliegue es manual, porque las credenciales de Academy caducan.

### 7.2. Matriz de aceptación (sección 17 de la propuesta)

| Caso | Nivel | Evidencia |
|---|---|---|
| API sin autenticación rechaza | Integración | 401 en las 7 APIs |
| Gestión de usuarios aislada | Componente + E2E | Admin de ClimaLima contra FríoSur |
| Token de otro tenant, alterando body, path o query | Componente + E2E | Se ignora el `tenant_id` enviado |
| Cuenta inactiva | Componente + Integración | Sin login; sesión revocada tras el TTL de caché |
| Aislamiento entre empresas | Componente + E2E | FríoSur recibe 404 sobre una orden de ClimaLima |
| Aislamiento de analítica | Componente | Solo métricas propias |
| Permiso del técnico | Componente | Otro técnico recibe 403 |
| Referencias válidas | Componente | Cliente de otro tenant rechazado |
| Creación repetida | Componente + Integración | Mismo ID con la misma clave |
| **Reserva concurrente** | **Integración, sobre AWS** | N hilos, exactamente 1 confirmado |
| Jornada inválida | Unitario + Componente | Fuera de jornada o con ausencia |
| Reprogramación fallida | Componente + Integración | Reserva original intacta |
| Cancelación repetida | Componente | El contador baja una sola vez |
| Visita en ejecución | Unitario | Transición rechazada |
| Evidencia | Integración | Subida real, lectura autorizada, más de 5 MB rechazado |
| Parte no resuelto | Integración | Orden en `REQUIERE_REVISITA` |
| Mensaje duplicado | Componente + Integración | Mismo mensaje 2 veces, mismo contador |
| Sugerencia de técnico | Unitario + E2E | Orden y justificación correctos |
| Analítica no disponible | Integración | Agenda programa con el orden predeterminado |
| Mensaje atrasado | Unitario + Componente | No revierte el estado |
| Publicación fallida | Integración | Repetir el `POST` vuelve a publicar el mismo `event_id`, sin duplicar efectos |
| **Cierre concurrente** | **Integración, sobre AWS** | Cierre y reserva en paralelo; nunca ambos |
| Datos | Reporte | `conteos.md` |
| Carga directa | Evidencia | Script, MV, conteos, sin invocaciones de Lambda durante la carga |
| Despliegue | Manual | `deploy_all.sh` en un stage nuevo |

**Pruebas añadidas por este plan:** autorizador con caché entre rutas (H11), 401 con cabeceras CORS (H12), correo duplicado concurrente (H10), y ausencia de secretos en los logs.

---

## 8. Riesgos y recortes

| Riesgo | Mitigación |
|---|---|
| Academy bloquea un servicio del diseño | Verificación de F0, con plan B para cada punto |
| Sesión de 4 h durante una carga o la demo | Carga reanudable; iniciar el laboratorio con antelación |
| La cuenta dueña queda inutilizable | Despliegue reproducible y carga repetible con semilla; probarlo en F7 |
| Complicaciones en MS4 o en eventos | Lógica pura primero; la publicación ya es directa, sin outbox |
| Un evento se pierde entre guardar y publicar | Repetir el `POST` idempotente vuelve a publicar el mismo `event_id`; consumidores idempotentes por `INBOX#`; limitación documentada |
| Conflictos de transacción en contadores | Reintentos vía SQS y `maximumConcurrency` bajo |
| Cambios de contrato que afecten a frontend | Colección de Postman actualizada y aviso; congelar los contratos tras el avance |
| Nuevos talleres cambian lo esperado | Comparar cada taller nuevo con la sección 2 |

**Si hace falta, recortar en este orden:**

1. Búsqueda de clientes por prefijo (dejar solo el listado paginado).
2. Reprogramación con bloques compartidos (solo cambiar a horarios sin solapamiento).

Ya recortados en esta versión: outbox y Streams, `ReportBatchItemFailures`, `RawMessageDelivery`, TTL, alarmas de CloudWatch y GitHub Actions. **Si tras F7 hay margen, el primero en reponerse es el outbox.**

**No se recorta:** los mínimos del enunciado (5 microservicios protegidos, S3, SNS, SQS, Serverless Framework, 30 000 registros por servicio en 3 tenants, demo con 2 tenants), el aislamiento entre tenants y la reserva sin duplicados.

**MS6 y sugerencia de técnico:** el mínimo de 5 microservicios se cumple sin ellos, pero son el principal diferenciador de la propuesta. Solo se recortan como último recurso.

---

## 9. Preguntas para el docente o asistente

Ninguna bloquea el inicio:

1. ¿MS0 Usuarios también debe tener 30 000 registros? (El plan los carga de todos modos, como perfiles inactivos.)
2. ¿Se aceptan el Lambda Authorizer y `TransactWriteItems`, aunque no aparezcan en los talleres?
3. ¿Se acepta publicar en SNS desde la Lambda después de guardar (taller 10), sin garantía transaccional entre ambos pasos? (SQS y DLQ ya se vieron en los talleres 12 y 13.)
4. ¿Un solo repositorio cumple con "enlaces públicos a repositorios"?
5. ¿Qué se espera exactamente en el avance del 30 %?
6. ¿Amplify también debe desplegarse de forma automatizada, o solo el backend?

---

## 10. Próximos pasos inmediatos

1. Elegir la cuenta de Academy dueña del despliegue y confirmar `org` de Serverless Framework.
2. Ejecutar la verificación de la sección 5.1.
3. Aceptar o ajustar H1-H14. Los que cambian contratos: H1, H2, H5, H6, H13, H14.
4. Crear la estructura del repositorio, la librería común y la plantilla de `serverless.yml`.
5. Implementar MS0 y compartir con frontend la primera versión del contrato.
6. Enviar las preguntas de la sección 9.
