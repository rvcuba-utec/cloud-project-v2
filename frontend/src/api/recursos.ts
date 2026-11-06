import { api } from './client';

export interface Pagina<T> {
  items: T[];
  next_cursor: string | null;
}

export interface Cliente {
  cliente_id: string;
  nombre: string;
  telefono?: string;
  correo?: string;
  activo: boolean;
}

export interface Ubicacion {
  ubicacion_id: string;
  cliente_id: string;
  nombre: string;
  direccion: string;
  distrito: string;
  referencia?: string;
}

export type Especialidad = 'INSTALACION' | 'MANTENIMIENTO' | 'REPARACION';
export type Prioridad = 'BAJA' | 'MEDIA' | 'ALTA';
export type EstadoOrden =
  | 'ABIERTA' | 'PROGRAMADA' | 'EN_ATENCION' | 'REQUIERE_REVISITA'
  | 'PENDIENTE_DE_CIERRE' | 'CIERRE_EN_PROCESO' | 'CERRADA' | 'CANCELADA';

export interface Tecnico {
  tecnico_id: string;
  nombre: string;
  especialidades: Especialidad[];
  activo: boolean;
}

export interface Intervalo {
  inicio: string;
  fin: string;
}

export interface Jornada {
  fecha: string;
  intervalos: Intervalo[];
}

export interface Ausencia {
  fecha: string;
  motivo: string;
}

export interface Orden {
  orden_id: string;
  cliente_id: string;
  ubicacion_id: string;
  cliente_nombre: string;
  direccion: string;
  distrito: string;
  tipo_servicio: Especialidad;
  descripcion: string;
  prioridad: Prioridad;
  estado: EstadoOrden;
  version: number;
  creada_en: string;
}

export interface EntradaHistorial {
  tipo: string;
  detalle: string;
  ocurrido_en: string;
}

export function consulta(parametros: Record<string, string | number | undefined | null>): string {
  const q = new URLSearchParams();
  Object.entries(parametros).forEach(([clave, valor]) => {
    if (valor !== undefined && valor !== null && valor !== '') q.set(clave, String(valor));
  });
  const texto = q.toString();
  return texto ? `?${texto}` : '';
}

export const clientes = {
  listar: (p: { q?: string; cursor?: string | null; limit?: number }) =>
    api<Pagina<Cliente>>('clientes', `/clientes${consulta(p)}`),
  detalle: (id: string) => api<Cliente>('clientes', `/clientes/${id}`),
  crear: (datos: Partial<Cliente>, idempotencyKey: string) =>
    api<Cliente>('clientes', '/clientes', { method: 'POST', body: datos, idempotencyKey }),
  actualizar: (id: string, datos: Partial<Cliente>) =>
    api<Cliente>('clientes', `/clientes/${id}`, { method: 'PATCH', body: datos }),
  ubicaciones: (id: string) => api<Pagina<Ubicacion>>('clientes', `/clientes/${id}/ubicaciones?limit=100`),
  crearUbicacion: (id: string, datos: Partial<Ubicacion>, idempotencyKey: string) =>
    api<Ubicacion>('clientes', `/clientes/${id}/ubicaciones`, { method: 'POST', body: datos, idempotencyKey }),
};

