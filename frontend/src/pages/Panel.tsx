import { useMemo, useState } from 'react';
import { Link } from 'react-router';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { agenda, alertas, analitica, mapa, tecnicos, type Alerta } from '../api/recursos';
import MapaOrdenes, { GRUPOS, grupoDe } from '../components/MapaOrdenes';
import ReprogramarVisita from '../components/ReprogramarVisita';
import { ESTADOS_VISITA, fechaLarga, hace, horaLima, hoyLima, porcentaje } from '../components/formato';
import { Boton, CAMPO, Cargando, Cifra, Encabezado, Insignia, MensajeError, Tarjeta, type Tono } from '../components/ui';

const TONO_VISITA: Record<string, Tono> = { PROGRAMADA: 'aviso', EN_ATENCION: 'info', FINALIZADA: 'bien', CANCELADA: 'neutro' };

/** Anillo de una sola medida por segmento, con su texto al lado: la leyenda es la lista misma. */
function Anillo({ partes }: { partes: { etiqueta: string; valor: number; color: string }[] }) {
  const total = partes.reduce((s, p) => s + p.valor, 0);
  const [activo, setActivo] = useState<number | null>(null);
  const R = 52, C = 2 * Math.PI * R, HUECO = 2;
  let acumulado = 0;
  return (
    <div className="flex flex-wrap items-center gap-6">
      <svg viewBox="0 0 140 140" className="size-40 shrink-0 -rotate-90" role="img"
        aria-label={partes.map((p) => `${p.etiqueta}: ${p.valor}`).join(', ')}>
        <circle cx="70" cy="70" r={R} fill="none" stroke="var(--color-surface)" strokeWidth="18" />
        {total > 0 && partes.map((p, i) => {
          const largo = (p.valor / total) * C;
          const trazo = Math.max(0, largo - (partes.filter((x) => x.valor).length > 1 ? HUECO : 0));
          const el = (
            <circle key={p.etiqueta} cx="70" cy="70" r={R} fill="none" stroke={p.color} strokeWidth={activo === i ? 22 : 18}
              strokeDasharray={`${trazo} ${C - trazo}`} strokeDashoffset={-acumulado}
              onMouseEnter={() => setActivo(i)} onMouseLeave={() => setActivo(null)} className="transition-[stroke-width] duration-150">
              <title>{`${p.etiqueta}: ${p.valor} (${Math.round((p.valor / total) * 100)} %)`}</title>
            </circle>
          );
          acumulado += largo;
          return el;
        })}
        <text x="70" y="70" transform="rotate(90 70 70)" textAnchor="middle" dominantBaseline="central"
          className="fill-ink font-display text-[26px]">{total}</text>
      </svg>
      <ul className="min-w-44 flex-1 space-y-2">
        {partes.map((p, i) => (
          <li key={p.etiqueta} onMouseEnter={() => setActivo(i)} onMouseLeave={() => setActivo(null)}
            className={`flex items-center justify-between gap-3 rounded-lg px-2 py-1 ${activo === i ? 'bg-surface/60' : ''}`}>
            <span className="flex items-center gap-2 text-[15px]"><span className="size-3 rounded-sm" style={{ background: p.color }} />{p.etiqueta}</span>
            <span className="tabular text-[15px] font-medium">{p.valor}<span className="ml-2 text-muted">{total ? Math.round((p.valor / total) * 100) : 0} %</span></span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Medidor({ valor }: { valor: number }) {
  return (
    <span className="flex items-center gap-2">
      <span className="h-1.5 w-20 overflow-hidden rounded-full bg-surface"><span className="block h-full rounded-full bg-accent" style={{ width: `${Math.round(valor * 100)}%` }} /></span>
      <span className="tabular">{porcentaje(valor)}</span>
    </span>
  );
}

function Alertas({ pendientes, onReprogramar }: { pendientes: Alerta[]; onReprogramar: (a: Alerta) => void }) {
  if (!pendientes.length) {
    return <p className="flex items-center gap-2 text-[15px] text-muted"><Insignia tono="bien">Todo en orden</Insignia> No hay visitas esperando reprogramación.</p>;
  }
  return (
    <ul className="space-y-3">
      {pendientes.map((a) => (
        <li key={a.visita_id} className="entra rounded-xl border border-critical/25 bg-critical-soft/60 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="font-medium text-ink">{a.cliente_nombre}</p>
              <p className="text-sm text-ink/80">{fechaLarga(a.fecha)}, {horaLima(a.inicio)}–{horaLima(a.fin)} · {a.distrito}</p>
              <p className="mt-1 text-sm text-critical">{a.motivo}</p>
            </div>
            <Boton pequeno flecha onClick={() => onReprogramar(a)}>Reprogramar</Boton>
          </div>
        </li>
      ))}
    </ul>
  );
}

export default function Panel() {
  const hoy = hoyLima();
  const [periodo, setPeriodo] = useState(hoy.slice(0, 7));
  const [reprogramando, setReprogramando] = useState<Alerta | null>(null);
  const avisos = useQuery({ queryKey: ['alertas'], queryFn: alertas.listar, refetchInterval: 15_000 });
  const puntos = useQuery({ queryKey: ['mapa'], queryFn: mapa.ordenes, refetchInterval: 30_000 });
  const mes = useQuery({ queryKey: ['dashboard', periodo], queryFn: () => analitica.dashboard(periodo), placeholderData: keepPreviousData, enabled: /^\d{4}-\d{2}$/.test(periodo) });
  const rendimiento = useQuery({ queryKey: ['rendimiento', hoy], queryFn: () => analitica.tecnicos(hoy) });
  const perfiles = useQuery({ queryKey: ['tecnicos-nombres'], queryFn: () => tecnicos.listar({ limit: 100 }) });
  const visitasHoy = useQuery({ queryKey: ['visitas-dia', hoy], queryFn: () => agenda.listar({ fecha: hoy, limit: 50 }), refetchInterval: 30_000 });

  const nombres = useMemo(() => new Map(perfiles.data?.items.map((t) => [t.tecnico_id, t.nombre])), [perfiles.data]);
  const filas = useMemo(() => [...(rendimiento.data?.items ?? [])]
    .map((m) => ({ ...m, nombre: nombres.get(m.tecnico_id) ?? m.tecnico_id }))
    .sort((a, b) => (b.tasa_resolucion ?? -1) - (a.tasa_resolucion ?? -1) || a.carga_dia - b.carga_dia), [rendimiento.data, nombres]);
  const porGrupo = useMemo(() => {
    const c: Record<string, number> = {};
    puntos.data?.puntos.forEach((p) => { const g = grupoDe(p.estado).id; c[g] = (c[g] ?? 0) + 1; });
    return c;
  }, [puntos.data]);
  const vivas = Object.entries(puntos.data?.conteo ?? {}).filter(([e]) => e !== 'CERRADA').reduce((s, [, n]) => s + (n ?? 0), 0);
  const pendientes = avisos.data?.pendientes ?? [];
  const d = mes.data;

  return (
    <>
      <Encabezado titulo="Panel" subtitulo={<>Lo que pasa hoy en tus órdenes, visitas y técnicos. {fechaLarga(hoy)}.</>}>
        <label className="text-sm font-medium text-ink">Mes del resumen
          <input className={`${CAMPO} !mt-1 w-44`} type="month" value={periodo} max={hoy.slice(0, 7)} onChange={(e) => setPeriodo(e.target.value)} />
        </label>
      </Encabezado>

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Cifra etiqueta="Alertas por atender" valor={pendientes.length} tono={pendientes.length ? 'critico' : 'bien'}
          nota={pendientes.length ? 'Visitas sin técnico' : 'Nada pendiente'} />
        <Cifra etiqueta="Órdenes en curso" valor={vivas} tono="aviso" nota={`${porGrupo.sin ?? 0} aún sin atender`} />
        <Cifra etiqueta="Visitas hoy" valor={visitasHoy.data?.items.length ?? '—'} tono="info"
          nota={`${visitasHoy.data?.items.filter((v) => v.estado === 'FINALIZADA').length ?? 0} terminadas`} />
        <Cifra etiqueta="Cerradas en el mes" valor={d?.ordenes_cerradas ?? '—'} tono="bien"
          nota={d?.tiempo_promedio_cierre_dias !== undefined ? `En ${d.tiempo_promedio_cierre_dias} días de promedio` : undefined} />
      </div>

      <div className="mb-6 grid items-start gap-4 xl:grid-cols-[1fr_400px]">
        <Tarjeta titulo="Mapa de órdenes" accion={<span className="text-[13px] text-muted">Vivas y cerradas en 14 días</span>}>
          <MensajeError error={puntos.error} />
          {puntos.isLoading ? <Cargando /> : <MapaOrdenes puntos={puntos.data?.puntos ?? []} />}
        </Tarjeta>
        <div className="flex flex-col gap-4">
          <Tarjeta titulo="Reprogramación urgente" accion={pendientes.length > 0 && <Insignia tono="critico" vivo>{pendientes.length} por atender</Insignia>}>
            <MensajeError error={avisos.error} />
            {avisos.isLoading ? <Cargando /> : <Alertas pendientes={pendientes} onReprogramar={setReprogramando} />}
          </Tarjeta>
          <Tarjeta titulo="Lo que el sistema resolvió solo">
            {!avisos.data?.recientes.length && <p className="text-[15px] text-muted">Cuando un técnico se ausente, sus visitas se reasignarán aquí, al instante.</p>}
            <ol className="space-y-3">
              {avisos.data?.recientes.slice(0, 5).map((a) => (
                <li key={a.creado_en + a.visita_id} className="border-l-2 pl-3" style={{ borderColor: a.tipo === 'REASIGNADA' ? 'var(--color-good)' : 'var(--color-critical)' }}>
                  <Link to={`/ordenes/${a.orden_id}`} className="block font-medium text-ink hover:underline">{a.cliente_nombre}</Link>
                  <p className="text-sm text-ink/85">{a.detalle}</p>
                  <p className="text-[13px] text-muted">{hace(a.creado_en)}</p>
                </li>
              ))}
            </ol>
          </Tarjeta>
        </div>
      </div>

      <div className="mb-6 grid gap-4 lg:grid-cols-[400px_1fr]">
        <Tarjeta titulo="Órdenes del mes">
          <MensajeError error={mes.error} />
          {d ? (
            <Anillo partes={[
              { etiqueta: 'Abiertas', valor: d.ordenes_abiertas, color: GRUPOS[0].color },
              { etiqueta: 'Cerradas', valor: d.ordenes_cerradas, color: GRUPOS[3].color },
              { etiqueta: 'Canceladas', valor: d.ordenes_canceladas, color: '#8d8a80' },
            ]} />
          ) : <Cargando />}
        </Tarjeta>
        <Tarjeta titulo="Rendimiento de técnicos" accion={<span className="text-[13px] text-muted">La reasignación automática elige con estos datos</span>}>
          <MensajeError error={rendimiento.error} />
          <div className="max-h-[340px] overflow-auto">
            <table className="w-full text-left text-[15px]">
              <thead className="sticky top-0 bg-card text-[13px] text-muted">
                <tr><th className="py-2 pr-3 font-medium">Técnico</th><th className="py-2 pr-3 font-medium">Hoy</th><th className="py-2 pr-3 font-medium">Resolución sin revisita</th><th className="py-2 pr-3 font-medium">Tiempo medio</th><th className="py-2 font-medium">Completadas</th></tr>
              </thead>
              <tbody className="divide-y divide-line">
                {filas.map((m) => (
                  <tr key={m.tecnico_id}>
                    <td className="py-2 pr-3 font-medium">{m.nombre}</td>
                    <td className="tabular py-2 pr-3">{m.carga_dia}</td>
                    <td className="py-2 pr-3">{m.tasa_resolucion === undefined ? <span className="text-muted">Sin historial</span> : <Medidor valor={m.tasa_resolucion} />}</td>
                    <td className="tabular py-2 pr-3">{m.tiempo_promedio_min === undefined ? '—' : `${Math.round(m.tiempo_promedio_min)} min`}</td>
                    <td className="tabular py-2">{m.visitas_completadas_total}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {rendimiento.isLoading && <Cargando />}
          </div>
        </Tarjeta>
      </div>

      <Tarjeta titulo="Visitas de hoy" accion={<Link className="link text-[15px]" to="/agenda">Ver la agenda</Link>}>
        <MensajeError error={visitasHoy.error} />
        {visitasHoy.isLoading && <Cargando />}
        {visitasHoy.data?.items.length === 0 && <p className="text-[15px] text-muted">No hay visitas para hoy.</p>}
        <ul className="divide-y divide-line">
          {visitasHoy.data?.items.map((v) => (
            <li key={v.visita_id} className="flex flex-wrap items-center gap-x-4 gap-y-1 py-3">
              <span className="tabular w-28 font-medium">{horaLima(v.inicio)}–{horaLima(v.fin)}</span>
              <Link className="min-w-0 flex-1 truncate hover:underline" to={`/ordenes/${v.orden_id}`}>{v.cliente_nombre}</Link>
              <span className="text-muted">{v.tecnico_nombre}</span>
              <Insignia tono={v.requiere_reprogramacion ? 'critico' : TONO_VISITA[v.estado]}>{v.requiere_reprogramacion ? 'Sin técnico' : ESTADOS_VISITA[v.estado]}</Insignia>
            </li>
          ))}
        </ul>
      </Tarjeta>

      {reprogramando && <ReprogramarVisita visita={reprogramando} onCerrar={() => setReprogramando(null)} onHecho={() => setReprogramando(null)} />}
    </>
  );
}
