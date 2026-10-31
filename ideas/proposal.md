# DispatchIQ — FSM SaaS Proposal

> **Grupo 5 | CS2032 Cloud Computing**  
> **Tipo:** Field Service Management (FSM)  
> **Arquitectura:** Multi-tenancy · Serverless · EDA  
> **Stack:** AWS (API Gateway · Lambda · RDS · DynamoDB · S3 · SNS · SQS · Amplify)

---

## Concepto

Plataforma SaaS para empresas de servicios técnicos domiciliarios con asignación inteligente de técnicos, seguimiento en tiempo real y alertas automáticas basadas en condiciones climáticas externas.

El diferenciador principal: el sistema no solo reacciona a acciones del usuario — también reacciona a eventos del mundo real (clima) para reasignar o suspender trabajos automáticamente.

---

## Tenants

| Tenant ID | Empresa | Rubro |
|---|---|---|
| `aquafix` | AquaFix | Plomería |
| `electroserv` | ElectroServ | Electricidad |
| `climatech` | ClimaTech | HVAC / Climatización |

---

## Microservicios

### MS1 — Customers & Requests `(RDS)`
Gestión de clientes y solicitudes de servicio.

**Entidades:** Customer, ServiceRequest, ServiceType, Address

**Operaciones clave:**
- Crear/listar solicitudes por tenant
- Consultar historial de servicios por cliente
- Filtrar por estado (pending, assigned, in_progress, completed, cancelled)

---

### MS2 — Technician Management `(RDS)`
Perfiles, habilidades y disponibilidad de técnicos.

**Entidades:** Technician, Skill, Availability, Zone

**Operaciones clave:**
- Registrar técnicos y sus habilidades por tenant
- Consultar disponibilidad en tiempo real
- Actualizar zonas de cobertura

---

### MS3 — Job Dispatch & Tracking `(DynamoDB)`
Asignación y seguimiento de trabajos en tiempo real.

**Estructura JSON:**
```json
{
  "tenantId": "aquafix",
  "jobId": "job_001",
  "requestId": "req_123",
  "technicianId": "tech_07",
  "status": "in_progress",
  "assignedAt": "2026-11-01T10:00:00Z",
  "estimatedArrival": "2026-11-01T11:30:00Z",
  "statusHistory": [
    { "status": "assigned", "timestamp": "2026-11-01T10:00:00Z" },
    { "status": "in_progress", "timestamp": "2026-11-01T11:35:00Z" }
  ],
  "photosBefore": ["s3://dispatchiq/aquafix/job_001/before_1.jpg"],
  "photosAfter": []
}
```

---

### MS4 — Notifications & Event Log `(DynamoDB)`
Registro de todos los eventos SNS/SQS y notificaciones enviadas.

**Estructura JSON:**
```json
{
  "tenantId": "electroserv",
  "eventId": "evt_789",
  "eventType": "job_assigned",
  "source": "dispatch-lambda",
  "targetType": "customer",
  "targetId": "cust_42",
  "channel": "email",
  "status": "delivered",
  "timestamp": "2026-11-01T10:01:00Z",
  "payload": { "jobId": "job_001", "techName": "Carlos R.", "eta": "11:30" }
}
```

---

### MS5 — Billing & Analytics `(RDS)`
Facturas, pagos y métricas por tenant.

**Entidades:** Invoice, Payment, ServiceRate, TenantMetrics

**Operaciones clave:**
- Generar factura automática al cerrar un trabajo
- Consultar ingresos por período y por tenant
- Dashboard de métricas: trabajos completados, tiempo promedio, satisfacción

---

### MS6 — Weather & External Alerts `(DynamoDB)` — Web Scraping
Monitorea condiciones climáticas externas y genera alertas que afectan el dispatch.

**Fuentes:**
- **Senamhi** (Peru) — scraping HTML con BeautifulSoup + requests en Lambda
- **OpenWeatherMap API** (fallback gratuito)