export const tecnicos = {
  listar: (p: { cursor?: string | null; limit?: number }) => api<Pagina<Tecnico>>('tecnicos', `/tecnicos${consulta(p)}`),
  detalle: (id: string) => api<Tecnico>('tecnicos', `/tecnicos/${id}`),
  crear: (datos: Partial<Tecnico>, idempotencyKey: string) =>
    api<Tecnico>('tecnicos', '/tecnicos', { method: 'POST', body: datos, idempotencyKey }),
  actualizar: (id: string, datos: Partial<Tecnico>) =>
    api<Tecnico>('tecnicos', `/tecnicos/${id}`, { method: 'PATCH', body: datos }),
  jornadas: (id: string, desde: string, hasta: string) =>
    api<{ jornadas: Jornada[]; ausencias: Ausencia[] }>('tecnicos', `/tecnicos/${id}/jornadas${consulta({ desde, hasta })}`),
  definirJornada: (id: string, fecha: string, intervalos: Intervalo[]) =>
    api<Jornada>('tecnicos', `/tecnicos/${id}/jornadas/${fecha}`, { method: 'PUT', body: { intervalos } }),
  registrarAusencia: (id: string, fecha: string, motivo: string) =>
    api<Ausencia>('tecnicos', `/tecnicos/${id}/ausencias/${fecha}`, { method: 'PUT', body: { motivo } }),
};

export const ordenes = {
  listar: (p: { estado?: string; cliente_id?: string; cursor?: string | null; limit?: number }) =>
    api<Pagina<Orden>>('ordenes', `/ordenes${consulta(p)}`),
  detalle: (id: string) => api<Orden>('ordenes', `/ordenes/${id}`),
  crear: (datos: Record<string, unknown>, idempotencyKey: string) =>
    api<Orden>('ordenes', '/ordenes', { method: 'POST', body: datos, idempotencyKey }),
  cambiarPrioridad: (id: string, prioridad: Prioridad, version: number) =>
    api<Orden>('ordenes', `/ordenes/${id}`, { method: 'PATCH', body: { prioridad, version } }),
  historial: (id: string) => api<Pagina<EntradaHistorial>>('ordenes', `/ordenes/${id}/historial?limit=50`),
  cerrar: (id: string) => api<Orden>('ordenes', `/ordenes/${id}/cerrar`, { method: 'POST' }),
  cancelar: (id: string) => api<Orden>('ordenes', `/ordenes/${id}/cancelar`, { method: 'POST' }),
};

export type EstadoVisita = 'PROGRAMADA' | 'EN_ATENCION' | 'FINALIZADA' | 'CANCELADA';

export interface Visita {
  visita_id: string;
  orden_id: string;
  tecnico_id: string;
  tecnico_nombre: string;
  orden_descripcion: string;
  cliente_nombre: string;
  direccion: string;
  distrito: string;
  tipo_servicio: Especialidad;
  inicio: string;
  fin: string;
  fecha: string;
  estado: EstadoVisita;
  numero_visita_orden: number;
  version: number;
}

export interface OpcionTecnico {
  tecnico_id: string;
  nombre: string;
  especialidades: Especialidad[];
  horarios: string[];
  justificacion?: string;
}

export const agenda = {
  listar: (p: { fecha?: string; desde?: string; tecnico_id?: string; orden_id?: string; cursor?: string | null; limit?: number }) =>
    api<Pagina<Visita>>('agenda', `/visitas${consulta(p)}`),
  detalle: (id: string) => api<Visita>('agenda', `/visitas/${id}`),
  disponibilidad: (p: { fecha: string; especialidad?: string; duracion_min: number; sugerir?: boolean }) =>
    api<{ items: OpcionTecnico[] }>('agenda', `/disponibilidad${consulta({ ...p, sugerir: p.sugerir ? 'true' : undefined })}`),
  programar: (datos: { orden_id: string; tecnico_id: string; inicio: string; fin: string }, idempotencyKey: string) =>
    api<Visita>('agenda', '/visitas', { method: 'POST', body: datos, idempotencyKey }),
  reprogramar: (id: string, datos: { inicio: string; fin: string; version: number; tecnico_id?: string }) =>
    api<Visita>('agenda', `/visitas/${id}/reprogramar`, { method: 'POST', body: datos }),
  cancelar: (id: string) => api<Visita>('agenda', `/visitas/${id}/cancelar`, { method: 'POST' }),
  iniciar: (id: string) => api<Visita>('agenda', `/visitas/${id}/iniciar`, { method: 'POST' }),
};
