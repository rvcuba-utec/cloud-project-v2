# Trazora FSM — Arquitectura técnica en AWS

Vista técnica de **todos los recursos AWS** desplegados, derivada de la [propuesta final](proposal.md) y comprobada contra el código de `backend/`. Los diagramas están en Mermaid.

- Flechas continuas: invocación o flujo de datos.
- Flechas punteadas: llamadas internas entre servicios, redrive o barrido.
- Las tablas y colas llevan el stage como prefijo, por ejemplo `dev-t_ordenes` y `dev-q-agenda`.

## 1. Diagrama general

```mermaid
flowchart LR
    USR["Usuarios<br/>PC y celular"]
    DEV["Repositorio Git<br/>serverless.yml por servicio"]
    VM["MV de desarrollo EC2<br/>scripts/seed/cargar_datos.py<br/>Python + boto3"]

    subgraph AWS["Cuenta AWS Academy"]

        CF["CloudFormation<br/>1 stack por microservicio<br/>+ stack de infraestructura compartida"]

        subgraph FRONT["Frontend"]
            AMP["Amplify Hosting<br/>React<br/>.zip publicado por CLI"]
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
            P3["Lambda barrerOutbox<br/>OrdenCreada, OrdenCerrada,<br/>OrdenCancelada"]
        end

        subgraph MS4["MS4 Agenda"]
            API4["API Gateway<br/>/disponibilidad, /visitas<br/>reprogramar, iniciar, cancelar"]
            L4["Lambdas API<br/>disponibilidad y sugerencia,<br/>programar, reprogramar, cancelar,<br/>iniciar, bloqueo de orden"]
            C4["Lambda consumidor<br/>ParteFinalizado"]
            P4["Lambda barrerOutbox<br/>VisitaProgramada, Reprogramada,<br/>Cancelada, Iniciada, Completada"]
        end

        subgraph MS5["MS5 Partes"]
            API5["API Gateway<br/>/visitas/id/partes<br/>/partes, /evidencias"]
            L5["Lambdas API<br/>borrador y edición, POST firmado,<br/>confirmar evidencia, finalizar"]
            P5["Lambda barrerOutbox<br/>ParteFinalizado"]
            N5["Lambda onEvidenciaSubida<br/>notificación de S3"]
        end

        subgraph MS6["MS6 Analítica"]
            API6["API Gateway<br/>/analitica/tecnicos<br/>/analitica/dashboard"]
            L6["Lambdas API<br/>métricas de técnico,<br/>ranking, dashboard"]
            C6["Lambda consumidor<br/>agrega métricas"]
        end

        subgraph DATA["DynamoDB: una persistencia exclusiva por servicio"]
            T0[("t_usuarios")]
            T0S[("t_sesiones<br/>expiración revisada al validar")]
            T1[("t_clientes")]
            T2[("t_tecnicos")]
            T3[("t_ordenes")]
            T4[("t_agenda")]
            T5[("t_partes")]
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
            IAM["IAM<br/>LabRole en todas las Lambdas"]
            EB["EventBridge<br/>rate 5 minutes"]
        end
    end

    %% Despliegue
    DEV -->|"serverless deploy"| CF
    DEV -->|"deploy.sh frontend: .zip por CLI"| AMP

    %% Acceso
    USR --> AMP
    AMP -->|"HTTPS + token"| API0
    AMP -->|"HTTPS + token"| API1
    AMP -->|"HTTPS + token"| API2
    AMP -->|"HTTPS + token"| API3
    AMP -->|"HTTPS + token"| API4
    AMP -->|"HTTPS + token"| API5
    AMP -->|"HTTPS + token"| API6
    AMP -->|"POST firmado y GET prefirmado"| S3

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
    L3 -.->|"lambda.invoke: bloquea programaciones al cerrar"| L4
    L4 -.->|"valida jornada y especialidad"| API2
    L4 -.->|"valida orden"| API3
    L4 -.->|"métricas para sugerir técnico"| API6
    L5 -.->|"valida visita y asignación"| API4
    L5 -->|"firma subida y lectura"| S3
    S3 -->|"notificación ObjectCreated"| N5
    N5 --> T5

    %% Outbox: publica la Lambda que hizo el cambio; el barrido recupera lo pendiente
    L3 -->|"publica y borra OUTBOX"| SNS
    L4 -->|"publica y borra OUTBOX"| SNS
    L5 -->|"publica y borra OUTBOX"| SNS
    C4 -->|"VisitaCompletada"| SNS
    EB -.-> P3
    EB -.-> P4
    EB -.-> P5
    T3 -.->|"OUTBOX pendiente"| P3
    T4 -.->|"OUTBOX pendiente"| P4
    T5 -.->|"OUTBOX pendiente"| P5
    P3 -->|"reenvía"| SNS
    P4 -->|"reenvía"| SNS
    P5 -->|"reenvía"| SNS

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
    IAM -.->|"rol de ejecución"| DATA

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

    SNS -->|"VisitaProgramada<br/>VisitaReprogramada<br/>VisitaCancelada<br/>VisitaCompletada<br/>OrdenCreada<br/>OrdenCerrada<br/>OrdenCancelada"| QAN["q-analitica"]
```

