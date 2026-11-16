# Auditoría del backend de Trazora FSM

La referencia de partida es `rvcuba-utec/cloud-project-v2@7817304`. El paquete académico describe otro repositorio de seis servicios. Aquí hay siete, incluidos Analítica y el evento de ausencia de Técnicos. La API pública, las claves de DynamoDB, el modelo de sesiones y las rutas que usa el frontend se conservan.

## Estado y evidencia

| Aspecto | Evidencia |
|---|---|
| Base del cambio | Se revisaron README, la API, documentación de datos, evidencias y arquitectura, configuraciones de los siete servicios, scripts de despliegue/carga y pruebas. El árbol usa `infra/shared` y barridos programados, no el layout histórico `infra/eventos` y `scripts/recovery` del paquete. |
| Cuenta Academy consultada, us-east-1, 16 de noviembre de 2026 | STS válido. En dev hay 8 stacks, 60 funciones, 8 tablas, 1 tema y 6 colas del proyecto. CloudFormation registra 7 API REST, 1 tema y 6 colas en los stacks de dev. Los mappings de Agenda, Órdenes y Analítica figuran como **Disabled**. |
| Test y prod en esa cuenta y región | Cero stacks activos, Lambda, tablas, temas o colas con los nombres esperados. El README base enlaza también una demo de prod. Estos resultados solo describen la cuenta y región consultadas. |
| Ingreso privado, consulta de solo lectura en Academy | En us-east-1, el simulador IAM permitió a `LabRole` y `voclabs` crear el VPC Link V2, el ALB interno, el listener HTTPS y sus reglas y destinos. El stack compartido de dev usa la identidad de despliegue. ACM devolvió cero certificados. [Detalle de la consulta](AMBIENTES_DEV_TEST_PROD.md#consulta-de-aws-academy) |
| Secrets Manager | Los tres nombres previstos devolvieron `ResourceNotFoundException`. No se verificaron KMS, creación del secreto ni lectura real del pepper. |
| Solución de la rama | Se resolvieron los 24 archivos de configuración (ocho stacks por tres ambientes) y se compilaron las 24 plantillas localmente con parámetros ficticios. Las reglas del ALB se cotejaron con OpenAPI y se verificaron con cfn-lint. Los ZIP de servicio contienen sus handlers y la librería común. Detalles y versión de las herramientas en la [guía de fallos](PRUEBAS_FALLOS_CONTROLADOS.md). |
| Alcance de la validación | Pruebas de Lambda, dominio, persistencia y fallos con Moto/mocks. La lectura de AWS inventarió el despliegue anterior. El tráfico real a través del gateway compartido, del VPC Link V2 y del ALB, las Lambdas modificadas y el nuevo secreto requieren una futura validación integrada en un ambiente autorizado. |

## Hallazgos corregidos

- La barrera HTTP registraba `str(exception)` y devolvía un 500 indistinto. Ahora un error incluye un identificador de solicitud y la causa técnica se registra mediante tipo, código del SDK, operación y marcos de pila. El log emplea una lista de campos operativos permitidos.
- Los tres consumidores solo procesaban el primer registro. Ahora devuelven los identificadores SQS fallidos mediante `ReportBatchItemFailures`. Un mensaje incompatible sigue el redrive de la cola. Un mensaje ya aplicado se reconoce por su INBOX transaccional. En Agenda se valida también que orden y técnico correspondan a la visita y que el contador no se vuelva negativo.
- Al caer SNS, un cambio ya confirmado queda en la tabla con su OUTBOX. Si el barrido tampoco puede publicarlo, la invocación programada falla y EventBridge puede reintentar. Si SNS recibió el evento y falla el borrado del OUTBOX, el reenvío conserva el event_id.
- Usuarios usa un pepper versionado en Secrets Manager para nuevas contraseñas cuando corresponde. Las cuentas PBKDF2 existentes y los tokens opacos siguen funcionando. El SDK tiene límites de espera y de intentos, incluidas las invocaciones con efectos entre servicios.
- Los stacks independientes pasan a compartir el gateway y el autorizador de su ambiente. Las 47 rutas usan el VPC Link V2 y el ALB HTTPS interno del stack compartido. Se verificó que cada ambiente resuelve nombres distintos de tablas, colas, DLQ, tema, bucket, funciones y secreto.

## Inventario de funciones

Todas las filas se declaran en dev, test y prod. Las API HTTP usan el mismo contrato de error y el aislamiento por identidad validada por MS0. Los códigos 400/401/403/404/409 distinguen validación, sesión, permiso, ausencia y conflicto. Los fallos internos o de dependencias se traducen en 500/502/503. El gateway puede emitir 429 al limitar peticiones. Las invocaciones directas y S3 propagan una excepción saneada. El autorizador conserva el contrato `Unauthorized`. Los barridos propagan los fallos pendientes y los consumidores SQS devuelven fallos parciales. Cada bloque enlaza la suite de ese servicio y cada archivo indica el punto de entrada.

### Usuarios

[Configuración](../backend/usuarios/serverless.yml) · [Pruebas](../backend/usuarios/tests/test_usuarios.py)

| Lambda | Archivo y función | Entrada | Acceso al ejecutar | Secreto |
|---|---|---|---|---|
| validarToken | [handlers/validar_token.lambda_handler](../backend/usuarios/handlers/validar_token.py) | Autorizador TOKEN | DynamoDB propia, tabla de sesiones | — |
| login | [handlers/login.lambda_handler](../backend/usuarios/handlers/login.py) | POST /auth/login | DynamoDB propia, tabla de sesiones | GetSecretValue, caché |
| crear | [handlers/crear.lambda_handler](../backend/usuarios/handlers/crear.py) | POST /usuarios | DynamoDB propia, Lambda Técnicos si hay vínculo | GetSecretValue, caché |
| listar | [handlers/listar.lambda_handler](../backend/usuarios/handlers/listar.py) | GET /usuarios | DynamoDB propia | — |
| yo | [handlers/yo.lambda_handler](../backend/usuarios/handlers/yo.py) | GET /usuarios/me | DynamoDB propia | — |
| actualizar | [handlers/actualizar.lambda_handler](../backend/usuarios/handlers/actualizar.py) | PATCH /usuarios/{usuario_id} | DynamoDB propia, Lambda Técnicos si hay vínculo | — |

### Clientes

[Configuración](../backend/clientes/serverless.yml) · [Pruebas](../backend/clientes/tests/test_clientes.py)

| Lambda | Archivo y función | Entrada | Acceso al ejecutar | Secreto |
|---|---|---|---|---|
| crear | [handlers/clientes.crear](../backend/clientes/handlers/clientes.py) | POST /clientes | DynamoDB propia | — |
| listar | [handlers/clientes.listar](../backend/clientes/handlers/clientes.py) | GET /clientes | DynamoDB propia | — |
| detalle | [handlers/clientes.detalle](../backend/clientes/handlers/clientes.py) | GET /clientes/{cliente_id} | DynamoDB propia | — |
| actualizar | [handlers/clientes.actualizar](../backend/clientes/handlers/clientes.py) | PATCH /clientes/{cliente_id} | DynamoDB propia | — |
| crearUbicacion | [handlers/ubicaciones.crear](../backend/clientes/handlers/ubicaciones.py) | POST /clientes/{cliente_id}/ubicaciones | DynamoDB propia | — |
| listarUbicaciones | [handlers/ubicaciones.listar](../backend/clientes/handlers/ubicaciones.py) | GET /clientes/{cliente_id}/ubicaciones | DynamoDB propia | — |
| detalleUbicacion | [handlers/ubicaciones.detalle](../backend/clientes/handlers/ubicaciones.py) | GET /clientes/{cliente_id}/ubicaciones/{ubicacion_id} | DynamoDB propia | — |

### Tecnicos

[Configuración](../backend/tecnicos/serverless.yml) · [Pruebas](../backend/tecnicos/tests/test_tecnicos.py)

| Lambda | Archivo y función | Entrada | Acceso al ejecutar | Secreto |
|---|---|---|---|---|
| crear | [handlers/tecnicos.crear](../backend/tecnicos/handlers/tecnicos.py) | POST /tecnicos | DynamoDB propia | — |
| listar | [handlers/tecnicos.listar](../backend/tecnicos/handlers/tecnicos.py) | GET /tecnicos | DynamoDB propia | — |
| disponibles | [handlers/jornadas.disponibles](../backend/tecnicos/handlers/jornadas.py) | GET /tecnicos/disponibles | DynamoDB propia | — |
| detalle | [handlers/tecnicos.detalle](../backend/tecnicos/handlers/tecnicos.py) | GET /tecnicos/{tecnico_id} | DynamoDB propia | — |
| actualizar | [handlers/tecnicos.actualizar](../backend/tecnicos/handlers/tecnicos.py) | PATCH /tecnicos/{tecnico_id} | DynamoDB propia | — |
| definirJornada | [handlers/jornadas.definir_jornada](../backend/tecnicos/handlers/jornadas.py) | PUT /tecnicos/{tecnico_id}/jornadas/{fecha} | DynamoDB propia | — |
| registrarAusencia | [handlers/jornadas.registrar_ausencia](../backend/tecnicos/handlers/jornadas.py) | PUT /tecnicos/{tecnico_id}/ausencias/{fecha} | DynamoDB propia, SNS | — |
| consultarJornadas | [handlers/jornadas.consultar](../backend/tecnicos/handlers/jornadas.py) | GET /tecnicos/{tecnico_id}/jornadas | DynamoDB propia | — |
| disponiblesInterno | [handlers/jornadas.disponibles_interno](../backend/tecnicos/handlers/jornadas.py) | Invocación Lambda directa | DynamoDB propia | — |
| existeInterno | [handlers/tecnicos.existe_interno](../backend/tecnicos/handlers/tecnicos.py) | Invocación Lambda directa | DynamoDB propia | — |
| barrerOutbox | [trazora_common.eventos.manejador_barrido](../backend/common/trazora_common/eventos.py) | EventBridge, cada 5 min | DynamoDB propia, SNS | — |

### Ordenes

[Configuración](../backend/ordenes/serverless.yml) · [Pruebas](../backend/ordenes/tests/test_ordenes.py)

| Lambda | Archivo y función | Entrada | Acceso al ejecutar | Secreto |
|---|---|---|---|---|
| crear | [handlers/ordenes.crear](../backend/ordenes/handlers/ordenes.py) | POST /ordenes | DynamoDB propia, HTTP Clientes, SNS | — |
| listar | [handlers/ordenes.listar](../backend/ordenes/handlers/ordenes.py) | GET /ordenes | DynamoDB propia | — |
| detalle | [handlers/ordenes.detalle](../backend/ordenes/handlers/ordenes.py) | GET /ordenes/{orden_id} | DynamoDB propia | — |
| actualizar | [handlers/ordenes.actualizar](../backend/ordenes/handlers/ordenes.py) | PATCH /ordenes/{orden_id} | DynamoDB propia | — |
| mapa | [handlers/ordenes.mapa](../backend/ordenes/handlers/ordenes.py) | GET /ordenes/mapa | DynamoDB propia | — |
| historial | [handlers/ordenes.historial](../backend/ordenes/handlers/ordenes.py) | GET /ordenes/{orden_id}/historial | DynamoDB propia | — |
| cerrar | [handlers/ordenes.cerrar](../backend/ordenes/handlers/ordenes.py) | POST /ordenes/{orden_id}/cerrar | DynamoDB propia, Lambda Agenda, SNS | — |
| cancelar | [handlers/ordenes.cancelar](../backend/ordenes/handlers/ordenes.py) | POST /ordenes/{orden_id}/cancelar | DynamoDB propia, Lambda Agenda, SNS | — |
| barrerOutbox | [trazora_common.eventos.manejador_barrido](../backend/common/trazora_common/eventos.py) | EventBridge, cada 5 min | DynamoDB propia, SNS | — |
| consumidor | [handlers/consumidor.lambda_handler](../backend/ordenes/handlers/consumidor.py) | SQS, fallo parcial | DynamoDB propia | — |

### Agenda

[Configuración](../backend/agenda/serverless.yml) · [Pruebas](../backend/agenda/tests/test_agenda.py)

| Lambda | Archivo y función | Entrada | Acceso al ejecutar | Secreto |
|---|---|---|---|---|
| crear | [handlers/visitas.crear](../backend/agenda/handlers/visitas.py) | POST /visitas | DynamoDB propia, HTTP Órdenes y Técnicos, SNS | — |
| listar | [handlers/visitas.listar](../backend/agenda/handlers/visitas.py) | GET /visitas | DynamoDB propia | — |
| detalle | [handlers/visitas.detalle](../backend/agenda/handlers/visitas.py) | GET /visitas/{visita_id} | DynamoDB propia | — |
| reprogramar | [handlers/visitas.reprogramar](../backend/agenda/handlers/visitas.py) | POST /visitas/{visita_id}/reprogramar | DynamoDB propia, HTTP Técnicos, SNS | — |
| cancelar | [handlers/visitas.cancelar](../backend/agenda/handlers/visitas.py) | POST /visitas/{visita_id}/cancelar | DynamoDB propia, SNS | — |
| iniciar | [handlers/visitas.iniciar](../backend/agenda/handlers/visitas.py) | POST /visitas/{visita_id}/iniciar | DynamoDB propia, SNS | — |
| disponibilidad | [handlers/disponibilidad.consultar](../backend/agenda/handlers/disponibilidad.py) | GET /disponibilidad | DynamoDB propia, HTTP Técnicos y Analítica | — |
| alertas | [handlers/alertas.listar](../backend/agenda/handlers/alertas.py) | GET /alertas | DynamoDB propia | — |
| bloquearOrden | [handlers/control.bloquear](../backend/agenda/handlers/control.py) | Invocación Lambda directa | DynamoDB propia, SNS si cancela visitas | — |
| barrerOutbox | [trazora_common.eventos.manejador_barrido](../backend/common/trazora_common/eventos.py) | EventBridge, cada 5 min | DynamoDB propia, SNS | — |
| consumidor | [handlers/consumidor.lambda_handler](../backend/agenda/handlers/consumidor.py) | SQS, fallo parcial | DynamoDB propia, SNS, Lambda Técnicos y Analítica según evento | — |

### Partes

[Configuración](../backend/partes/serverless.yml) · [Pruebas](../backend/partes/tests/test_partes.py)

| Lambda | Archivo y función | Entrada | Acceso al ejecutar | Secreto |
|---|---|---|---|---|
| crear | [handlers/partes.crear](../backend/partes/handlers/partes.py) | POST /visitas/{visita_id}/partes | DynamoDB propia, HTTP Agenda, firma S3 si hay evidencias | — |
| deVisita | [handlers/partes.de_visita](../backend/partes/handlers/partes.py) | GET /visitas/{visita_id}/parte | DynamoDB propia, firma S3 | — |
| listar | [handlers/partes.listar](../backend/partes/handlers/partes.py) | GET /partes | DynamoDB propia | — |
| detalle | [handlers/partes.detalle](../backend/partes/handlers/partes.py) | GET /partes/{parte_id} | DynamoDB propia, firma S3 | — |
| editar | [handlers/partes.editar](../backend/partes/handlers/partes.py) | PUT /partes/{parte_id} | DynamoDB propia, firma S3 | — |
| finalizar | [handlers/partes.finalizar](../backend/partes/handlers/partes.py) | POST /partes/{parte_id}/finalizar | DynamoDB propia, SNS, firma S3 | — |
| solicitarEvidencia | [handlers/evidencias.solicitar](../backend/partes/handlers/evidencias.py) | POST /partes/{parte_id}/evidencias | DynamoDB propia, firma S3 | — |
| confirmarEvidencia | [handlers/evidencias.confirmar](../backend/partes/handlers/evidencias.py) | POST /evidencias/{evidencia_id}/confirmar | DynamoDB propia, S3 HeadObject | — |
| onEvidenciaSubida | [handlers/on_evidencia.lambda_handler](../backend/partes/handlers/on_evidencia.py) | S3 ObjectCreated | DynamoDB propia, S3 HeadObject | — |
| barrerOutbox | [trazora_common.eventos.manejador_barrido](../backend/common/trazora_common/eventos.py) | EventBridge, cada 5 min | DynamoDB propia, SNS | — |

### Analitica

[Configuración](../backend/analitica/serverless.yml) · [Pruebas](../backend/analitica/tests/test_analitica.py)

| Lambda | Archivo y función | Entrada | Acceso al ejecutar | Secreto |
|---|---|---|---|---|
| dashboard | [handlers/consultas.dashboard](../backend/analitica/handlers/consultas.py) | GET /analitica/dashboard | DynamoDB propia | — |
| tecnicos | [handlers/consultas.tecnicos](../backend/analitica/handlers/consultas.py) | GET /analitica/tecnicos | DynamoDB propia | — |
| tecnico | [handlers/consultas.tecnico](../backend/analitica/handlers/consultas.py) | GET /analitica/tecnicos/{tecnico_id} | DynamoDB propia | — |
| tecnicosInterno | [handlers/consultas.tecnicos_interno](../backend/analitica/handlers/consultas.py) | Invocación Lambda directa | DynamoDB propia | — |
| consumidor | [handlers/consumidor.lambda_handler](../backend/analitica/handlers/consumidor.py) | SQS, fallo parcial | DynamoDB propia | — |

[Ambientes y migración](AMBIENTES_DEV_TEST_PROD.md) · [Secrets Manager y MCP](SECRETS_MANAGER_ACADEMY.md) · [Pruebas y CloudWatch](PRUEBAS_FALLOS_CONTROLADOS.md)
