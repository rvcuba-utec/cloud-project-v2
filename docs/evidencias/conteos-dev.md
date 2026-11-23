# Conteos de registros

Generado el 2026-11-23 03:18 UTC, stage `dev`, leyendo DynamoDB con paginación completa.
Se separan los registros de negocio de los ítems técnicos (marcadores, bloques, historial).

| Servicio | Tenant | Negocio | Técnicos | Detalle |
|---|---|---:|---:|---|
| usuarios | CLIMALIMA | 10003 | 4 | EMAIL: 3, EMPRESA: 1, USUARIO: 10003 |
| usuarios | FRIOSUR | 10003 | 4 | EMAIL: 3, EMPRESA: 1, USUARIO: 10003 |
| usuarios | TECNINORTE | 10003 | 4 | EMAIL: 3, EMPRESA: 1, USUARIO: 10003 |
| clientes | CLIMALIMA | 20007 | 7 | CLIENTE: 10004, IDEMP: 7, UBICACION: 10003 |
| clientes | FRIOSUR | 20000 | 0 | CLIENTE: 10000, UBICACION: 10000 |
| clientes | TECNINORTE | 20000 | 0 | CLIENTE: 10000, UBICACION: 10000 |
| tecnicos | CLIMALIMA | 10680 | 0 | AUSENCIA: 1, JORNADA: 10628, TECNICO: 51 |
| tecnicos | FRIOSUR | 10081 | 0 | JORNADA: 10030, TECNICO: 51 |
| tecnicos | TECNINORTE | 10081 | 0 | JORNADA: 10030, TECNICO: 51 |
| ordenes | CLIMALIMA | 10044 | 20112 | HISTORIAL: 20084, IDEMP: 9, INBOX: 19, ORDEN: 10044 |
| ordenes | FRIOSUR | 10035 | 20055 | HISTORIAL: 20055, ORDEN: 10035 |
| ordenes | TECNINORTE | 10035 | 20055 | HISTORIAL: 20055, ORDEN: 10035 |
| agenda | CLIMALIMA | 10651 | 88 | BLOQUE: 52, CONTROL_ORDEN: 26, IDEMP: 6, INBOX: 4, VISITA: 10651 |
| agenda | FRIOSUR | 10604 | 60 | BLOQUE: 40, CONTROL_ORDEN: 20, VISITA: 10604 |
| agenda | TECNINORTE | 10617 | 60 | BLOQUE: 40, CONTROL_ORDEN: 20, VISITA: 10617 |
| partes | CLIMALIMA | 10634 | 10630 | EVIDENCIA: 4, MARCA_VISITA: 10630, PARTE: 10630 |
| partes | FRIOSUR | 10584 | 10584 | MARCA_VISITA: 10584, PARTE: 10584 |
| partes | TECNINORTE | 10597 | 10597 | MARCA_VISITA: 10597, PARTE: 10597 |
| analitica | CLIMALIMA | 10061 | 21 | INBOX: 21, METRICAS_TECNICO: 51, SNAPSHOT_TECNICO_DIA: 10003, SNAPSHOT_TENANT: 7 |
| analitica | FRIOSUR | 10057 | 0 | METRICAS_TECNICO: 50, SNAPSHOT_TECNICO_DIA: 10000, SNAPSHOT_TENANT: 7 |
| analitica | TECNINORTE | 10057 | 0 | METRICAS_TECNICO: 50, SNAPSHOT_TECNICO_DIA: 10000, SNAPSHOT_TENANT: 7 |

| Servicio | Registros de negocio | Mínimo de 30 000 |
|---|---:|---|
| usuarios | 30009 | Cumple |
| clientes | 60007 | Cumple |
| tecnicos | 30842 | Cumple |
| ordenes | 30114 | Cumple |
| agenda | 31872 | Cumple |
| partes | 31815 | Cumple |
| analitica | 30175 | Cumple |
