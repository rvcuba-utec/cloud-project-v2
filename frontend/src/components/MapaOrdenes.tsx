import { useEffect, useMemo, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { EstadoOrden, PuntoMapa } from '../api/recursos';
import { ESTADOS_ORDEN, ESPECIALIDADES } from './formato';
import { PUNTO, type Tono } from './ui';

/** Cuatro grupos que se leen de un vistazo: lo que falta atender, lo que ya tiene visita,
    lo que se atiende ahora y lo que quedó resuelto. Rojo y verde, como en una pizarra de taller. */
export const GRUPOS: { id: string; texto: string; tono: Tono; color: string; estados: EstadoOrden[] }[] = [
  { id: 'sin', texto: 'Sin atender', tono: 'critico', color: '#a8321f', estados: ['ABIERTA', 'REQUIERE_REVISITA'] },
  { id: 'prog', texto: 'Con visita', tono: 'aviso', color: '#b37a14', estados: ['PROGRAMADA'] },
  { id: 'ahora', texto: 'En atención', tono: 'info', color: '#2456b0', estados: ['EN_ATENCION'] },
  { id: 'ok', texto: 'Atendida', tono: 'bien', color: '#2f7a4a', estados: ['PENDIENTE_DE_CIERRE', 'CIERRE_EN_PROCESO', 'CERRADA'] },
];
export const grupoDe = (estado: EstadoOrden) => GRUPOS.find((g) => g.estados.includes(estado)) ?? GRUPOS[0];

const LIMA: L.LatLngTuple = [-12.075, -77.02];
const TESELAS = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const CREDITO = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';

function escapar(t: string) {
  return t.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]!));
}

export default function MapaOrdenes({ puntos, alto = 460 }: { puntos: PuntoMapa[]; alto?: number }) {
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

  useEffect(() => {
    const grupo = capa.current;
    if (!grupo || !mapa.current) return;
    grupo.clearLayers();
    const visibles = puntos.filter((p) => !ocultos.has(grupoDe(p.estado).id));
    // Lo urgente se dibuja encima.
    const orden = ['ok', 'prog', 'ahora', 'sin'];
    visibles.sort((a, b) => orden.indexOf(grupoDe(a.estado).id) - orden.indexOf(grupoDe(b.estado).id));
    visibles.forEach((p) => {
      const g = grupoDe(p.estado);
      const marca = L.circleMarker([p.lat, p.lng], {
        radius: g.id === 'ok' ? 5 : 8, color: '#f8f4ee', weight: 2, fillColor: g.color, fillOpacity: g.id === 'ok' ? 0.75 : 0.95,
      });
      marca.bindPopup(
        `<div style="font:15px/1.4 var(--font-text);min-width:200px">
           <strong>${escapar(p.cliente_nombre)}</strong><br>
           <span style="color:#5a5c53">${escapar(p.distrito)} · ${escapar(ESPECIALIDADES[p.tipo_servicio] ?? '')}</span><br>
           <span>${escapar(ESTADOS_ORDEN[p.estado])}${p.prioridad === 'ALTA' ? ' · prioridad alta' : ''}</span><br>
           <a href="/ordenes/${encodeURIComponent(p.orden_id)}" style="color:#2e5b44;font-weight:500">Abrir la orden →</a>
         </div>`,
      );
      marca.addTo(grupo);
    });
  }, [puntos, ocultos]);

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
      <div className="mb-3 flex flex-wrap gap-2" role="group" aria-label="Mostrar en el mapa">
        {GRUPOS.map((g) => {
          const activo = !ocultos.has(g.id);
          return (
            <button key={g.id} type="button" aria-pressed={activo} onClick={() => alternar(g.id)}
              className={`inline-flex h-9 items-center gap-2 rounded-full border px-3 text-[14px] font-medium transition-colors ${activo ? 'border-line-strong bg-card text-ink' : 'border-line bg-transparent text-muted line-through'}`}>
              <span className={`size-2.5 rounded-full ${PUNTO[g.tono]}`} aria-hidden="true" />
              {g.texto}<span className="tabular text-muted">{conteo[g.id] ?? 0}</span>
            </button>
          );
        })}
      </div>
      <div ref={caja} style={{ height: alto }} className="isolate overflow-hidden rounded-[20px] border border-line bg-surface"
        role="region" aria-label="Mapa de órdenes por estado" />
    </div>
  );
}
