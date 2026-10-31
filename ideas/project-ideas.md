# Ideas de Proyecto — FSM SaaS (Grupo 5)

> **Tipo asignado:** Field Service Management (FSM)  
> **Arquitectura requerida:** Multi-tenancy · Serverless · EDA  
> **Stack:** AWS (API Gateway + Lambda + RDS + DynamoDB + S3 + SNS + SQS + Amplify)

---

## 1. FixFlow — Mantenimiento Industrial

Gestión de órdenes de trabajo para técnicos que reparan equipos industriales (HVAC, maquinaria, energía solar).

**Tenants posibles:** Empresa de HVAC / Empresa de paneles solares / Empresa de maquinaria industrial

| # | Microservicio | DB |
|---|---|---|
| 1 | Work Orders | RDS (SQL) |
| 2 | Technicians & Skills | RDS (SQL) |
| 3 | Scheduling & Dispatch | DynamoDB |
| 4 | Inventory & Parts | DynamoDB |
| 5 | Reports & SLA | RDS (SQL) |

**Flujo EDA:** Cliente crea orden → SNS notifica → SQS cola de asignación → Lambda asigna técnico disponible → SNS notifica al técnico → S3 guarda fotos del trabajo.

---

## 2. MediField — Mantenimiento de Equipos Médicos

Coordina técnicos certificados que realizan mantenimiento preventivo/correctivo en hospitales y clínicas. Historial de compliance integrado.

**Tenants posibles:** Hospital privado / Red de clínicas / Laboratorio de diagnóstico

| # | Microservicio | DB |
|---|---|---|
| 1 | Equipment Registry | RDS (SQL) |
| 2 | Work Orders & Compliance | RDS (SQL) |
| 3 | Technician Certifications | DynamoDB |
| 4 | Scheduling | DynamoDB |
| 5 | Audit & Reports | RDS (SQL) |

**Diferenciador:** S3 para certificados de calibración, SNS para alertas de equipos críticos fuera de servicio.

---

## 3. TowerTech — Infraestructura de Telecomunicaciones ⭐

Gestiona cuadrillas que mantienen torres de antenas, repetidores y estaciones base. Incluye control de acceso a sitios remotos y registro de incidentes.

**Tenants posibles:** Operadora móvil / ISP rural / Empresa de radio FM

| # | Microservicio | DB |
|---|---|---|
| 1 | Sites & Towers | RDS (SQL) |
| 2 | Incident Management | RDS (SQL) |
| 3 | Crew Dispatch | DynamoDB |
| 4 | Equipment & Tools | DynamoDB |
| 5 | SLA & Uptime Reports | RDS (SQL) |

**Flujo EDA:** Sensor detecta caída → SNS → SQS → Lambda crea incident automático → asigna cuadrilla más cercana → S3 guarda fotos del sitio.

---

## 4. ServiPro — Servicios Domiciliarios a Demanda

Plataforma estilo "Uber para técnicos": plomeros, electricistas y técnicos de electrodomésticos gestionados por empresas de servicios al hogar.

**Tenants posibles:** Empresa de plomería / Empresa de electricidad / Empresa de electrodomésticos

| # | Microservicio | DB |
|---|---|---|
| 1 | Customers & Requests | RDS (SQL) |
| 2 | Technician Profiles | RDS (SQL) |
| 3 | Real-time Dispatch | DynamoDB |
| 4 | Quotes & Billing | DynamoDB |
| 5 | Reviews & Analytics | RDS (SQL) |

**Diferenciador:** S3 para fotos antes/después del trabajo, SNS para notificaciones al cliente en cada etapa del servicio.

---

## 5. CleanOps — Facilities Management y Limpieza Corporativa

Orquesta equipos de limpieza en edificios corporativos, hoteles y centros comerciales con control de calidad por checklist digital.

**Tenants posibles:** Empresa de limpieza / Cadena hotelera / Centro comercial

| # | Microservicio | DB |
|---|---|---|
| 1 | Contracts & Locations | RDS (SQL) |
| 2 | Staff & Routes | RDS (SQL) |
| 3 | Task Checklists | DynamoDB |
| 4 | Quality Control | DynamoDB |
| 5 | Billing & Reports | RDS (SQL) |

**Flujo EDA:** Supervisor crea inspección → SNS → SQS → Lambda asigna tarea → S3 guarda evidencia fotográfica → SNS notifica resultado al cliente.

---

## Recomendación

**TowerTech** o **MediField** son los más llamativos para exponer porque:
- El flujo EDA es natural y fácil de demostrar (alertas automáticas, asignación reactiva)
- Los datos ficticios (30k registros en 3 tenants) son fáciles de generar con sentido
- La demo con 2 tenants cuenta una historia clara
