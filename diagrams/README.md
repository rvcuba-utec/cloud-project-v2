# Guía de estudio — Diagrama de arquitectura técnica de Trazora FSM

Explica cómo leer `trazora-arquitectura-tecnica.drawio`. Fuentes: [`ideas/proposal.md`](../ideas/proposal.md) y [`ideas/aws-architecture.md`](../ideas/aws-architecture.md).

> **Aviso:** las rutas, tablas y eventos salen de la propuesta. La columna «Lambda que origina» en la sección 5 es una **deducción** de los flujos de la sección 11 de la propuesta; el documento solo indica servicio origen, destino y ruta.

---

## 1. Idea general

Cada microservicio (MS) es un paquete independiente con:

| Pieza | Qué es |
|---|---|
| **API Gateway propia** | Una API por MS (7 en total). Recibe las peticiones HTTPS. |
| **Varias Lambdas** | Una por operación o ruta (`crearOrden`, `getOrden`…). No es una sola Lambda por MS. |
| **Tabla(s) DynamoDB propia(s)** | Solo las Lambdas de ese MS la usan. Otro servicio no la lee: le pide el dato a su API. |
| **Stack de CloudFormation** | Generado por Serverless Framework, uno por MS más uno compartido. |

Un MS «no está encendido»: sus Lambdas se ejecutan solo cuando llega una petición, un evento o un mensaje.

---

## 2. Colores y tipos de línea

### Cajas (Lambdas)

| Color | Tipo | Cómo se activa |
|---|---|---|
| Naranja | Lambda **HTTP** | Una petición que llega a la API Gateway del MS. |
| Rosa | Lambda **de evento** | Un mensaje en SQS o un cambio en DynamoDB Streams. Nadie la llama directamente. |
| Azul claro | Lambda **interna** | La llama otro servicio por HTTPS, o la usa la API Gateway (`authorizer`). No la usa el frontend. |

### Líneas

| Línea | Significado | ¿Se espera respuesta? |
|---|---|---|
| Negra continua | Petición HTTPS: usuario → Amplify → API Gateway | Sí |
| **Azul punteada** | Llamada **síncrona** de un servicio a la API de otro | **Sí**, el llamador espera |
| **Rosa continua** | **Evento** hacia/desde SNS y SQS | **No**, es asíncrono |
| Morada/azul oscura | Lectura/escritura a DynamoDB | Sí |
| Verde | S3 (URL prefirmada) | — |
| Gris punteada | Carga masiva de datos desde la MV | — |

**Diferencia clave:** una *solicitud* pide hacer algo y devuelve respuesta («reserva esta visita»). Un *evento* informa algo que ya ocurrió («esta visita fue programada») y el emisor no espera nada.

---

## 3. Recorrido de una petición normal

1. El usuario abre la web (React en **Amplify Hosting**).
2. El navegador llama a la API Gateway del MS que necesita, con un token (HTTPS).
3. La API Gateway ejecuta el **Lambda Authorizer** (del MS0). Si es válido, entrega `usuario_id`, `tenant_id` y `rol`.
4. La API Gateway invoca la Lambda de esa ruta.
5. La Lambda lee o escribe **solo en la tabla de su MS**, usando el `tenant_id` verificado (nunca uno enviado por el navegador).

Excepción: en MS0, `POST /auth/login` es público, y sus demás rutas validan el token dentro del propio servicio, porque MS0 no se llama a sí mismo para autorizarse.

---

## 4. Los siete microservicios

| MS | Responsabilidad | Tabla(s) | Streams | Consume cola | Publica eventos |
|---|---|---|:-:|---|:-:|
| **MS0** Usuarios | Login, usuarios, roles, sesiones, authorizer | `t_usuarios`, `t_sesiones` (TTL) | No | — | No |
| **MS1** Clientes | Clientes y ubicaciones | `t_clientes` | No | — | No |
| **MS2** Técnicos | Técnicos, jornadas, ausencias | `t_tecnicos` | No | — | No |
| **MS3** Órdenes | Órdenes de trabajo y su historial | `t_ordenes` | Sí | `q-ordenes` | Sí |
| **MS4** Agenda | Visitas, reservas de bloques, control de orden | `t_agenda` | Sí | `q-agenda` | Sí |
| **MS5** Partes | Parte de trabajo y evidencias | `t_partes` | Sí | — | Sí |
| **MS6** Analítica | Métricas por técnico y por tenant (solo lectura de eventos) | `t_analitica` | No | `q-analitica` | No |