## 3. Inventario de recursos

| Recurso AWS | Cantidad | Detalle |
|---|---:|---|
| Amplify Hosting | 1 app | React, rama `main`, publicada con un `.zip` por CLI. Las URLs de las 7 APIs se fijan al compilar. |
| API Gateway | 7 REST | Una por microservicio, con integración proxy. Todas usan el Lambda Authorizer de MS0, salvo `POST /auth/login`. |
| Lambda Authorizer | 1 | `validarToken`, del stack de MS0. Tipo TOKEN con 60 s de caché. |
| Lambdas de API | Una por operación | Definidas en cada `backend/<servicio>/serverless.yml`. |
| Lambda interna | 1 | `bloquearOrden`, sin ruta: la invoca MS3 con `lambda.invoke`. |
| Lambdas programadas | 3 | `barrerOutbox` en MS3, MS4 y MS5, con EventBridge cada 5 minutos. |
| Lambdas consumidoras | 3 | MS3, MS4 y MS6, disparadas por SQS con `batchSize: 1` y `maximumConcurrency: 2`. |
| Lambda de notificación | 1 | `onEvidenciaSubida`, disparada por el bucket de S3. |
| DynamoDB | 8 tablas | `t_usuarios`, `t_sesiones`, `t_clientes`, `t_tecnicos`, `t_ordenes`, `t_agenda`, `t_partes`, `t_analitica`. Bajo demanda y sin Streams. |
| SNS | 1 tema | `fsm-eventos`, con 3 suscripciones filtradas. |
| SQS | 3 colas + 3 DLQ | `q-agenda`, `q-ordenes`, `q-analitica` y su cola de errores cada una. Visibilidad de 120 s y 5 intentos. |
| S3 | 1 bucket | Privado. Acceso solo con formularios y URLs firmados por MS5. |
| EventBridge | 3 reglas | Las de los barridos. |
| CloudWatch | — | Grupos de logs por Lambda. |
| CloudFormation | 7 + 1 | Un stack por microservicio y uno compartido, generados por Serverless Framework. |
| IAM | `LabRole` | Único rol disponible en el laboratorio. |
| EC2 | 1 MV | Solo para la carga inicial con boto3; no forma parte de la ejecución. |

## 4. Notas técnicas

- **Propiedad de datos:** cada Lambda accede únicamente a la tabla de su servicio. Las consultas entre servicios pasan por la API del otro servicio, nunca por su tabla. Con `LabRole`, IAM no lo impone: lo comprueba `backend/common/tests/test_arquitectura.py`.
- **Outbox e inbox:** los registros `OUTBOX` viven en la tabla del productor y los `INBOX` en la del consumidor. Se escriben en la misma transacción que el cambio de negocio.
- **Por qué sin Streams:** publicar desde la misma Lambda y barrer lo pendiente da la misma garantía con menos Lambdas activas, lo que ayuda a respetar el límite de concurrencia de Academy.
- **Analítica es opcional en ejecución:** si `API6` no responde, MS4 sigue programando visitas en orden alfabético y sin justificación. Se comprobó en AWS apuntando Agenda a una URL inválida.
- **Carga masiva:** escribe directo a DynamoDB con boto3, en un solo proceso. No pasa por API Gateway ni Lambda ni publica eventos: no consume concurrencia.
- **Token:** opaco (UUID4), con su hash SHA-256 en `t_sesiones`. La caché del autorizador puede retrasar hasta 60 s la revocación de una sesión o de un usuario inactivo.
- **Filtro SNS:** los productores envían `event_type` como atributo del mensaje; la política de filtrado de cada suscripción se basa en ese atributo.
- **Evidencias:** el bucket permite `POST` y `GET` desde el dominio de Amplify. `content-length-range` hace que S3 rechace archivos de más de 5 MB.
- **Región:** `us-east-1`.
