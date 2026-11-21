import type { Carga, Destino } from './useArrastre';
import { TEXTO_MOTIVO } from './dnd';

/** Copia del bloque que sigue al puntero mientras se arrastra. */
export default function Fantasma({ carga, puntero, destino }: { carga: Carga; puntero: { x: number; y: number }; destino: Destino | null }) {
  const anillo = !destino ? 'border-line-strong' : destino.valido ? 'border-good ring-2 ring-good/40' : 'border-critical ring-2 ring-critical/40';
  return (
    <div aria-hidden="true" style={{ left: puntero.x - 84, top: puntero.y - carga.offsetY, width: 168 }}
      className={`fantasma-arrastre fixed z-[60] rounded-lg border bg-card px-2 py-1 text-[13px] leading-tight shadow-xl ${anillo}`}>
      <span className="block truncate font-medium text-ink">{destino ? `${destino.hora} ` : ''}{carga.titulo}</span>
      {carga.subtitulo && <span className="block truncate text-muted">{carga.subtitulo}</span>}
      {destino && !destino.valido && destino.motivo && <span className="mt-0.5 block text-[12px] font-medium text-critical">{TEXTO_MOTIVO[destino.motivo]}</span>}
    </div>
  );
}
