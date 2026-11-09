# Verificación de la cuenta de AWS Academy

Región: `us-east-1`. Ejecutada: 2026-11-06 00:24 UTC.

| # | Prueba | Resultado | Detalle |
|---|---|---|---|
| 0 | Amplify sin Git, por CLI | CORRECTO | publica por CLI y la web responde |
| 1 | Autorizador en otro stack | CORRECTO | 401 con CORS, contexto y caché entre rutas |
| 2 | CORS previo con Idempotency-Key | CORRECTO | permite Idempotency-Key |
| 3 | Transacciones y lambda.invoke | CORRECTO | TransactWriteItems y lambda.invoke con LabRole |
| 4 | SNS a SQS con filtro | CORRECTO | fan-out con filtro por event_type, declarado en YML |
| 5 | SQS a Lambda con DLQ | CORRECTO | mensaje fallido en la DLQ tras los reintentos |
| 6 | S3: POST prefirmado y CORS | CORRECTO | POST prefirmado, CORS y límite de tamaño |
| 7 | S3: notificación a Lambda | CORRECTO | notificación S3 con bucket en provider.s3 |
| 8 | EventBridge programado | CORRECTO | evento schedule declarado en YML |
| 9 | Límite de concurrencia | CORRECTO | límite de concurrencia: 400 |

**Manual:** comprobar si la API y la web responden con el laboratorio detenido.
