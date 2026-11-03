# Trazora FSM — Arquitectura técnica en AWS

Vista técnica de **todos los recursos AWS** que se desplegarán, derivada de la [propuesta final](proposal.md). Los diagramas están en Mermaid.

- Flechas continuas: invocación o flujo de datos.
- Flechas punteadas: llamadas internas entre servicios, streams, redrive o permisos.
- Los nombres de tablas, colas y funciones son orientativos; el sufijo `-{stage}` se define al desplegar.

## 1. Diagrama general

```mermaid
flowchart LR
    USR["Usuarios<br/>PC y celular"]
    DEV["Repositorio Git<br/>serverless.yml por servicio"]
    VM["MV de desarrollo EC2<br/>scripts/seed/cargar_datos.py<br/>Python + boto3"]

    subgraph AWS["Cuenta AWS Academy"]

        CF["CloudFormation<br/>1 stack por microservicio<br/>+ stack de infraestructura compartida"]

        subgraph FRONT["Frontend"]
            AMP["Amplify Hosting<br/>React<br/>build + deploy desde Git"]
        end

        subgraph MS0["MS0 Usuarios y acceso"]
            API0["API Gateway<br/>POST /auth/login<br/>/usuarios, /usuarios/me"]
            L0["Lambdas<br/>login, crear usuario,<br/>listar, perfil, patch"]
            AUTH["Lambda Authorizer<br/>valida token y devuelve<br/>usuario_id, tenant_id, rol"]
        end

        subgraph MS1["MS1 Clientes"]
            API1["API Gateway<br/>/clientes<br/>/clientes/id/ubicaciones"]
            L1["Lambdas<br/>CRUD clientes, ubicaciones<br/>y consulta de ubicación"]
        end

        subgraph MS2["MS2 Técnicos"]
            API2["API Gateway<br/>/tecnicos<br/>/tecnicos/id/jornadas"]
            L2["Lambdas<br/>CRUD técnicos, jornadas<br/>y ausencias"]
        end

        subgraph MS3["MS3 Órdenes"]
            API3["API Gateway<br/>/ordenes<br/>cerrar, cancelar"]
            L3["Lambdas API<br/>crear, listar, detalle, prioridad,<br/>cerrar, cancelar"]
            C3["Lambda consumidor<br/>eventos de Agenda y Partes"]
            P3["Lambda publicadora<br/>OrdenCreada, OrdenCerrada,<br/>OrdenCancelada"]
        end

        subgraph MS4["MS4 Agenda"]
            API4["API Gateway<br/>/disponibilidad, /visitas<br/>reprogramar, iniciar, cancelar"]
            L4["Lambdas API<br/>disponibilidad y sugerencia,<br/>programar, reprogramar, cancelar,<br/>iniciar, bloqueo de orden"]
            C4["Lambda consumidor<br/>ParteFinalizado"]
            P4["Lambda publicadora<br/>VisitaProgramada, Reprogramada,<br/>Cancelada, Iniciada, Completada"]
        end

        subgraph MS5["MS5 Partes"]
            API5["API Gateway<br/>/visitas/id/partes<br/>/partes, /evidencias"]
            L5["Lambdas API<br/>borrador y edición, URL prefirmada,<br/>confirmar evidencia, finalizar"]
            P5["Lambda publicadora<br/>ParteFinalizado"]
        end

        subgraph MS6["MS6 Analítica"]
            API6["API Gateway<br/>/analitica/tecnicos<br/>/analitica/dashboard"]
            L6["Lambdas API<br/>métricas de técnico,<br/>ranking, dashboard"]
            C6["Lambda consumidor<br/>agrega métricas"]
        end

        subgraph DATA["DynamoDB: una persistencia exclusiva por servicio"]
            T0[("t_usuarios")]
            T0S[("t_sesiones<br/>TTL de expiración")]
            T1[("t_clientes")]
            T2[("t_tecnicos")]
            T3[("t_ordenes<br/>Streams")]
            T4[("t_agenda<br/>Streams")]
            T5[("t_partes<br/>Streams")]
            T6[("t_analitica")]
        end

        subgraph MSG["Mensajería de eventos"]
            SNS{{"SNS<br/>tema fsm-eventos"}}
            QAG["SQS q-agenda"]
            QOR["SQS q-ordenes"]
            QAN["SQS q-analitica"]
            DAG["SQS DLQ agenda"]
            DOR["SQS DLQ ordenes"]
            DAN["SQS DLQ analitica"]
        end

        subgraph STO["Archivos"]
            S3[("S3 bucket privado<br/>tenants/tenant/ordenes/orden/<br/>visitas/visita/evidencia")]
        end

        subgraph OPS["Observabilidad y permisos"]
            CW["CloudWatch<br/>Logs y métricas<br/>de todas las Lambdas"]
            IAM["IAM<br/>rol de ejecución por Lambda<br/>mínimo privilegio"]
        end
    end

    %% Despliegue
    DEV -->|"serverless deploy"| CF
    DEV -->|"build en cada push"| AMP

    %% Acceso
    USR --> AMP
    AMP -->|"HTTPS + token"| API0
    AMP -->|"HTTPS + token"| API1
    AMP -->|"HTTPS + token"| API2
    AMP -->|"HTTPS + token"| API3
    AMP -->|"HTTPS + token"| API4
    AMP -->|"HTTPS + token"| API5
    AMP -->|"HTTPS + token"| API6
    AMP -->|"PUT y GET con URL prefirmada"| S3

    %% Autorizador
    API1 -.->|"authorizer"| AUTH
    API2 -.->|"authorizer"| AUTH
    API3 -.->|"authorizer"| AUTH
    API4 -.->|"authorizer"| AUTH
    API5 -.->|"authorizer"| AUTH
    API6 -.->|"authorizer"| AUTH
    AUTH -->|"verifica sesión"| T0S
    AUTH -->|"verifica usuario activo y rol"| T0

    %% API a Lambda a datos
    API0 --> L0
    L0 --> T0
    L0 --> T0S
    API1 --> L1 --> T1
    API2 --> L2 --> T2
    API3 --> L3 --> T3
    API4 --> L4 --> T4
    API5 --> L5 --> T5
    API6 --> L6 --> T6

    %% Llamadas internas síncronas
    L3 -.->|"valida cliente y ubicación"| API1
    L3 -.->|"bloquea programaciones al cerrar"| API4
    L4 -.->|"valida jornada y especialidad"| API2
    L4 -.->|"valida orden"| API3
    L4 -.->|"métricas para sugerir técnico"| API6
    L5 -.->|"valida visita y asignación"| API4
    L5 -->|"genera URL prefirmada y verifica objeto"| S3

    %% Outbox, streams y publicación
    T3 -.->|"Stream OUTBOX"| P3
    T4 -.->|"Stream OUTBOX"| P4
    T5 -.->|"Stream OUTBOX"| P5
    P3 -->|"publica"| SNS
    P4 -->|"publica"| SNS
    P5 -->|"publica"| SNS

    %% Fan-out
    SNS -->|"filtro por tipo de evento"| QAG
    SNS -->|"filtro por tipo de evento"| QOR
    SNS -->|"filtro por tipo de evento"| QAN

    %% Consumidores con INBOX
    QAG --> C4 --> T4
    QOR --> C3 --> T3
    QAN --> C6 --> T6

    %% Colas de errores
    QAG -.->|"redrive"| DAG
    QOR -.->|"redrive"| DOR
    QAN -.->|"redrive"| DAN

    %% Observabilidad y permisos
    L0 -.-> CW
    L3 -.-> CW
    L4 -.-> CW
    L5 -.-> CW
    L6 -.-> CW
    IAM -.->|"roles"| MS0
    IAM -.->|"roles"| MS3
    IAM -.->|"roles"| MS4
    IAM -.->|"roles"| MS5
    IAM -.->|"roles"| MS6

    %% Carga masiva
    VM ==>|"batch_writer directo,<br/>sin API Gateway ni Lambda"| DATA
```

