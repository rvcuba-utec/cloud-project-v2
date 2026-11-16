# Pruebas de fallos controlados

Ejecución local del 16 de noviembre de 2026, Python 3.12, pytest y Moto. Los fallos inducidos se activan exclusivamente desde los tests. Los clientes y las colas simuladas usan credenciales ficticias. La rama no incorpora ninguna ruta HTTP ni interruptor de producción para provocar fallos.

## Reproducción

Desde la raíz, instalar las dependencias de `requirements-dev.txt` y las de `frontend/package-lock.json`. `./test.sh` ejecuta pytest en un proceso por servicio, además de las pruebas de seed y Vitest. En Windows con Git Bash funcionan tanto `.venv/Scripts` como `.venv/bin`.

```bash
./test.sh
python -m pytest backend/analitica/tests/test_analitica.py -k 'dashboard_denegado or lote_mixto or llega_a_dlq'
python -m pytest backend/common/tests/test_secretos.py
python -m pytest backend/common/tests/test_comun.py -k 'barrido or fallo_al_publicar'
python -m pytest backend/agenda/tests/test_agenda.py -k 'parte_repetido or visita_cancelada_registra or parte_incompatible'
python -m pytest backend/partes/tests/test_partes.py -k 'si_publicar_falla'
```

| Fallo o reintento | Qué verifica la prueba |
|---|---|
| DynamoDB rechaza GetItem en Analítica | El dashboard devuelve 503, el cliente recibe el request_id y el log privado incluye AccessDeniedException y la pila saneada. |
| Fecha inválida o rol con tipo incorrecto | HTTP 400. El contrato de error incluye el campo cuando corresponde. Los IDs de otros tenants conservan el 404. |
| El segundo mensaje SQS de un lote es ilegible | El primero se procesa. Solo el segundo aparece en batchItemFailures. Al reenviar el lote, INBOX impide duplicar el contador de Analítica. |
| El mismo mensaje inválido se recibe cinco veces | El test reproduce localmente la entrega del consumidor y el redrive con una cola y una DLQ de Moto. La sexta lectura de la cola principal está vacía y el mensaje está en la DLQ. |
| SNS no está disponible al finalizar un parte | La operación de negocio ya está confirmada en DynamoDB. El OUTBOX sigue pendiente con el mismo event_id. El barrido falla mientras continúe el problema y lo recupera después. |
| Agenda recibe dos veces ParteFinalizado | La transacción con INBOX evita un segundo decremento de visitas activas. Una orden, técnico o estado incompatibles dejan un fallo visible. |
| Secrets Manager devuelve AccessDenied, ResourceNotFound, InvalidRequest, throttling o JSON inválido | MS0 responde 503, no guarda una lectura fallida en caché y no expone el valor. Las pruebas cubren expiración de caché, rotación y hashes previos. |
| Aislamiento de empresas | Las pruebas usan CLIMALIMA y FRIOSUR para verificar usuarios, resultados y métricas. La identidad HTTP procede del autorizador. |

## Resultados observados

La base `7817304` pasó 443 pruebas Python antes de la corrección. Estos son los resultados de `./test.sh` antes de incorporar el ingreso privado, en orden de suite.

```text
backend/common      132 passed in 7.64s
backend/usuarios     52 passed in 23.69s
backend/clientes     20 passed in 10.39s
backend/tecnicos     23 passed in 11.65s
backend/analitica    38 passed in 13.39s
backend/ordenes      57 passed in 13.69s
backend/agenda       72 passed in 18.53s
backend/partes       53 passed in 16.54s
scripts/seed         14 passed in 14.46s
Test Files  4 passed (4)
Tests  20 passed (20)
Todas las pruebas pasaron.
```

`python -m compileall -q backend scripts` terminó con éxito. El comando de unittest indicado por el paquete, `python -m unittest discover -s tests -p 'test_*.py' -v`, devolvió `Ran 0 tests` y código 5. La suite ejecutable de este repositorio usa pytest y Vitest.

Serverless Framework v4.46 pidió autenticación para ejecutar `print`. Para la verificación local se usó una instalación separada del compilador abierto v3.40.0. Se pasaron identificadores de cuenta, API, autorizador, origen de frontend y tema sintéticos. El esquema de v3 emite una advertencia sobre Python 3.12, pero conserva el runtime solicitado en las plantillas. La compilación con v4, el despliegue del nuevo diseño y la telemetría en CloudWatch de esta rama quedan pendientes.

```bash
npm install --prefix .local-env/sls3 --no-save serverless@3.40.0
python scripts/validar_ambientes.py --cli .local-env/sls3/node_modules/serverless/scripts/serverless.js
```

```text
dev: 1 API, 47 rutas, 60 Lambda, 8 tablas, 3 colas + 3 DLQ, 4 barridos
test: 1 API, 47 rutas, 60 Lambda, 8 tablas, 3 colas + 3 DLQ, 4 barridos
prod: 1 API, 47 rutas, 60 Lambda, 8 tablas, 3 colas + 3 DLQ, 4 barridos
```

