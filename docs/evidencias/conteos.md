# Conteos de registros

Generado el 2026-11-09 15:36 UTC, stage `dev`, leyendo DynamoDB con paginación completa.
Se separan los registros de negocio de los ítems técnicos (marcadores, bloques, historial).

| Servicio | Tenant | Negocio | Técnicos | Detalle |
|---|---|---:|---:|---|
| usuarios | CLIMALIMA | 10003 | 4 | EMAIL: 3, EMPRESA: 1, USUARIO: 10003 |
| usuarios | FRIOSUR | 10003 | 4 | EMAIL: 3, EMPRESA: 1, USUARIO: 10003 |
| usuarios | TECNINORTE | 10003 | 4 | EMAIL: 3, EMPRESA: 1, USUARIO: 10003 |
| clientes | CLIMALIMA | 20000 | 0 | CLIENTE: 10000, UBICACION: 10000 |
| clientes | FRIOSUR | 20000 | 0 | CLIENTE: 10000, UBICACION: 10000 |
| clientes | TECNINORTE | 20000 | 0 | CLIENTE: 10000, UBICACION: 10000 |
| tecnicos | CLIMALIMA | 10083 | 0 | AUSENCIA: 2, JORNADA: 10030, TECNICO: 51 |
| tecnicos | FRIOSUR | 10081 | 0 | JORNADA: 10030, TECNICO: 51 |
| tecnicos | TECNINORTE | 10081 | 0 | JORNADA: 10030, TECNICO: 51 |
| ordenes | CLIMALIMA | 10135 | 20280 | HISTORIAL: 20268, IDEMP: 1, INBOX: 11, ORDEN: 10135 |
| ordenes | FRIOSUR | 10133 | 20253 | HISTORIAL: 20253, ORDEN: 10133 |
| ordenes | TECNINORTE | 10133 | 20253 | HISTORIAL: 20253, ORDEN: 10133 |
| agenda | CLIMALIMA | 10661 | 92 | AVISO: 1, BLOQUE: 60, CONTROL_ORDEN: 24, IDEMP: 6, INBOX: 2, VISITA: 10660 |
| agenda | FRIOSUR | 10607 | 70 | BLOQUE: 50, CONTROL_ORDEN: 20, VISITA: 10607 |
| agenda | TECNINORTE | 10621 | 70 | BLOQUE: 50, CONTROL_ORDEN: 20, VISITA: 10621 |
| partes | CLIMALIMA | 10636 | 10635 | EVIDENCIA: 1, MARCA_VISITA: 10635, PARTE: 10635 |
| partes | FRIOSUR | 10587 | 10587 | MARCA_VISITA: 10587, PARTE: 10587 |
| partes | TECNINORTE | 10601 | 10601 | MARCA_VISITA: 10601, PARTE: 10601 |
| analitica | CLIMALIMA | 10058 | 11 | INBOX: 11, METRICAS_TECNICO: 51, SNAPSHOT_TECNICO_DIA: 10001, SNAPSHOT_TENANT: 6 |
| analitica | FRIOSUR | 10056 | 0 | METRICAS_TECNICO: 50, SNAPSHOT_TECNICO_DIA: 10000, SNAPSHOT_TENANT: 6 |
| analitica | TECNINORTE | 10056 | 0 | METRICAS_TECNICO: 50, SNAPSHOT_TECNICO_DIA: 10000, SNAPSHOT_TENANT: 6 |

| Servicio | Registros de negocio | Mínimo de 30 000 |
|---|---:|---|
| usuarios | 30009 | Cumple |
| clientes | 60000 | Cumple |
| tecnicos | 30245 | Cumple |
| ordenes | 30401 | Cumple |
| agenda | 31889 | Cumple |
| partes | 31824 | Cumple |
| analitica | 30170 | Cumple |
