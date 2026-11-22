import { useEffect, useMemo, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { EstadoOrden, PuntoMapa } from '../api/recursos';
import { ESTADOS_ORDEN, ESPECIALIDADES } from './formato';
import { colorToken, useTema } from '../theme/tema';
import { PUNTO, type Tono } from './ui';

/** Cuatro grupos que se leen de un vistazo: lo que falta atender, lo que ya tiene visita,
    lo que se atiende ahora y lo que quedó resuelto. Rojo y verde, como en una pizarra de taller. */
export const GRUPOS: { id: string; texto: string; tono: Tono; color: string; token: string; estados: EstadoOrden[] }[] = [
  { id: 'sin', texto: 'Sin atender', tono: 'critico', color: 'var(--pin-critical)', token: '--pin-critical', estados: ['ABIERTA', 'REQUIERE_REVISITA'] },
  { id: 'prog', texto: 'Con visita', tono: 'aviso', color: 'var(--pin-warning)', token: '--pin-warning', estados: ['PROGRAMADA'] },
  { id: 'ahora', texto: 'En atención', tono: 'info', color: 'var(--pin-info)', token: '--pin-info', estados: ['EN_ATENCION'] },
  { id: 'ok', texto: 'Atendida', tono: 'bien', color: 'var(--pin-good)', token: '--pin-good', estados: ['PENDIENTE_DE_CIERRE', 'CIERRE_EN_PROCESO', 'CERRADA'] },
];
export const grupoDe = (estado: EstadoOrden) => GRUPOS.find((g) => g.estados.includes(estado)) ?? GRUPOS[0];

const LIMA: L.LatLngTuple = [-12.075, -77.02];
const TESELAS = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const CREDITO = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';

function escapar(t: string) {
  return t.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]!));
}

export default function MapaOrdenes({ puntos, alto = 460, resaltar, denso = false }: {
  puntos: PuntoMapa[]; alto?: number;
  /** orden_id que se marca en el mapa (por ejemplo, al pasar el cursor por su tarjeta en la bandeja). */
  resaltar?: string | null;
  /** Filtros más pequeños, para el mapa lateral de la Agenda. */
  denso?: boolean;
}) {
  const { tema } = useTema();
  const marcas = useRef(new Map<string, { marca: L.CircleMarker; g: (typeof GRUPOS)[number] }>());
  const caja = useRef<HTMLDivElement>(null);
  const mapa = useRef<L.Map | null>(null);
  const capa = useRef<L.LayerGroup | null>(null);
  const [ocultos, setOcultos] = useState<Set<string>>(new Set());

  const conteo = useMemo(() => {
    const c: Record<string, number> = {};
    puntos.forEach((p) => { const g = grupoDe(p.estado).id; c[g] = (c[g] ?? 0) + 1; });
    return c;
  }, [puntos]);

  useEffect(() => {
    if (!caja.current || mapa.current) return;
    mapa.current = L.map(caja.current, { zoomControl: true, scrollWheelZoom: false, attributionControl: true }).setView(LIMA, 12);
    L.tileLayer(TESELAS, { attribution: CREDITO, maxZoom: 19, className: 'teselas' }).addTo(mapa.current);
    capa.current = L.layerGroup().addTo(mapa.current);
    return () => { mapa.current?.remove(); mapa.current = null; };
  }, []);

  const estiloMarca = (g: (typeof GRUPOS)[number], activa: boolean): L.CircleMarkerOptions => ({
    radius: activa ? 12 : g.id === 'ok' ? 5 : 8,
    color: activa ? colorToken('--p-ink') : colorToken('--p-card'),
    weight: activa ? 3 : 2,
    fillColor: colorToken(g.token),
    fillOpacity: g.id === 'ok' && !activa ? 0.75 : 0.95,
  });

  useEffect(() => {
    const grupo = capa.current;
    if (!grupo || !mapa.current) return;
    grupo.clearLayers();
    marcas.current.clear();
    const visibles = puntos.filter((p) => !ocultos.has(grupoDe(p.estado).id));
    // Lo urgente se dibuja encima.
    const orden = ['ok', 'prog', 'ahora', 'sin'];
    visibles.sort((a, b) => orden.indexOf(grupoDe(a.estado).id) - orden.indexOf(grupoDe(b.estado).id));
    visibles.forEach((p) => {
      const g = grupoDe(p.estado);
      const marca = L.circleMarker([p.lat, p.lng], estiloMarca(g, false));
      marca.bindPopup(
        `<div style="font:14px/1.45 var(--font-text);min-width:200px;color:var(--p-ink)">
           <strong>${escapar(p.cliente_nombre)}</strong><br>
           <span style="color:var(--p-muted)">${escapar(p.distrito)} · ${escapar(ESPECIALIDADES[p.tipo_servicio] ?? '')}</span><br>
           <span>${escapar(ESTADOS_ORDEN[p.estado])}${p.prioridad === 'ALTA' ? ' · prioridad alta' : ''}</span><br>
           <a href="/ordenes/${encodeURIComponent(p.orden_id)}" style="color:var(--p-accent);font-weight:500">Abrir la orden →</a>
         </div>`,
      );
      marca.addTo(grupo);
      marcas.current.set(p.orden_id, { marca, g });
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [puntos, ocultos, tema]);

  useEffect(() => {
    marcas.current.forEach(({ marca, g }, id) => {
      const activa = id === resaltar;
      marca.setStyle(estiloMarca(g, activa));
      if (activa) marca.bringToFront();
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resaltar, puntos, ocultos, tema]);

  // Encuadra los puntos la primera vez que llegan; después respeta lo que el usuario movió.
  const encuadrado = useRef(false);
  useEffect(() => {
    if (encuadrado.current || !mapa.current || !puntos.length) return;
    mapa.current.fitBounds(L.latLngBounds(puntos.map((p) => [p.lat, p.lng] as L.LatLngTuple)), { padding: [32, 32], maxZoom: 14 });
    encuadrado.current = true;
  }, [puntos]);

  const alternar = (id: string) => setOcultos((o) => { const n = new Set(o); if (n.has(id)) n.delete(id); else n.add(id); return n; });

  return (
    <div>
      <div className={`flex flex-wrap ${denso ? 'mb-2 gap-1.5' : 'mb-3 gap-2'}`} role="group" aria-label="Mostrar en el mapa">
        {GRUPOS.map((g) => {
          const activo = !ocultos.has(g.id);
          return (
            <button key={g.id} type="button" aria-pressed={activo} onClick={() => alternar(g.id)}
              className={`inline-flex items-center rounded-full border font-medium transition-[border-color,color,transform] duration-150 active:scale-95 ${denso ? 'h-7 gap-1.5 px-2.5 text-[12px]' : 'h-9 gap-2 px-3 text-[14px]'} ${activo ? 'border-line-strong bg-card text-ink hover:border-ink' : 'border-line bg-transparent text-muted line-through'}`}>
              <span className={`size-2.5 rounded-full ${PUNTO[g.tono]}`} aria-hidden="true" />
              {g.texto}<span className="tabular text-muted">{conteo[g.id] ?? 0}</span>
            </button>
          );
        })}
      </div>
      <div ref={caja} style={{ height: alto }} className="isolate overflow-hidden rounded-xl border border-line bg-surface"
        role="region" aria-label="Mapa de órdenes por estado" />
    </div>
  );
}
