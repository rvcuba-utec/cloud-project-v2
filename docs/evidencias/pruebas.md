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

## Stage `prod`: despliegue limpio y carga completa

- **Despliegue desde cero:** `./deploy.sh --stage prod` creó los 8 stacks, las cuentas de demo y la web de Amplify a la primera, en 666 s. Las 16 pruebas de solo lectura pasaron.
- **Carga completa:** 336 156 ítems en 1 622 s (27 min), desde la laptop, directo a DynamoDB con `batch_writer` en un solo proceso y sin invocar Lambda. Los 7 servicios superan los 30 000 registros de negocio: ver `conteos.md`.
- **Recorrido en navegador** sobre `prod`, con los datos cargados: correcto.

Tiempos con 30 000 registros por servicio, mejor de 3 intentos, desde la laptop (incluyen la red):

| Petición | Tiempo |
|---|---:|
| `GET /clientes?limit=25` | 251 ms |
| `GET /clientes?q=hotel` | 185 ms |
| `GET /ordenes?limit=25` | 387 ms |
| `GET /ordenes?estado=CERRADA` | 410 ms |
| `GET /visitas?fecha=…` | 614 ms |
| `GET /disponibilidad` con sugerencia | 1 536 ms |
| `GET /analitica/dashboard` | 307 ms |
| `GET /analitica/tecnicos` (50 técnicos) | 218 ms |

La paginación con `cursor` devuelve la página siguiente sin repetir registros.

**Corregido durante la carga:** un técnico generado se llamaba igual que el técnico de demo, y el recorrido le asignó la visita a él. Ahora los técnicos de demo usan apellidos que el generador no usa, ningún técnico se repite dentro de una empresa y hay pruebas que lo comprueban. También se corrigió que el panel mostraba "No hay registros" mientras cargaba.

## Muestra en `dev`

Muestra del 1 %: 4 089 ítems en 28 s. `dev` conserva esa muestra y los datos de las pruebas; los conteos válidos son los de `prod`.

## Automatizaciones (contra AWS real, `tests/integracion/test_automatizacion_aws.py`)

- **Reasignación por ausencia:** se registra la ausencia del técnico de demo y, por el evento `TecnicoAusente`, Agenda pasa su visita a otro técnico libre según Analítica (o deja una alerta si nadie puede); Órdenes anota en el historial que fue automática. Registrar la misma ausencia otra vez no vuelve a reasignar.
- **Cancelación en cascada:** cancelar una orden con 2 visitas programadas las cancela a las dos.
- **Mapa, alertas y filtros de usuarios** responden con permisos por rol.

Encontrado y corregido al probar en AWS: el cierre de una orden fallaba si los eventos de sus visitas llegaban a Órdenes durante el cierre; ahora relee la orden antes del paso final. También que AWS Academy deshabilita los disparadores SQS al apagar el laboratorio: `./warmup.sh` los reactiva y `./check.sh` avisa.

## Portada y revisor de la skill de diseño

`/presentacion/` sigue el recorrido completo de la skill `design-taste-frontend` (tipo software). Su revisor terminó en **GATE: OPEN 4** tras sus 3 rondas, con estos fallos abiertos: contraste del subtítulo del encabezado (5,6:1; el kit pide 7:1, AA exige 4,5:1), hueco entre las secciones de reasignación y preguntas, la sección de funciones mide 2,1 pantallas a 390 px, y el chequeo de títulos, que no reconoce sustantivos en español. Excepciones registradas con su motivo: largo del h1 medido con relleno, botones del tablero de muestra y la sección de preguntas sin imagen.

## Pendiente de comprobar

- Ensayo de la demo partiendo de un laboratorio recién iniciado.
- Navegación en un teléfono físico.
