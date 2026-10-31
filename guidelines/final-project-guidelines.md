# CS2032 - Cloud Computing (Ciclo 2026-2)
## Proyecto Final
**Semanas 11 a 15 — Exposición en Semana 16**
Elaborado por: Geraldo Colchado | UTEC - Universidad de Ingeniería y Tecnología

---

## Agenda

1. Competencias a lograr
2. Enunciado y Rúbrica
3. Entregables y Plazo

---

## 1. Competencias a Lograr

> Por el alumno al finalizar el proyecto final

**Competencia 4.1:** Crea, selecciona, adapta y aplica técnicas, recursos y herramientas modernas para la práctica de la computación y comprende sus limitaciones. *(nivel 3)*

---

## 2. Enunciado y Rúbrica

### Datos generales

- **Integrantes:** Mantener el mismo grupo que el Proyecto Parcial.
- **Funcionalidad:** Implementar una Solución Tecnológica Software as a Service (SaaS).

### Arquitectura requerida

- Multi-tenancy
- Serverless
- Basada en eventos (EDA)

### Rúbrica de evaluación

| Criterio | Puntos |
|---|---|
| Diagrama de Arquitectura Solución | 2 |
| BackEnd | 8 |
| FrontEnd | 6 |
| Exposición presencial | 1 |
| Exposición Virtual con ACL (avance proporcional al 30%, hasta Sábado 14-Nov) | 3 |
| **Total** | **20** |

> **Advertencia:** Si no se presenta a la exposición presencial, la evaluación será desaprobatoria (nota máxima: 10).

---

## 3. Enunciado — Solución Tecnológica SaaS

### Tipo de SaaS por Grupo

Elegir el tipo de SaaS según Grupo Canvas: `Cloud Computing (CS2032) > Personas > Grupos`

| Grupo | Tipo de SaaS | Descripción | Ejemplos |
|---|---|---|---|
| 1 | CRM | **Customer Relationship Management.** Gestiona clientes, oportunidades comerciales, ventas y relaciones comerciales. | salesforce.com / zoho.com/es-xl/crm / odoo.com/es/app/crm |
| 2 | HCM | **Human Capital Management.** Gestiona empleados, nóminas, talento, contratación y desempeño. | sap.com/products/hcm.html / bamboohr.com / workday.com |
| 3 | LMS | **Learning Management System.** Administra cursos, contenidos educativos, evaluaciones y seguimiento de estudiantes. | instructure.com/canvas / moodlecloud.com / talentlms.com |
| 4 | PPM | **Project Portfolio Management.** Gestiona proyectos, portafolios, recursos, presupuestos y prioridades. | monday.com / es.smartsheet.com / planview.com |
| 5 | FSM | **Field Service Management.** Coordina técnicos, visitas, órdenes de trabajo y servicios en campo. | salesforce.com/service/field-service-management / servicetitan.com / getjobber.com |
| 6 | ITSM | **IT Service Management.** Gestión de incidentes, problemas, cambios y solicitudes de servicios TI. | servicenow.com/products/itsm.html / atlassian.com/software/jira/service-management / freshworks.com/freshservice |

### Requerimientos Técnicos

Implementar una Solución Tecnológica **SaaS en AWS**: Multi-tenancy, serverless y basada en eventos, tomando como base las funcionalidades del tipo de SaaS asignado al grupo.

#### FrontEnd
- Usar cualquier framework.
- Desplegar en **AWS Amplify**.

#### BackEnd
- Crear mínimo **5 microservicios serverless protegidos** (API Gateway + Lambda), cada uno con su propia base de datos:
  - **SQL:** Crear un único RDS usando el patrón Multi-tenancy — *Patrón 2: Single Database, Multiple Schemas*. Presentar Diagrama Entidad-Relación por microservicio.
  - **NoSQL:** Usar DynamoDB. Presentar estructura JSON por microservicio.
- Cada microservicio debe tener **mínimo 30,000 registros ficticios** divididos en 3 tenants.
- Utilizar adicionalmente los servicios: **S3, SNS y SQS**.
- Automatizar todo el despliegue con **Serverless Framework**.

#### Otros requisitos
- Presentar un **Diagrama de Arquitectura de Solución**.
- Realizar la **Demo** con 2 tenants.

---

## 4. Entregables y Plazo

**Grupos de hasta 5 personas**

### Entregables

1. **Informe** en Word o PDF con evidencia de todo lo solicitado:
   - Incluir enlaces públicos a repositorios de código fuente.
   - Incluir diseño de la base de datos de cada microservicio.
2. **Resumen en PowerPoint** con todo lo solicitado.
3. **Exposición presencial y demo** durante la Semana 16.

### Plazo

> Máximo hasta el **domingo 22 de noviembre de 2026 a las 23:59** (entrega en Canvas).