**Estructura JSON:**
```json
{
  "tenantId": "climatech",
  "alertId": "weather_001",
  "city": "Lima",
  "condition": "heavy_rain",
  "severity": "high",
  "affectedJobTypes": ["outdoor_installation", "rooftop_ac"],
  "scrapedAt": "2026-11-01T09:00:00Z",
  "source": "senamhi",
  "actionTaken": "jobs_rescheduled",
  "jobsAffected": ["job_045", "job_046"]
}
```

**Lambda scraper:** se ejecuta cada hora via EventBridge Scheduler. Si detecta condición crítica, publica en SNS → SQS → Lambda de reasignación.

---

## Flujo EDA Principal

```
[Cliente crea solicitud en Frontend]
        │
        ▼
  API Gateway → Lambda (MS1)
        │  guarda en RDS
        │
        ▼
  SNS: publica "new_request"
        │
        ▼
  SQS: cola de asignación
        │
        ▼
  Lambda (MS3): evalúa técnicos disponibles (MS2)
        │  asigna el más cercano y disponible
        │
        ├──▶ DynamoDB: crea Job record
        │
        ├──▶ SNS: "job_assigned" → notifica técnico (email/push)
        │
        └──▶ SNS: "job_assigned" → notifica cliente con ETA
                    │
                    ▼
              Lambda (MS4): registra evento en DynamoDB
```

## Flujo EDA — Weather Alert

```
[EventBridge Scheduler — cada hora]
        │
        ▼
  Lambda (MS6): scrapea Senamhi / llama OpenWeatherMap
        │  detecta condición crítica (lluvia fuerte, tormenta)
        │
        ▼
  DynamoDB: guarda WeatherAlert
        │
        ▼
  SNS: publica "weather_alert"
        │
        ▼
  SQS: cola de reasignación
        │
        ▼
  Lambda (MS3): busca jobs afectados (outdoor, en zona)
        │
        ├──▶ Reasigna o marca como "suspended"
        │
        └──▶ SNS: notifica a clientes y técnicos afectados
```

---

## Uso de Servicios AWS

| Servicio | Uso |
|---|---|
| **S3** | Fotos del problema (cliente) y evidencia del trabajo (técnico) — subidas desde el frontend |
| **SNS** | Notificaciones de nuevas solicitudes, asignaciones, cambios de estado, alertas climáticas |
| **SQS** | Buffer de asignación de trabajos (absorbe picos) y cola de reasignación por clima |
| **RDS** | MS1, MS2, MS5 — con patrón Multi-tenancy Schema por tenant |
| **DynamoDB** | MS3, MS4, MS6 — datos de acceso frecuente y alta velocidad |
| **Lambda** | Todos los microservicios + scraper climático |
| **API Gateway** | Expone todos los microservicios, protegidos con Cognito/JWT |
| **Amplify** | Frontend desplegado |
| **EventBridge** | Scheduler para el scraper climático (cada hora) |
| **Serverless Framework** | Automatiza todo el despliegue |

---

## Demo con 2 Tenants

**Escenario demo:**

1. Ingresar como `aquafix` → crear solicitud de plomería
2. Ver asignación automática de técnico en tiempo real
3. Cliente recibe notificación
4. Técnico sube foto desde app → guardada en S3
5. Cerrar trabajo → factura generada automáticamente
6. Cambiar a tenant `climatech` → ver datos completamente aislados
7. Disparar alerta climática manualmente → ver reasignación automática de trabajos outdoor

---

## Datos Ficticios (30,000 registros por microservicio, 3 tenants)

| Microservicio | Registros por tenant | Total |
|---|---|---|
| MS1 Customers & Requests | ~10,000 | 30,000 |
| MS2 Technician Management | ~10,000 | 30,000 |
| MS3 Job Dispatch & Tracking | ~10,000 | 30,000 |
| MS4 Notifications & Event Log | ~10,000 | 30,000 |
| MS5 Billing & Analytics | ~10,000 | 30,000 |
| MS6 Weather & External Alerts | ~10,000 | 30,000 |
