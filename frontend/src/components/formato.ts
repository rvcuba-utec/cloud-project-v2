import type { EstadoOrden, Prioridad, Especialidad } from '../api/recursos';

export const ZONA = 'America/Lima';

export function fechaHora(iso: string): string {
  return new Intl.DateTimeFormat('es-PE', { dateStyle: 'short', timeStyle: 'short', timeZone: ZONA }).format(new Date(iso));
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
