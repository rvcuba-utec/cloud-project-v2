import { useEffect, useId, useState, type PointerEvent, type ReactNode } from 'react';
import type { Visita } from '../api/recursos';
import { ESTADOS_VISITA, horaLima, hoyLima } from './formato';

export const HORA_INICIO = 7;
export const HORA_FIN = 19;
export const ALTO_HORA = 56;

const minutos = (hhmm: string) => Number(hhmm.slice(0, 2)) * 60 + Number(hhmm.slice(3, 5));
export const posicion = (inicio: string, fin: string) => {
  const desde = minutos(horaLima(inicio)) - HORA_INICIO * 60;
  const hasta = minutos(horaLima(fin)) - HORA_INICIO * 60;
  return { top: (desde / 60) * ALTO_HORA, height: Math.max(22, ((hasta - desde) / 60) * ALTO_HORA - 3) };
};

export const ESTILO_VISITA: Record<string, string> = {
  PROGRAMADA: 'border-warning/45 bg-warning-soft text-ink',
  EN_ATENCION: 'border-info/45 bg-info-soft text-ink',
  FINALIZADA: 'border-good/40 bg-good-soft text-ink',
  CANCELADA: 'border-line bg-surface/50 text-muted line-through',
};

export function claseVisita(v: Visita) {
  return v.requiere_reprogramacion ? 'border-critical bg-critical-soft text-ink' : ESTILO_VISITA[v.estado];
}

/** Solo se mueven las visitas PROGRAMADAS (también las que quedaron sin técnico). */
export const esMovible = (v: Visita) => v.estado === 'PROGRAMADA';

/** El estado nunca va solo en color: cada bloque lleva su ícono (reloj, pulso o marca). */
function IconoEstado({ v }: { v: Visita }) {
  if (v.requiere_reprogramacion) return <span className="text-[11px] font-semibold text-critical">Sin técnico</span>;
  if (v.estado === 'EN_ATENCION') return <span className="relative inline-flex size-2" aria-hidden="true"><span className="pulso absolute inset-0 rounded-full bg-info" /><span className="relative size-2 rounded-full bg-info" /></span>;
  if (v.estado === 'FINALIZADA') return <svg viewBox="0 0 16 16" className="size-3 shrink-0 text-good" aria-hidden="true"><path d="m3 8.5 3.2 3.2L13 4.8" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>;
  if (v.estado === 'PROGRAMADA') return <svg viewBox="0 0 16 16" className="size-3 shrink-0 text-warning" aria-hidden="true"><circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" strokeWidth="1.5" /><path d="M8 4.8V8l2 1.2" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>;
  return null;
}

export function BloqueVisita({ v, onClick, detalle, onArrastrar, arrastrando = false, enVuelo = false }: {
  v: Visita; onClick?: () => void; detalle?: ReactNode;
  /** Si se pasa, el bloque se puede arrastrar; recibe el evento y el desplazamiento vertical del puntero dentro del bloque. */
  onArrastrar?: (e: PointerEvent<HTMLButtonElement>, offsetY: number) => void;
  arrastrando?: boolean; enVuelo?: boolean;
}) {
  const p = posicion(v.inicio, v.fin);
  const movible = Boolean(onArrastrar) && esMovible(v) && !enVuelo;
  const fijo = Boolean(onArrastrar) && !esMovible(v);
  return (
    <button type="button" onClick={onClick} style={{ top: p.top + 1, height: p.height }}
      data-visita={v.visita_id}
      onPointerDown={movible ? (e) => onArrastrar!(e, e.clientY - e.currentTarget.getBoundingClientRect().top) : undefined}
      title={`${horaLima(v.inicio)}–${horaLima(v.fin)} · ${v.cliente_nombre} · ${v.requiere_reprogramacion ? 'Sin técnico' : ESTADOS_VISITA[v.estado]}${movible ? ' · Arrástrala para reprogramar' : fijo ? ' · No se puede mover' : ''}`}
      className={`absolute inset-x-1 overflow-hidden rounded-lg border px-2 py-1 text-left text-[13px] leading-tight transition-[transform,opacity] select-none hover:-translate-y-px hover:shadow-md ${claseVisita(v)} ${movible ? 'cursor-grab active:cursor-grabbing' : ''} ${fijo ? 'bloque-fijo' : ''} ${arrastrando ? 'opacity-35' : ''} ${enVuelo ? 'animate-pulse opacity-70' : ''}`}>
      <span className="flex items-center justify-between gap-1 font-medium">
        <span className="truncate"><span className="tabular font-normal opacity-75">{horaLima(v.inicio)}</span> {v.cliente_nombre}</span>
        <span className="flex shrink-0 items-center gap-1.5">
        <IconoEstado v={v} />
        {movible && (
          <svg viewBox="0 0 10 14" className="asa-arrastre size-3 shrink-0 opacity-45" aria-hidden="true">
            <circle cx="3" cy="3" r="1.1" fill="currentColor" /><circle cx="7" cy="3" r="1.1" fill="currentColor" />
            <circle cx="3" cy="7" r="1.1" fill="currentColor" /><circle cx="7" cy="7" r="1.1" fill="currentColor" />
            <circle cx="3" cy="11" r="1.1" fill="currentColor" /><circle cx="7" cy="11" r="1.1" fill="currentColor" />
          </svg>
        )}
        {fijo && (
          <svg viewBox="0 0 16 16" className="size-3 shrink-0 opacity-55" aria-hidden="true">
            <path d="M5 7V5a3 3 0 0 1 6 0v2h1a1 1 0 0 1 1 1v5a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1h1Zm1.5 0h3V5a1.5 1.5 0 0 0-3 0v2Z" fill="currentColor" />
          </svg>
        )}
        </span>
      </span>
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
        <span key={h} className="tabular absolute right-2 -translate-y-1/2 font-mono text-[11px] text-muted" style={{ top: (h - HORA_INICIO) * ALTO_HORA }}>{String(h).padStart(2, '0')}:00</span>
      ))}
    </div>
  );
}