Claves de DynamoDB: `PK = TENANT#<id>` y `SK = <TIPO>#<id>` (por ejemplo `ORDEN#OT-001`). El tenant va siempre en la clave.

---

## 5. Líneas azules punteadas: llamadas síncronas entre servicios

Cuando un servicio necesita un dato de otro, **llama a la API Gateway de ese servicio**. No lee su tabla.

| # | Lambda que origina | Servicio origen | Ruta llamada | Lambda destino | Servicio destino | Para qué | Qué la dispara |
|---|---|---|---|---|---|---|---|
| 1 | `crearOrden` | MS3 Órdenes | `GET /clientes/{id}/ubicaciones/{id}` | `getUbicacion` | MS1 Clientes | Validar que cliente y ubicación existen y son del tenant | El coordinador crea una orden |
| 2 | `cerrarOrden`, `cancelarOrden` | MS3 Órdenes | `POST /control-ordenes/{id}/bloqueo` | `bloquearOrden` | MS4 Agenda | Bloquear nuevas visitas antes de cerrar o cancelar (idempotente; solo acepta a Órdenes) | El coordinador cierra o cancela |
| 3 | `programarVisita` | MS4 Agenda | `GET /ordenes/{id}` | `getOrden` | MS3 Órdenes | Verificar la orden y su estado | El coordinador programa una visita |
| 4 | `getDisponibilidad`, `programarVisita` | MS4 Agenda | `GET /tecnicos/{id}` y `GET /tecnicos/{id}/jornadas` | `getTecnico`, `getJornadas` | MS2 Técnicos | Validar especialidad, jornada y ausencias | Consultar disponibilidad o programar |
| 5 | `getDisponibilidad` (con `sugerir=true`) | MS4 Agenda | `GET /analitica/tecnicos/{id}` | `getMetricasTecnico` | MS6 Analítica | Carga del día y tasa de resolución para ordenar técnicos | El coordinador pide una sugerencia |
| 6 | `crearBorrador`, `finalizarParte` | MS5 Partes | `GET /visitas/{id}` | `getVisita` | MS4 Agenda | Verificar visita, técnico asignado y estado | El técnico crea o finaliza el parte |

Detalles a recordar:

- Cada llamada autentica al emisor y conserva el contexto del tenant.
- **Analítica es opcional:** si MS6 no responde, Agenda ofrece los técnicos compatibles en un orden por defecto, sin justificación de métricas.
- En el diagrama estas líneas van de contenedor a contenedor, no de Lambda a Lambda; esta tabla es la precisión.

---

## 6. Líneas rosadas: eventos (SNS + SQS)

### Por qué existen
Guardar un cambio y avisar a otros servicios son dos acciones distintas; si la segunda falla, los datos quedan inconsistentes. Por eso se usa el patrón **Outbox/Inbox**.

### Recorrido completo de un evento

1. Una Lambda HTTP de negocio guarda el cambio **y** un registro `OUTBOX` en la misma transacción de su tabla.
2. **DynamoDB Streams** detecta el registro nuevo y activa la Lambda **publicadora** del MS.
3. La publicadora lo envía al tema **SNS `fsm-eventos`**, con `event_type` como atributo.
4. SNS entrega **una copia a cada cola cuyo filtro coincida**.
5. **SQS** conserva el mensaje. Una Lambda **consumidora** lo procesa (*event source mapping*).
6. La consumidora guarda en su tabla una marca `INBOX` con el `event_id` y el cambio, **en la misma transacción**. Si el mensaje llega repetido, lo detecta y no duplica el efecto.
7. Si un mensaje falla demasiadas veces, pasa a la **DLQ** (cola de errores) de esa cola, para inspeccionarlo.

### Quién publica y quién consume

| Publicador | Eventos |
|---|---|
| MS3 Órdenes | `OrdenCreada`, `OrdenCerrada`, `OrdenCancelada` |
| MS4 Agenda | `VisitaProgramada`, `VisitaReprogramada`, `VisitaIniciada`, `VisitaCancelada`, `VisitaCompletada` |
| MS5 Partes | `ParteFinalizado` |

