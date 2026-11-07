# API de Trazora FSM

Generado por `scripts/documentar_api.py` desde los `serverless.yml`. La URL de cada API la imprime `./check.sh`.

- **Autenticación:** `Authorization: Bearer <token>`, salvo `POST /auth/login`. El tenant y el rol salen del autorizador, nunca del cuerpo ni de la URL.
- **Errores:** `{"error": {"codigo", "mensaje", "detalle"}}`. 400 entrada inválida, 401 sin sesión, 403 sin permiso, 404 inexistente o de otra empresa, 409 conflicto de estado, versión u horario.
- **Listas:** `limit` (de 1 a 100) y `cursor`; la respuesta trae `items` y `next_cursor`.
- **Creaciones repetibles:** clientes, técnicos, órdenes y visitas aceptan la cabecera `Idempotency-Key`.
- **Funciones internas sin ruta** (`lambda.invoke`): `bloquearOrden` (Agenda), `disponiblesInterno` (Técnicos) y `tecnicosInterno` (Analítica).
- **Colección de Postman:** `docs/postman/trazora.postman_collection.json`.

## MS0 Usuarios

| Método | Ruta | Función |
|---|---|---|
| POST | `/auth/login` | `login` |
| POST | `/usuarios` | `crear` |
| GET | `/usuarios` | `listar` |
| GET | `/usuarios/me` | `yo` |
| PATCH | `/usuarios/{usuario_id}` | `actualizar` |

## MS1 Clientes

| Método | Ruta | Función |
|---|---|---|
| POST | `/clientes` | `crear` |
| GET | `/clientes` | `listar` |
| GET | `/clientes/{cliente_id}` | `detalle` |
| PATCH | `/clientes/{cliente_id}` | `actualizar` |
| POST | `/clientes/{cliente_id}/ubicaciones` | `crearUbicacion` |
| GET | `/clientes/{cliente_id}/ubicaciones` | `listarUbicaciones` |
| GET | `/clientes/{cliente_id}/ubicaciones/{ubicacion_id}` | `detalleUbicacion` |

## MS2 Técnicos

| Método | Ruta | Función |
|---|---|---|
| POST | `/tecnicos` | `crear` |
| GET | `/tecnicos` | `listar` |
| GET | `/tecnicos/disponibles` | `disponibles` |
| GET | `/tecnicos/{tecnico_id}` | `detalle` |
| PATCH | `/tecnicos/{tecnico_id}` | `actualizar` |
| PUT | `/tecnicos/{tecnico_id}/jornadas/{fecha}` | `definirJornada` |
| PUT | `/tecnicos/{tecnico_id}/ausencias/{fecha}` | `registrarAusencia` |
| GET | `/tecnicos/{tecnico_id}/jornadas` | `consultarJornadas` |

## MS3 Órdenes

| Método | Ruta | Función |
|---|---|---|
| POST | `/ordenes` | `crear` |
| GET | `/ordenes` | `listar` |
| GET | `/ordenes/{orden_id}` | `detalle` |
| PATCH | `/ordenes/{orden_id}` | `actualizar` |
| GET | `/ordenes/mapa` | `mapa` |
| GET | `/ordenes/{orden_id}/historial` | `historial` |
| POST | `/ordenes/{orden_id}/cerrar` | `cerrar` |
| POST | `/ordenes/{orden_id}/cancelar` | `cancelar` |

## MS4 Agenda

| Método | Ruta | Función |
|---|---|---|
| POST | `/visitas` | `crear` |
| GET | `/visitas` | `listar` |
| GET | `/visitas/{visita_id}` | `detalle` |
| POST | `/visitas/{visita_id}/reprogramar` | `reprogramar` |
| POST | `/visitas/{visita_id}/cancelar` | `cancelar` |
| POST | `/visitas/{visita_id}/iniciar` | `iniciar` |
| GET | `/disponibilidad` | `disponibilidad` |
| GET | `/alertas` | `alertas` |

## MS5 Partes

| Método | Ruta | Función |
|---|---|---|
| POST | `/visitas/{visita_id}/partes` | `crear` |
| GET | `/visitas/{visita_id}/parte` | `deVisita` |
| GET | `/partes` | `listar` |
| GET | `/partes/{parte_id}` | `detalle` |
| PUT | `/partes/{parte_id}` | `editar` |
| POST | `/partes/{parte_id}/finalizar` | `finalizar` |
| POST | `/partes/{parte_id}/evidencias` | `solicitarEvidencia` |
| POST | `/evidencias/{evidencia_id}/confirmar` | `confirmarEvidencia` |

## MS6 Analítica

| Método | Ruta | Función |
|---|---|---|
| GET | `/analitica/dashboard` | `dashboard` |
| GET | `/analitica/tecnicos` | `tecnicos` |
| GET | `/analitica/tecnicos/{tecnico_id}` | `tecnico` |
