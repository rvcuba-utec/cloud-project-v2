import { useMemo, type PointerEvent } from 'react';
import { Link } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { ordenes, type Especialidad, type Orden, type Prioridad } from '../../api/recursos';
import { ESPECIALIDADES, ESTADOS_ORDEN, PRIORIDADES, hace } from '../formato';
import { Cargando, Insignia, MensajeError, type Tono } from '../ui';

const PESO_PRIORIDAD: Record<Prioridad, number> = { ALTA: 0, MEDIA: 1, BAJA: 2 };
const TONO_PRIORIDAD: Record<Prioridad, Tono> = { ALTA: 'critico', MEDIA: 'aviso', BAJA: 'neutro' };
export const DURACION_BANDEJA_MIN = 60;

/** Bandeja lateral con órdenes abiertas o que requieren otra visita.
    Se arrastran al calendario para programarlas (60 min, POST /visitas). */
export default function BandejaOrdenes({ especialidad, abierta, onAlternar, onArrastrar, arrastrandoId, ocupado = false }: {
  especialidad: Especialidad | '';
  abierta: boolean;
  onAlternar: () => void;
  onArrastrar: (e: PointerEvent<HTMLElement>, orden: Orden) => void;
  arrastrandoId?: string;
  ocupado?: boolean;
}) {
  const abiertas = useQuery({
    queryKey: ['bandeja-ordenes', 'ABIERTA'],
    queryFn: () => ordenes.listar({ estado: 'ABIERTA', limit: 50 }),
    refetchInterval: 30_000,
  });
  const revisitas = useQuery({
    queryKey: ['bandeja-ordenes', 'REQUIERE_REVISITA'],
    queryFn: () => ordenes.listar({ estado: 'REQUIERE_REVISITA', limit: 50 }),
    refetchInterval: 30_000,
  });

  const lista = useMemo(() => {
    const vistas = new Map<string, Orden>();
    for (const o of [...(abiertas.data?.items ?? []), ...(revisitas.data?.items ?? [])]) {
      if (!especialidad || o.tipo_servicio === especialidad) vistas.set(o.orden_id, o);
    }
    return [...vistas.values()].sort(
      (a, b) => PESO_PRIORIDAD[a.prioridad] - PESO_PRIORIDAD[b.prioridad] || a.creada_en.localeCompare(b.creada_en),
    );
  }, [abiertas.data, revisitas.data, especialidad]);

  const cargando = abiertas.isLoading || revisitas.isLoading;
  const error = abiertas.error ?? revisitas.error;

  if (!abierta) {
    return (
      <div className="mb-3 flex items-center justify-between rounded-xl border border-line bg-card px-4 py-2.5 lg:mb-0 lg:w-12 lg:flex-col lg:items-center lg:justify-start lg:gap-3 lg:px-2 lg:py-4">
        <button type="button" onClick={onAlternar} aria-expanded={false}
          className="flex items-center gap-2 text-[14px] font-medium text-ink hover:text-accent lg:flex-col">
          <span className="inline-flex min-w-6 items-center justify-center rounded-full bg-accent-soft px-1.5 py-0.5 text-[12px] font-semibold text-accent tabular">
            {lista.length}
          </span>
          <span className="lg:[writing-mode:vertical-rl] lg:rotate-180">Órdenes sin visita</span>
        </button>
      </div>
    );
  }

  return (
    <aside aria-label="Órdenes esperando visita"
      className="flex w-full shrink-0 flex-col rounded-[20px] border border-line bg-card p-4 lg:w-72">
      <div className="mb-3 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h2 className="text-[16px] font-medium text-ink">Sin visita</h2>
          <span className="rounded-full bg-surface px-2 py-0.5 text-[12px] font-medium text-ink tabular">{lista.length}</span>
        </div>
        <button type="button" onClick={onAlternar} aria-expanded={true}
          className="text-[13px] font-medium text-muted hover:text-ink">Ocultar</button>
      </div>

      <p className="mb-3 text-[13px] text-muted">
        Arrastra una orden al calendario para programarla ({DURACION_BANDEJA_MIN} min).
      </p>

      <MensajeError error={error} />
      {cargando && <Cargando texto="Cargando órdenes…" />}
      {!cargando && !error && lista.length === 0 && (
        <p className="rounded-xl border border-dashed border-line p-4 text-center text-[14px] text-muted">
          No hay órdenes esperando visita{especialidad ? ` de ${ESPECIALIDADES[especialidad].toLowerCase()}` : ''}.
        </p>
      )}

      <ul className="flex max-h-[640px] flex-col gap-2 overflow-y-auto pr-0.5">
        {lista.map((o) => {
          const activa = arrastrandoId === o.orden_id;
          return (
            <li key={o.orden_id}
              onPointerDown={!ocupado ? (e) => onArrastrar(e, o) : undefined}
              title={`Arrastra para programar · ${o.cliente_nombre} (${ESPECIALIDADES[o.tipo_servicio]})`}
              className={`rounded-xl border border-line bg-ground/70 p-3 select-none transition-[transform,opacity,box-shadow] ${!ocupado ? 'cursor-grab hover:-translate-y-px hover:border-line-strong hover:shadow-sm active:cursor-grabbing' : 'opacity-60'} ${activa ? 'opacity-35' : ''}`}>
              <div className="flex items-start justify-between gap-2">
                <p className="truncate text-[14px] font-medium text-ink">{o.cliente_nombre}</p>
                <svg viewBox="0 0 10 14" className="asa-arrastre mt-0.5 size-3.5 shrink-0 text-muted" aria-hidden="true">
                  <circle cx="3" cy="3" r="1.1" fill="currentColor" /><circle cx="7" cy="3" r="1.1" fill="currentColor" />
                  <circle cx="3" cy="7" r="1.1" fill="currentColor" /><circle cx="7" cy="7" r="1.1" fill="currentColor" />
                  <circle cx="3" cy="11" r="1.1" fill="currentColor" /><circle cx="7" cy="11" r="1.1" fill="currentColor" />
                </svg>
              </div>
              <p className="mt-0.5 truncate text-[13px] text-muted">{o.distrito} · {ESPECIALIDADES[o.tipo_servicio]}</p>
              <p className="mt-1 line-clamp-2 text-[13px] text-ink/85">{o.descripcion}</p>
              <div className="mt-2 flex flex-wrap items-center justify-between gap-1.5">
                <div className="flex flex-wrap items-center gap-1.5">
                  <Insignia tono={TONO_PRIORIDAD[o.prioridad]}>{PRIORIDADES[o.prioridad]}</Insignia>
                  {o.estado === 'REQUIERE_REVISITA' && <Insignia tono="info">{ESTADOS_ORDEN.REQUIERE_REVISITA}</Insignia>}
                </div>
                <span className="text-[12px] text-muted">{hace(o.creada_en)}</span>
              </div>
              <div className="mt-2 flex justify-end">
                <Link to={`/ordenes/${o.orden_id}`} onPointerDown={(e) => e.stopPropagation()}
                  className="text-[12px] font-medium text-accent hover:underline">Abrir orden</Link>
              </div>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}