/** Franja que muestra dónde caería lo que se arrastra: verde si cabe, roja si no. */
export interface DestinoVisual { top: number; alto: number; hora: string; valido: boolean }

/** Hora de Lima en minutos, actualizada cada minuto, para dibujar la línea de «ahora». */
function useAhoraMin() {
  const calc = () => minutos(horaLima(new Date().toISOString()));
  const [min, setMin] = useState(calc);
  useEffect(() => { const t = setInterval(() => setMin(calc()), 60_000); return () => clearInterval(t); }, []);
  return min;
}

function Trama() {
  const id = useId();
  return (
    <svg className="pointer-events-none absolute inset-0 size-full text-critical opacity-[.22]" aria-hidden="true">
      <defs><pattern id={id} width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><path d="M0 0V10" stroke="currentColor" strokeWidth="1.5" /></pattern></defs>
      <rect width="100%" height="100%" fill={`url(#${id})`} />
    </svg>
  );
}

export function Columna({ children, tono, intervalos, tecnicoId, fecha, destino, atenuada = false }: {
  children: ReactNode; tono?: 'ausente' | 'libre'; intervalos?: { inicio: string; fin: string }[];
  /** Con estos dos datos la columna acepta que se suelte algo encima. */
  tecnicoId?: string; fecha?: string; destino?: DestinoVisual; atenuada?: boolean;
}) {
  const horas = Array.from({ length: HORA_FIN - HORA_INICIO }, (_, i) => i);
  const ahora = useAhoraMin();
  const esHoy = fecha !== undefined && fecha === hoyLima();
  const topAhora = ((ahora - HORA_INICIO * 60) / 60) * ALTO_HORA;
  return (
    <div data-col-tecnico={tecnicoId} data-col-fecha={fecha}
      className={`relative border-l border-line ${tono === 'ausente' ? 'bg-critical-soft/40' : ''} ${esHoy && tono !== 'ausente' ? 'bg-accent-soft/30' : ''} ${atenuada ? 'opacity-50' : ''}`}
      style={{ height: (HORA_FIN - HORA_INICIO) * ALTO_HORA }}>
      {tono === 'ausente' && <Trama />}
      {horas.map((h) => <div key={h} className="absolute inset-x-0 border-t border-line/70" style={{ top: h * ALTO_HORA }} />)}
      {intervalos?.map((i) => {
        const top = ((minutos(i.inicio) - HORA_INICIO * 60) / 60) * ALTO_HORA;
        const alto = ((minutos(i.fin) - minutos(i.inicio)) / 60) * ALTO_HORA;
        return <div key={i.inicio} className="absolute inset-x-0 bg-card/70" style={{ top, height: alto }} aria-hidden="true" />;
      })}
      {children}
      {esHoy && topAhora > 0 && topAhora < (HORA_FIN - HORA_INICIO) * ALTO_HORA && (
        <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 z-[5] h-0 border-t-[1.5px] border-accent" style={{ top: topAhora }}>
          <span className="absolute -left-1 -top-[5px] size-2 rounded-full bg-accent" />
        </div>
      )}
      {destino && (
        <div aria-hidden="true" style={{ top: destino.top + 1, height: Math.max(22, destino.alto - 3) }}
          className={`pointer-events-none absolute inset-x-1 z-10 rounded-lg border-2 border-dashed px-2 py-0.5 text-[12px] font-medium ${destino.valido ? 'border-good bg-good-soft/80 text-good' : 'border-critical bg-critical-soft/80 text-critical'}`}>
          {destino.hora}
        </div>
      )}
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
      <li className="flex items-center gap-1.5"><span className="size-3 rounded border border-dashed border-critical/60 bg-critical-soft/60" />Ausente o sin jornada</li>
      <li className="flex items-center gap-1.5"><span className="h-0 w-3 border-t-[1.5px] border-accent" />Ahora</li>
    </ul>
  );
}
