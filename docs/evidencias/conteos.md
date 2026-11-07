# Conteos de registros

Generado el 2026-11-07 14:33 UTC, stage `prod`, leyendo DynamoDB con paginación completa.
Se separan los registros de negocio de los ítems técnicos (marcadores, bloques, historial).

| Servicio | Tenant | Negocio | Técnicos | Detalle |
|---|---|---:|---:|---|
| usuarios | CLIMALIMA | 10003 | 4 | EMAIL: 3, EMPRESA: 1, USUARIO: 10003 |
| usuarios | FRIOSUR | 10003 | 4 | EMAIL: 3, EMPRESA: 1, USUARIO: 10003 |
| usuarios | TECNINORTE | 10003 | 4 | EMAIL: 3, EMPRESA: 1, USUARIO: 10003 |
| clientes | CLIMALIMA | 20000 | 0 | CLIENTE: 10000, UBICACION: 10000 |
| clientes | FRIOSUR | 20000 | 0 | CLIENTE: 10000, UBICACION: 10000 |
| clientes | TECNINORTE | 20000 | 0 | CLIENTE: 10000, UBICACION: 10000 |
| tecnicos | CLIMALIMA | 10081 | 0 | JORNADA: 10030, TECNICO: 51 |
| tecnicos | FRIOSUR | 10081 | 0 | JORNADA: 10030, TECNICO: 51 |
| tecnicos | TECNINORTE | 10081 | 0 | JORNADA: 10030, TECNICO: 51 |
| ordenes | CLIMALIMA | 10023 | 20068 | HISTORIAL: 20056, IDEMP: 3, INBOX: 9, ORDEN: 10023 |
| ordenes | FRIOSUR | 10020 | 20040 | HISTORIAL: 20040, ORDEN: 10020 |
| ordenes | TECNINORTE | 10020 | 20040 | HISTORIAL: 20040, ORDEN: 10020 |
| agenda | CLIMALIMA | 10648 | 74 | BLOQUE: 46, CONTROL_ORDEN: 23, IDEMP: 3, INBOX: 2, VISITA: 10648 |
| agenda | FRIOSUR | 10604 | 60 | BLOQUE: 40, CONTROL_ORDEN: 20, VISITA: 10604 |
| agenda | TECNINORTE | 10617 | 60 | BLOQUE: 40, CONTROL_ORDEN: 20, VISITA: 10617 |
| partes | CLIMALIMA | 10629 | 10627 | EVIDENCIA: 2, MARCA_VISITA: 10627, PARTE: 10627 |
| partes | FRIOSUR | 10584 | 10584 | MARCA_VISITA: 10584, PARTE: 10584 |
| partes | TECNINORTE | 10597 | 10597 | MARCA_VISITA: 10597, PARTE: 10597 |
| analitica | CLIMALIMA | 10059 | 10 | INBOX: 10, METRICAS_TECNICO: 51, SNAPSHOT_TECNICO_DIA: 10001, SNAPSHOT_TENANT: 7 |
| analitica | FRIOSUR | 10056 | 0 | METRICAS_TECNICO: 50, SNAPSHOT_TECNICO_DIA: 10000, SNAPSHOT_TENANT: 6 |
| analitica | TECNINORTE | 10056 | 0 | METRICAS_TECNICO: 50, SNAPSHOT_TECNICO_DIA: 10000, SNAPSHOT_TENANT: 6 |

| Servicio | Registros de negocio | Mínimo de 30 000 |
|---|---:|---|
| usuarios | 30009 | Cumple |
| clientes | 60000 | Cumple |
| tecnicos | 30243 | Cumple |
| ordenes | 30063 | Cumple |
| agenda | 31869 | Cumple |
| partes | 31810 | Cumple |
| analitica | 30171 | Cumple |