| Cola | Eventos que recibe (filtro) | Lambda consumidora |
|---|---|---|
| `q-agenda` | `ParteFinalizado` | MS4 Agenda → finaliza la visita |
| `q-ordenes` | `VisitaProgramada`, `VisitaReprogramada`, `VisitaIniciada`, `VisitaCancelada`, `VisitaCompletada`, `ParteFinalizado` | MS3 Órdenes → actualiza historial y resumen |
| `q-analitica` | `VisitaProgramada`, `VisitaReprogramada`, `VisitaCancelada`, `VisitaCompletada`, `ParteFinalizado`, `OrdenCreada`, `OrdenCerrada`, `OrdenCancelada` | MS6 Analítica → actualiza contadores |

Cada consumidor tiene su propia cola porque dos Lambdas que comparten una cola no reciben una copia cada una.

### Ejemplo: finalizar un parte

1. El técnico llama `POST /partes/{id}/finalizar` → Lambda `finalizarParte` (MS5).
2. Guarda el parte `FINALIZADO` + `OUTBOX` en `t_partes`.
3. Streams activa la `publicadora` de MS5 → publica `ParteFinalizado` en SNS.
4. SNS lo copia a `q-agenda`, `q-ordenes` y `q-analitica`.
5. MS4 marca la visita `FINALIZADA` y su publicadora emite `VisitaCompletada`.
6. SNS reparte `VisitaCompletada` a `q-ordenes` y `q-analitica`.
7. MS3 actualiza la orden y MS6 actualiza las métricas.

---

## 7. S3 y evidencias

- El bucket es privado. El navegador **no** tiene credenciales de AWS.
- MS5 (`solicitarEvidencia`) genera una **URL prefirmada** temporal. El navegador sube o descarga el archivo directo a S3 con ella.
- `confirmarEvidencia` verifica que el objeto existe; solo entonces la evidencia figura como disponible.
- El bucket necesita CORS para `PUT` y `GET` desde el dominio de Amplify.
- Ruta del objeto: `tenants/<tenant>/ordenes/<orden>/visitas/<visita>/<evidencia>`. La ruta por sí sola no da acceso.

---

## 8. Carga masiva de datos

- Una **MV EC2** ejecuta un script Python + boto3 (`scripts/seed/cargar_datos.py`).
- Escribe **directo a DynamoDB** con credenciales temporales de AWS Academy, usando `batch_writer`.
- **No pasa por API Gateway ni Lambda.** Lo pidió el profesor.
- La MV no forma parte del sistema en ejecución.
- Meta: 30 000 registros por microservicio, repartidos entre ClimaLima, FríoSur y TecniNorte. Está pendiente confirmar si MS0 entra en esa cifra.

---

## 9. Despliegue y operación

| Pieza | Papel |
|---|---|
| **Repositorio Git** | Contiene un `serverless.yml` por servicio. |
| **Serverless Framework → CloudFormation** | `serverless deploy` crea APIs, Lambdas, tablas, SNS/SQS y roles. |
| **Amplify** | Compila y publica el React en cada push. |
| **CloudWatch** | Logs y métricas de las Lambdas; alarmas sobre las DLQ. |
| **IAM** | Un rol por Lambda con mínimo privilegio. En AWS Academy puede estar limitado a `LabRole`; hay que verificarlo. |

---

## 10. Preguntas para autoevaluarse

1. ¿Por qué Órdenes no lee la tabla de Clientes al crear una orden?
2. ¿Qué diferencia hay entre una línea azul punteada y una rosa? ¿Cuál espera respuesta?
3. ¿Qué Lambdas de MS4 son naranja, rosa y azul, y por qué?
4. ¿Por qué hay tres colas en vez de una?
5. ¿Para qué sirven `OUTBOX` e `INBOX`? ¿Qué problema evita cada uno?
6. ¿Qué pasa con la agenda si MS6 Analítica se cae?
7. ¿Qué ocurre con un mensaje que falla varias veces en `q-ordenes`?
8. ¿Por qué el `authorizer` de MS0 es una Lambda azul y no naranja?
9. ¿Cómo evita el sistema que un usuario de FríoSur lea una orden de ClimaLima, aunque conozca su ID?
10. ¿Por qué la carga de 30 000 registros no usa la API REST?

---

## 11. Decisiones aún abiertas en la propuesta

- **Token de MS0:** opaco con sesión en `t_sesiones`, o firmado y verificable. Si es firmado, `t_sesiones` puede omitirse.
- **Caché del authorizer:** conviene activarla con TTL corto. Retrasa unos segundos la revocación de una sesión.
- **Roles IAM:** depende de si AWS Academy permite crear uno por Lambda.
- **Volumen de MS0:** confirmar con el profesor si debe llegar a 30 000 registros.
- **Región:** por definir; todos los recursos deben estar en la misma.
