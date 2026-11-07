# Resultados de las pruebas

Stage `dev`, cuenta de AWS Academy, región `us-east-1`.

## Sin AWS (`./test.sh`)

| Grupo | Pruebas |
|---|---:|
| Librería común y reglas de arquitectura | 90 |
| MS0 Usuarios | 30 |
| MS1 Clientes | 15 |
| MS2 Técnicos | 19 |
| MS3 Órdenes | 48 |
| MS4 Agenda | 53 |
| MS5 Partes | 53 |
| MS6 Analítica | 25 |
| Generador de datos | 12 |
| Frontend | 16 |
| **Total** | **361** |

## Contra AWS real (`scripts/pruebas_aws.sh`)

16 de solo lectura y 8 que crean datos. Todas pasan. Comprueban, entre otras cosas:

- **Reservas simultáneas**, con 5 hilos sobre el mismo horario: se confirma exactamente una.
- **Cierre y reserva a la vez:** no queda una orden cerrada con una visita activa.
- **Aislamiento:** con el token de otra empresa, las órdenes, partes y técnicos no aparecen.
- **Atención completa:** parte, foto en S3, notificación del bucket, lectura con URL temporal y lectura sin firma rechazada (403).
- **Más de 5 MB:** lo rechaza S3 (400).
- **Eventos:** `ParteFinalizado` termina la visita, la orden pasa a `PENDIENTE_DE_CIERRE`, Analítica suma la visita y la orden se puede cerrar.
- **Evento sin publicar:** un `OUTBOX` pendiente llega a su destino tras invocar `barrerOutbox`.
- **Evento repetido:** el mismo `event_id` no vuelve a restar del contador de visitas activas ni repite el historial.

## En un navegador real (`scripts/pruebas_web.sh`)

Chromium sin interfaz contra la URL de Amplify, sin errores de consola ni desborde horizontal a 390 px. Coordinador y técnico recorren: panel, crear orden, programar visita, iniciar desde el teléfono, rechazo de más de 5 MB, subida real a S3 con CORS, finalizar parte, ver el cambio por eventos y cerrar la orden. Las capturas están en `capturas/`. El teléfono se emuló con el navegador (390 × 844 y pantalla táctil); no se probó en un equipo físico.

## Fallos provocados a propósito

| Fallo | Resultado |
|---|---|
| Agenda apuntando a una URL inválida de Analítica | `GET /disponibilidad` responde 200, en orden alfabético y sin justificación. Se restauró y volvió la justificación |
| Mensaje inválido en `q-analitica` | Tras 5 intentos pasó a la DLQ, como se esperaba. Se borró después |
| Búsqueda de tokens y contraseñas en los 54 grupos de logs de las últimas 6 horas | Ningún resultado |

Tras las pruebas, las tres DLQ quedaron vacías.

## Carga de datos

Muestra del 1 %: 4 089 ítems en 28 s desde una laptop, directo a DynamoDB y sin invocar Lambda. Los datos se leyeron por las APIs y son coherentes entre servicios. **La carga completa aún no se ha ejecutado:** los conteos de `conteos.md` son de la muestra, junto con los datos de prueba.

## Pendiente de comprobar

- Carga completa y tiempos de las listas con 30 000 registros.
- Despliegue limpio en un stage nuevo.
- Ensayo de la demo partiendo de un laboratorio recién iniciado.
