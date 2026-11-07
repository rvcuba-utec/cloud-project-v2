# Conteos de registros

Generado el 2026-11-07 02:16 UTC, stage `dev`, leyendo DynamoDB con paginación completa.
Se separan los registros de negocio de los ítems técnicos (marcadores, bloques, historial).

| Servicio | Tenant | Negocio | Técnicos | Detalle |
|---|---|---:|---:|---|
| usuarios | CLIMALIMA | 107 | 8 | EMAIL: 7, EMPRESA: 1, USUARIO: 107 |
| usuarios | FRIOSUR | 103 | 4 | EMAIL: 3, EMPRESA: 1, USUARIO: 103 |
| usuarios | TECNINORTE | 103 | 4 | EMAIL: 3, EMPRESA: 1, USUARIO: 103 |
| clientes | CLIMALIMA | 220 | 0 | CLIENTE: 110, UBICACION: 110 |
| clientes | FRIOSUR | 200 | 0 | CLIENTE: 100, UBICACION: 100 |
| clientes | TECNINORTE | 200 | 0 | CLIENTE: 100, UBICACION: 100 |
| tecnicos | CLIMALIMA | 237 | 0 | JORNADA: 231, TECNICO: 6 |
| tecnicos | FRIOSUR | 237 | 0 | JORNADA: 231, TECNICO: 6 |
| tecnicos | TECNINORTE | 237 | 0 | JORNADA: 231, TECNICO: 6 |
| ordenes | CLIMALIMA | 138 | 321 | HISTORIAL: 291, IDEMP: 4, INBOX: 26, ORDEN: 138 |
| ordenes | FRIOSUR | 105 | 210 | HISTORIAL: 210, ORDEN: 105 |
| ordenes | TECNINORTE | 105 | 210 | HISTORIAL: 210, ORDEN: 105 |
| agenda | CLIMALIMA | 128 | 65 | BLOQUE: 27, CONTROL_ORDEN: 34, INBOX: 4, VISITA: 128 |
| agenda | FRIOSUR | 108 | 15 | BLOQUE: 10, CONTROL_ORDEN: 5, VISITA: 108 |
| agenda | TECNINORTE | 109 | 15 | BLOQUE: 10, CONTROL_ORDEN: 5, VISITA: 109 |
| partes | CLIMALIMA | 113 | 111 | EVIDENCIA: 2, MARCA_VISITA: 111, PARTE: 111 |
| partes | FRIOSUR | 103 | 103 | MARCA_VISITA: 103, PARTE: 103 |
| partes | TECNINORTE | 104 | 104 | MARCA_VISITA: 104, PARTE: 104 |
| analitica | CLIMALIMA | 212 | 22 | INBOX: 22, METRICAS_TECNICO: 6, SNAPSHOT_TECNICO_DIA: 204, SNAPSHOT_TENANT: 2 |
| analitica | FRIOSUR | 207 | 0 | METRICAS_TECNICO: 5, SNAPSHOT_TECNICO_DIA: 200, SNAPSHOT_TENANT: 2 |
| analitica | TECNINORTE | 207 | 0 | METRICAS_TECNICO: 5, SNAPSHOT_TECNICO_DIA: 200, SNAPSHOT_TENANT: 2 |

| Servicio | Registros de negocio | Mínimo de 30 000 |
|---|---:|---|
| usuarios | 313 | No cumple |
| clientes | 620 | No cumple |
| tecnicos | 711 | No cumple |
| ordenes | 348 | No cumple |
| agenda | 345 | No cumple |
| partes | 320 | No cumple |
| analitica | 626 | No cumple |