## 2. Filtros de suscripción SNS → SQS

Cada cola recibe solo los eventos que consume. El filtro se declara en la suscripción (atributo `event_type` del mensaje).

```mermaid
flowchart LR
    SNS{{"SNS fsm-eventos"}}

    SNS -->|"ParteFinalizado"| QAG["q-agenda"]

    SNS -->|"VisitaProgramada<br/>VisitaReprogramada<br/>VisitaIniciada<br/>VisitaCancelada<br/>VisitaCompletada<br/>ParteFinalizado"| QOR["q-ordenes"]

    SNS -->|"VisitaProgramada<br/>VisitaReprogramada<br/>VisitaCancelada<br/>VisitaCompletada<br/>ParteFinalizado<br/>OrdenCreada<br/>OrdenCerrada<br/>OrdenCancelada"| QAN["q-analitica"]
```

## 3. Inventario de recursos

| Recurso AWS | Cantidad | Detalle |
|---|---:|---|
| Amplify Hosting | 1 app | React, rama `main`, variables con las URLs de las 7 APIs. |
| API Gateway | 7 | Una por microservicio. MS1–MS6 usan el Lambda Authorizer de MS0. En MS0, `login` es público y sus demás rutas validan el token dentro del propio servicio. |
| Lambda Authorizer | 1 | Pertenece al stack de MS0 y las APIs de MS1–MS6 lo referencian. |
| Lambdas de API | por servicio | Una función por operación o grupo de operaciones. |
| Lambdas publicadoras | 3 | MS3, MS4 y MS5, disparadas por DynamoDB Streams. |
| Lambdas consumidoras | 3 | MS3, MS4 y MS6, disparadas por SQS. |
| DynamoDB | 8 tablas | `t_usuarios`, `t_sesiones`, `t_clientes`, `t_tecnicos`, `t_ordenes`, `t_agenda`, `t_partes`, `t_analitica`. Streams en órdenes, agenda y partes. |
| SNS | 1 tema | `fsm-eventos`, con 3 suscripciones filtradas. |
| SQS | 3 colas + 3 DLQ | `q-agenda`, `q-ordenes`, `q-analitica` y su cola de errores cada una. |
| S3 | 1 bucket | Privado. Acceso solo mediante URLs prefirmadas emitidas por MS5. |
| CloudWatch | — | Grupos de logs por Lambda y alarmas sobre las DLQ. |
| CloudFormation | 1 por servicio + compartido | Generado por Serverless Framework. |
| EC2 | 1 MV | Solo para la carga inicial con boto3; no forma parte del runtime. |

