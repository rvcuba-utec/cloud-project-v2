# Consultas de CloudWatch Logs Insights

Los logs son JSON con `tipo`, `operacion`, `tenant_id`, `correlation_id` y `log_datos`. Elegir los grupos `/aws/lambda/api-*`.

## Errores por servicio

```
fields @timestamp, @log, operacion, log_datos.codigo, log_datos.mensaje
| filter tipo = "ERROR"
| sort @timestamp desc
| limit 100
```

## Duración y memoria por Lambda

```
filter @type = "REPORT"
| stats count() as invocaciones, avg(@duration) as ms_promedio, max(@duration) as ms_maximo, max(@maxMemoryUsed / 1000000) as mb_maximos by @log
| sort ms_maximo desc
```

## Recorrido de una orden entre servicios

```
fields @timestamp, @log, operacion, tipo
| filter correlation_id = "OT-..."
| sort @timestamp asc
```

## Eventos que quedaron sin publicar

```
fields @timestamp, @log, log_datos.event_id, log_datos.event_type, log_datos.tipo_error
| filter operacion = "publicar_evento"
| sort @timestamp desc
```
