import type { ReactNode } from 'react';
import type { Visita } from '../api/recursos';
import { ESTADOS_VISITA, horaLima } from './formato';

export const HORA_INICIO = 7;
export const HORA_FIN = 19;
const ALTO_HORA = 56;

const minutos = (hhmm: string) => Number(hhmm.slice(0, 2)) * 60 + Number(hhmm.slice(3, 5));
export const posicion = (inicio: string, fin: string) => {
  const desde = minutos(horaLima(inicio)) - HORA_INICIO * 60;
  const hasta = minutos(horaLima(fin)) - HORA_INICIO * 60;
  return { top: (desde / 60) * ALTO_HORA, height: Math.max(22, ((hasta - desde) / 60) * ALTO_HORA - 3) };
};

export const ESTILO_VISITA: Record<string, string> = {
  PROGRAMADA: 'border-warning/40 bg-warning-soft text-ink',
  EN_ATENCION: 'border-info/40 bg-info-soft text-ink',
  FINALIZADA: 'border-good/35 bg-good-soft text-ink',
  CANCELADA: 'border-line bg-surface/50 text-muted line-through',
};

export function claseVisita(v: Visita) {
  return v.requiere_reprogramacion ? 'border-critical bg-critical-soft text-ink' : ESTILO_VISITA[v.estado];
}

export function BloqueVisita({ v, onClick, detalle }: { v: Visita; onClick?: () => void; detalle?: ReactNode }) {
  const p = posicion(v.inicio, v.fin);
  return (
    <button type="button" onClick={onClick} style={{ top: p.top + 1, height: p.height }}
      title={`${horaLima(v.inicio)}–${horaLima(v.fin)} · ${v.cliente_nombre} · ${v.requiere_reprogramacion ? 'Sin técnico' : ESTADOS_VISITA[v.estado]}`}
      className={`absolute inset-x-1 overflow-hidden rounded-lg border px-2 py-1 text-left text-[13px] leading-tight transition-transform hover:-translate-y-px hover:shadow-md ${claseVisita(v)}`}>
      <span className="block font-medium">{horaLima(v.inicio)} {v.cliente_nombre}</span>
      {p.height > 40 && <span className="block truncate opacity-80">{detalle ?? v.distrito}</span>}
      {v.reasignada_automaticamente && p.height > 56 && <span className="mt-0.5 block text-[12px] font-medium text-good">Reasignada sola</span>}
    </button>
  );
}

/** Eje de horas común a las dos vistas. */
export function Horas() {
  const horas = Array.from({ length: HORA_FIN - HORA_INICIO }, (_, i) => HORA_INICIO + i);
  return (
    <div className="relative w-14 shrink-0" style={{ height: (HORA_FIN - HORA_INICIO) * ALTO_HORA }}>
      {horas.map((h) => (
        <span key={h} className="tabular absolute right-2 -translate-y-1/2 text-[12px] text-muted" style={{ top: (h - HORA_INICIO) * ALTO_HORA }}>{String(h).padStart(2, '0')}:00</span>
      ))}
    </div>
  );
}

export function Columna({ children, tono, intervalos }: { children: ReactNode; tono?: 'ausente' | 'libre'; intervalos?: { inicio: string; fin: string }[] }) {
  const horas = Array.from({ length: HORA_FIN - HORA_INICIO }, (_, i) => i);
  return (
    <div className={`relative border-l border-line ${tono === 'ausente' ? 'bg-[repeating-linear-gradient(135deg,var(--color-critical-soft)_0_8px,transparent_8px_16px)]' : ''}`}
      style={{ height: (HORA_FIN - HORA_INICIO) * ALTO_HORA }}>
      {horas.map((h) => <div key={h} className="absolute inset-x-0 border-t border-line/70" style={{ top: h * ALTO_HORA }} />)}
      {intervalos?.map((i) => {
        const top = ((minutos(i.inicio) - HORA_INICIO * 60) / 60) * ALTO_HORA;
        const alto = ((minutos(i.fin) - minutos(i.inicio)) / 60) * ALTO_HORA;
        return <div key={i.inicio} className="absolute inset-x-0 bg-card/70" style={{ top, height: alto }} aria-hidden="true" />;
      })}
      {children}
    </div>
  );
}

export function LeyendaCalendario() {
  const items: [string, string][] = [
    ['Programada', ESTILO_VISITA.PROGRAMADA], ['En atención', ESTILO_VISITA.EN_ATENCION], ['Finalizada', ESTILO_VISITA.FINALIZADA],
    ['Sin técnico', 'border-critical bg-critical-soft'],
  ];
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-[13px] text-muted">
      {items.map(([t, c]) => <li key={t} className="flex items-center gap-1.5"><span className={`size-3 rounded border ${c}`} />{t}</li>)}
      <li className="flex items-center gap-1.5"><span className="size-3 rounded border border-line bg-[repeating-linear-gradient(135deg,var(--color-critical-soft)_0_3px,transparent_3px_6px)]" />Ausente o sin jornada</li>
    </ul>
  );
}