Además se ejecutó `serverless package --stage test` en copias locales del stack compartido y los siete servicios, con los mismos parámetros ficticios. Se inspeccionaron los ZIP, las integraciones y mappings del CloudFormation compilado. Solo shared crea el gateway. Cada método de negocio usa el gateway de test y cada mapping SQS declara `ReportBatchItemFailures`.

## Verificación del VPC Link V2 y del ALB

`scripts/validar_ingreso.py` empaqueta ocho stacks por ambiente en un directorio temporal. Compara las rutas con los siete documentos OpenAPI y evalúa las reglas por prioridad para cada verbo y ruta, con y sin el prefijo del stage. Comprueba el listener, las subredes, los permisos Lambda, el mapeo de la identidad y el adaptador presente en cada ZIP. La validación de CloudFormation usa los esquemas locales de us-east-1.

```bash
python scripts/validar_ingreso.py --cli .local-env/sls3/node_modules/serverless/scripts/serverless.js --salida .local-env/ingreso-verificado
cfn-lint -r us-east-1 -t .local-env/ingreso-verificado/*.json
```

Después del cambio pasaron 477 pruebas Python y 20 de frontend. Los tres ambientes produjeron 47 reglas y 47 grupos de destino por ALB. Cada uno protege 46 rutas y permite el login público. cfn-lint 1.60.1 validó las 24 plantillas. Las pruebas con Moto ejecutan login, el autorizador, el perfil y las consultas de Analítica usando eventos ALB. Cubren el aislamiento de dos empresas, el rechazo de cabeceras reservadas, los permisos por rol, CORS y los parámetros de ruta y consulta. Una comprobación HTTP en loopback usó las reglas empaquetadas de dev y los handlers reales. Tras el login, el panel devolvió 3 visitas para CLIMALIMA y 7 para FRIOSUR. Una cabecera de identidad enviada por el cliente devolvió 401. Los recursos administrados de AWS, la negociación TLS y los permisos efectivos de Academy quedan por validar en una cuenta.

## Respuesta y log simulados de Analítica

Los siguientes valores proceden de invocar el handler real con un cliente DynamoDB simulado. `req-analitica-01` es el ID de esta prueba local.

```json
{
  "statusCode": 503,
  "body": {
    "error": {
      "codigo": "DEPENDENCIA_NO_DISPONIBLE",
      "mensaje": "Servicio temporalmente no disponible",
      "detalle": {},
      "request_id": "req-analitica-01"
    }
  },
  "log_simulado": {
    "service": "analitica",
    "stage": "test",
    "function": "api-analitica-test-dashboard",
    "request_id": "req-analitica-01",
    "correlation_id": "req-analitica-01",
    "tenant_id": "CLIMALIMA",
    "severity": "ERROR",
    "tipo": "ERROR",
    "event_type": "handlers.consultas.dashboard",
    "operation": "handlers.consultas.dashboard",
    "operacion": "handlers.consultas.dashboard",
    "log_datos": {
      "aws_code": "AccessDeniedException",
      "aws_operation": "GetItem"
    },
    "error_code": "DEPENDENCIA_NO_DISPONIBLE",
    "exception_type": "ClientError",
    "stacktrace": [
      "http.py:147:envoltura",
      "consultas.py:41:dashboard",
      "mock.py:1139:__call__",
      "mock.py:1143:_mock_call",
      "mock.py:1198:_execute_mock_call"
    ]
  }
}
```

## Consultas para CloudWatch Logs Insights

Seleccionar los grupos del mismo ambiente, por ejemplo `/aws/lambda/api-analitica-dev-dashboard`. Estas consultas sirven cuando se publique una versión con los nuevos campos. El resultado anterior es local y nunca se envió a CloudWatch.

```sql
fields @timestamp, service, function, stage, operation, request_id, correlation_id, tenant_id, error_code, exception_type, log_datos.aws_code, log_datos.aws_operation, stacktrace
| filter severity = "ERROR"
| sort @timestamp desc
| limit 100
```

Para seguir una petición, reemplazar el identificador por el obtenido de la respuesta.

```sql
fields @timestamp, service, operation, request_id, correlation_id, error_code, log_datos.message_id
| filter request_id = "REEMPLAZAR" or correlation_id = "REEMPLAZAR"
| sort @timestamp asc
```

Los fallos parciales de SQS se ven en los logs por registro. Para observarlos también en métricas, usar un filtro sobre `error_code` de consumir_sqs y vigilar mensajes visibles en la DLQ y edad de la cola. La métrica Lambda Errors por sí sola no cuenta una invocación que devolvió correctamente la lista de mensajes fallidos. La creación de alarmas y la comprobación del redrive real requieren un ensayo posterior en un ambiente autorizado.