## 4. Notas técnicas

- **Propiedad de datos:** cada Lambda accede únicamente a la tabla de su servicio. Las consultas entre servicios pasan por la API del otro servicio, nunca por su tabla.
- **Outbox e inbox:** los registros `OUTBOX` viven en la tabla del productor y los `INBOX` en la del consumidor. Se escriben en la misma transacción que el cambio de negocio.
- **Analítica es opcional en runtime:** si `API6` no responde, MS4 sigue programando visitas con el orden por defecto.
- **Carga masiva:** la MV escribe directo a DynamoDB con credenciales temporales de AWS Academy, como pidió el docente. No pasa por API Gateway ni Lambda.
- **IAM en AWS Academy:** en el laboratorio suele estar disponible solo el rol preexistente `LabRole`. Hay que verificar si el despliegue puede crear un rol por Lambda; si no, todas usarán `LabRole` y la separación de permisos quedaría documentada pero no aplicada por IAM.
- **Mecanismo de token pendiente:** el diagrama asume tokens opacos con sesión en `t_sesiones`. Si se elige un token firmado y verificable (decisión abierta en la sección 9.1 de la propuesta), `t_sesiones` puede omitirse y quedaría 1 tabla menos en MS0.
- **Caché del autorizador:** conviene activar la caché de resultados del Lambda Authorizer en API Gateway (TTL corto). Sin ella, cada petición consulta DynamoDB dos veces. La caché retrasa unos segundos la revocación de una sesión o usuario inactivo.
- **Filtro SNS:** las publicadoras envían `event_type` como atributo del mensaje; la política de filtrado de cada suscripción se basa en ese atributo.
- **CORS en S3:** el bucket necesita una regla CORS que permita `PUT` y `GET` desde el dominio de Amplify, porque el navegador sube y descarga con URLs prefirmadas.
- **Recuperación de eventos:** el comando de `scripts/recovery/` vuelve a publicar en SNS los registros `OUTBOX` pendientes. Se ejecuta a demanda y no es un recurso permanente.
- **Región:** por definir al fijar el entorno. Todos los recursos deben desplegarse en la misma región.
