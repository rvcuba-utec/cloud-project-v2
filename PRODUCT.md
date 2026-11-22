# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
Dueños y coordinadores de empresas de servicio técnico en campo (climatización, refrigeración, mantenimiento) con 5 a 40 técnicos, como las empresas demo ClimaLima, FríoSur y TecniNorte. Coordinan desde un escritorio: reparten órdenes, arman la agenda del día y reaccionan cuando un técnico falla. Los técnicos usan el celular (Mis visitas, Atención, partes con fotos), pero el rediseño actual es solo de escritorio.
Roles reales: Administrador, Coordinador, Técnico.

## Product Purpose
Trazora es un SaaS multitenant de gestión de visitas técnicas. Une órdenes, agenda, partes con fotos y analítica de técnicos. Éxito: el coordinador ve en una pantalla qué falta atender, quién está libre y qué resolvió el sistema solo.

## Positioning
Si un técnico no puede asistir, sus visitas se reasignan solas al técnico libre con la especialidad, menos carga del día y mejor resolución sin revisita, con la razón a la vista. Cada media hora se reserva una sola vez (sin dobles reservas). Aislamiento total entre empresas.

## Operating Context
Pantallas reales: Login (código de empresa + correo + contraseña), Panel (cifras, mapa de Lima, reprogramación urgente, "Lo que el sistema resolvió solo", anillo del mes, rendimiento, visitas de hoy), Órdenes, Nueva orden, Agenda (vista Día/Semana, bandeja "Sin visita", arrastrar y soltar, "Marcar ausente"), Clientes, Técnicos, Usuarios, Mis visitas, Atención. Estados de orden agrupados en 4: Sin atender (rojo), Con visita (ámbar), En atención (azul), Atendida (verde). Zona horaria Lima; distritos como Miraflores, San Isidro, Surco, Lince.

## Capabilities and Constraints
Frontend: React 19, Vite, Tailwind 4, Leaflet, TanStack Query, react-router. Backend serverless en AWS. Escritorio primero para el coordinador; el técnico usa el celular. Las maquetas de referencia están en /mockups.
Sin dominio propio ni clientes reales: no inventar testimonios, logos de clientes ni métricas de mercado. Los datos de demostración (ClimaLima, Carlos Villanueva, Ana Huamán, 95 % de resolución) salen del repo.

## Brand Commitments
Nombre: Trazora. El usuario pidió explícitamente una identidad sobria, técnica y moderna, profesional, sin estética de papel ni artesanal, sin gradientes, con color con propósito. Identidad elegida: la dirección B (grafito neutro, radios generosos, Bricolage Grotesque, Onest y Fragment Mono) con el azul cobalto de la dirección A como único acento; el verde pino y el lima quedaron descartados. Landing más moderada y ordenada que la maqueta B; la app mantiene el estilo de la maqueta de agenda. Modo claro y oscuro. Idioma: español neutro de Perú.

## Evidence on Hand
Portada en frontend/public/presentacion/ (index.html, landing.css, landing.js): tablero con una reasignación en bucle, mapa, parte con fotos. Guion de demo en docs/guia-demo.md. No hay capturas de clientes ni testimonios reales.

## Product Principles
1. La razón a la vista: cada decisión automática muestra por qué.
2. Un solo lugar: orden, visita, parte y analítica se leen juntos.
3. El estado nunca va solo en color: siempre con texto o ícono.
4. Lo urgente sube; lo resuelto se atenúa.
