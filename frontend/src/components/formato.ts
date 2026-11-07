import type { EstadoOrden, EstadoVisita, Prioridad, Especialidad, ResultadoParte } from '../api/recursos';

export const ZONA = 'America/Lima';

export function fechaHora(iso: string): string {
  return new Intl.DateTimeFormat('es-PE', { dateStyle: 'short', timeStyle: 'short', timeZone: ZONA }).format(new Date(iso));
}

export function porcentaje(tasa: number): string {
  return `${Math.round(tasa * 100)} %`;
}

export function hoyLima(): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: ZONA }).format(new Date());
}

export function sumarDias(fecha: string, dias: number): string {
  const d = new Date(`${fecha}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + dias);
  return d.toISOString().slice(0, 10);
}

export const ESTADOS_ORDEN: Record<EstadoOrden, string> = {
  ABIERTA: 'Abierta',
  PROGRAMADA: 'Programada',
  EN_ATENCION: 'En atención',
  REQUIERE_REVISITA: 'Requiere otra visita',
  PENDIENTE_DE_CIERRE: 'Pendiente de cierre',
  CIERRE_EN_PROCESO: 'Cerrando',
  CERRADA: 'Cerrada',
  CANCELADA: 'Cancelada',
};

export const PRIORIDADES: Record<Prioridad, string> = { BAJA: 'Baja', MEDIA: 'Media', ALTA: 'Alta' };

export const ESPECIALIDADES: Record<Especialidad, string> = {
  INSTALACION: 'Instalación',
  MANTENIMIENTO: 'Mantenimiento',
  REPARACION: 'Reparación',
};

export const ESTADOS_VISITA: Record<EstadoVisita, string> = {
  PROGRAMADA: 'Programada',
  EN_ATENCION: 'En atención',
  FINALIZADA: 'Finalizada',
  CANCELADA: 'Cancelada',
};

export const RESULTADOS: Record<ResultadoParte, string> = {
  RESUELTO: 'Resuelto',
  REQUIERE_REVISITA: 'Requiere otra visita',
  NO_ATENDIDO: 'No atendido',
};

/** De fecha y hora de Lima al instante UTC que espera la API. */
export function instanteLima(fecha: string, hora: string, minutosExtra = 0): string {
  const d = new Date(`${fecha}T${hora}:00-05:00`);
  d.setUTCMinutes(d.getUTCMinutes() + minutosExtra);
  return d.toISOString().replace('.000Z', 'Z');
}

export function horaLima(iso: string): string {
  return new Intl.DateTimeFormat('es-PE', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23', timeZone: ZONA }).format(new Date(iso));
}

export function fechaLarga(fecha: string): string {
  return new Intl.DateTimeFormat('es-PE', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'UTC' }).format(new Date(`${fecha}T12:00:00Z`));
}

export function fechaCorta(fecha: string): string {
  return new Intl.DateTimeFormat('es-PE', { weekday: 'short', day: 'numeric', timeZone: 'UTC' }).format(new Date(`${fecha}T12:00:00Z`));
}

/** Lunes de la semana de una fecha (AAAA-MM-DD). */
export function lunesDe(fecha: string): string {
  const d = new Date(`${fecha}T12:00:00Z`);
  const dia = (d.getUTCDay() + 6) % 7;
  return sumarDias(fecha, -dia);
}

export function hace(iso: string): string {
  const s = Math.max(0, Math.round((Date.now() - Date.parse(iso)) / 1000));
  if (s < 60) return 'hace un momento';
  if (s < 3600) return `hace ${Math.round(s / 60)} min`;
  if (s < 86400) return `hace ${Math.round(s / 3600)} h`;
  return fechaHora(iso);
}
