import { ZONA, instanteLima } from '../formato';

/** Lógica pura del arrastrar y soltar de la Agenda. Espeja las reglas de backend/agenda/dominio/agenda.py,
    pero solo como ayuda visual: quien decide siempre es el backend. */

export const PASO_MIN = 30;
export const DURACION_MIN = 30;
export const DURACION_MAX = 240;

export type Motivo = 'PASADO' | 'FUERA_DE_JORNADA' | 'CHOCA' | 'ESPECIALIDAD' | 'DURACION';

export const TEXTO_MOTIVO: Record<Motivo, string> = {
  PASADO: 'Ese horario ya pasó',
  FUERA_DE_JORNADA: 'Fuera de la jornada del técnico',
  CHOCA: 'Choca con otra visita',
  ESPECIALIDAD: 'El técnico no tiene esa especialidad',
  DURACION: 'La duración no es válida',
};

const minutos = (hhmm: string) => Number(hhmm.slice(0, 2)) * 60 + Number(hhmm.slice(3, 5));
const hhmm = (min: number) => `${String(Math.floor(min / 60)).padStart(2, '0')}:${String(min % 60).padStart(2, '0')}`;

const horaDe = (iso: string) =>
  new Intl.DateTimeFormat('es-PE', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23', timeZone: ZONA }).format(new Date(iso));
const fechaDe = (iso: string) => new Intl.DateTimeFormat('en-CA', { timeZone: ZONA }).format(new Date(iso));

/** De la posición vertical (px) dentro de la columna a una hora HH:MM ajustada a bloques de 30 min.
    Nunca devuelve una hora cuyo fin se salga de la rejilla. */
export function horaDesdeY(y: number, altoHora: number, horaInicio: number, horaFin: number, duracionMin = PASO_MIN): string {
  const crudo = (y / altoHora) * 60;
  const ajustado = Math.round(crudo / PASO_MIN) * PASO_MIN;
  const minimo = horaInicio * 60;
  const maximo = Math.max(minimo, horaFin * 60 - duracionMin);
  return hhmm(Math.min(maximo, Math.max(minimo, minimo + ajustado)));
}

/** Posición vertical (px) de una hora HH:MM dentro de la columna. */
export function yDesdeHora(hora: string, altoHora: number, horaInicio: number): number {
  return ((minutos(hora) - horaInicio * 60) / 60) * altoHora;
}

/** Mueve un bloque conservando su duración. Devuelve inicio y fin en UTC, como espera la API. */
export function moverBloque(fecha: string, hora: string, duracionMin: number): { inicio: string; fin: string } {
  return { inicio: instanteLima(fecha, hora), fin: instanteLima(fecha, hora, duracionMin) };
}

export function duracionDe(inicio: string, fin: string): number {
  return Math.round((Date.parse(fin) - Date.parse(inicio)) / 60000);
}

export interface Ocupada { visita_id: string; inicio: string; fin: string }

export interface ContextoSoltar {
  ahora: Date;
  /** Jornada del técnico ese día (HH:MM de Lima). Sin intervalos: no trabaja o está ausente. */
  intervalos: { inicio: string; fin: string }[] | undefined;
  /** Visitas no canceladas del técnico, de cualquier día cercano. */
  ocupadas: Ocupada[];
  especialidades: string[];
  especialidadRequerida: string;
  /** La visita que se mueve no choca consigo misma. */
  ignorarVisitaId?: string;
}

/** Motivo por el que NO se puede soltar, o null si cabe. */
export function validarSoltar(inicio: string, fin: string, ctx: ContextoSoltar): Motivo | null {
  const dur = duracionDe(inicio, fin);
  if (dur < DURACION_MIN || dur > DURACION_MAX || dur % PASO_MIN !== 0 || fechaDe(inicio) !== fechaDe(fin)) return 'DURACION';
  if (Date.parse(inicio) < ctx.ahora.getTime()) return 'PASADO';
  if (!ctx.especialidades.includes(ctx.especialidadRequerida)) return 'ESPECIALIDAD';
  const desde = minutos(horaDe(inicio));
  const hasta = minutos(horaDe(fin));
  const cabe = (ctx.intervalos ?? []).some((i) => desde >= minutos(i.inicio) && hasta <= minutos(i.fin));
  if (!cabe) return 'FUERA_DE_JORNADA';
  const a = Date.parse(inicio);
  const b = Date.parse(fin);
  const choca = ctx.ocupadas.some((o) => o.visita_id !== ctx.ignorarVisitaId && a < Date.parse(o.fin) && Date.parse(o.inicio) < b);
  return choca ? 'CHOCA' : null;
}
