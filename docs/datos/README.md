# Diseño de datos por microservicio

Cada servicio tiene su propia tabla DynamoDB, bajo demanda: `PK = TENANT#<id>` y `SK = <TIPO>#<id>`. El tenant va siempre en la clave, por lo que una consulta no puede salir de su empresa. Los archivos `.json` de esta carpeta tienen un ejemplo real de cada tipo de registro, producido por el generador de datos.

| Servicio | Tabla | Ejemplos |
|---|---|---|
| MS0 Usuarios | `t_usuarios`, `t_sesiones` | [usuarios.json](usuarios.json) |
| MS1 Clientes | `t_clientes` | [clientes.json](clientes.json) |
| MS2 Técnicos | `t_tecnicos` | [tecnicos.json](tecnicos.json) |
| MS3 Órdenes | `t_ordenes` | [ordenes.json](ordenes.json) |
| MS4 Agenda | `t_agenda` | [agenda.json](agenda.json) |
| MS5 Partes | `t_partes` | [partes.json](partes.json) |
| MS6 Analítica | `t_analitica` | [analitica.json](analitica.json) |

## Claves

| Tabla | SK | GSI |
|---|---|---|
| `t_usuarios` | `USUARIO#<id>`, `EMAIL#<correo>`, `EMPRESA` | — |
| `t_clientes` | `CLIENTE#<id>`, `UBICACION#<cliente>#<id>` | GSI1: clientes por nombre normalizado |
| `t_tecnicos` | `TECNICO#<id>`, `JORNADA#<tec>#<fecha>`, `AUSENCIA#<tec>#<fecha>` | — |
| `t_ordenes` | `ORDEN#<id>`, `HIST#<orden>#<instante>#<sufijo>` | GSI1: por estado y fecha. GSI2: por cliente y fecha |
| `t_agenda` | `VISITA#<id>`, `BLOQUE#<fecha>#<tec>#<inicio>`, `CONTROL_ORDEN#<orden>` | GSI1: por técnico. GSI2: por orden. GSI3: por fecha |
| `t_partes` | `PARTE#<id>`, `EVIDENCIA#<id>`, `MARCA_VISITA#<visita>` | GSI1: partes de una orden y evidencias de un parte |
| `t_analitica` | `METRICAS#<tec>`, `DIA#<fecha>#<tec>`, `DASHBOARD#<AAAA-MM>` | — |

Ítems técnicos en las tablas que usan eventos o idempotencia: `OUTBOX#<event_id>`, `INBOX#<event_id>` e `IDEMP#<clave>`.

## Patrones de acceso

| Necesidad | Cómo se resuelve |
|---|---|
| Iniciar sesión | `get_item` de `EMAIL#<correo>` y luego del usuario |
| Validar un token | `get_item` en `t_sesiones` por el hash del token, y del usuario |
| Buscar clientes por inicio del nombre | GSI1 de `t_clientes` con `begins_with` |
| Órdenes por estado o por cliente | GSI1 o GSI2 de `t_ordenes`, descendente por fecha |
| Historial de una orden | `begins_with(SK, 'HIST#<orden>#')` |
| Jornada de un técnico un día | `get_item` de `JORNADA#<tec>#<fecha>` |
| Horarios ocupados de un día | `begins_with(SK, 'BLOQUE#<fecha>#')` |
| Mis visitas, visitas de una orden o de un día | GSI1, GSI2 o GSI3 de `t_agenda` |
| Evitar dobles reservas | Transacción con `Put` condicionado de cada `BLOQUE#` de 30 minutos |
| Un solo parte por visita | Transacción con `Put` condicionado de `MARCA_VISITA#<visita>` |
| Partes de una orden, evidencias de un parte | GSI1 de `t_partes` |
| Ranking de técnicos | `begins_with(SK, 'METRICAS#')` y `begins_with(SK, 'DIA#<fecha>#')` |
| Resumen del mes | `get_item` de `DASHBOARD#<AAAA-MM>` |

Las tasas y promedios no se guardan: `t_analitica` conserva numeradores y denominadores que admiten incrementos atómicos.
