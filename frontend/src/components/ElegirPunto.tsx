import { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

const LIMA: L.LatLngTuple = [-12.075, -77.02];

/** Un clic en el mapa marca el local; así aparece en el mapa del panel. */
export default function ElegirPunto({ valor, onCambio, puntos = [] }: {
  valor: { lat: number; lng: number } | null;
  onCambio: (p: { lat: number; lng: number }) => void;
  puntos?: { lat: number; lng: number; nombre: string }[];
}) {
  const caja = useRef<HTMLDivElement>(null);
  const mapa = useRef<L.Map | null>(null);
  const marca = useRef<L.CircleMarker | null>(null);
  const cambio = useRef(onCambio);
  cambio.current = onCambio;

  useEffect(() => {
    if (!caja.current || mapa.current) return;
    const m = L.map(caja.current, { scrollWheelZoom: false }).setView(puntos[0] ? [puntos[0].lat, puntos[0].lng] : LIMA, puntos.length ? 14 : 12);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>', maxZoom: 19, className: 'teselas',
    }).addTo(m);
    puntos.forEach((p) => L.circleMarker([p.lat, p.lng], { radius: 6, color: '#f8f4ee', weight: 2, fillColor: '#5a5c53', fillOpacity: 0.9 }).bindTooltip(p.nombre).addTo(m));
    m.on('click', (e: L.LeafletMouseEvent) => cambio.current({ lat: Number(e.latlng.lat.toFixed(6)), lng: Number(e.latlng.lng.toFixed(6)) }));
    mapa.current = m;
    return () => { m.remove(); mapa.current = null; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!mapa.current) return;
    marca.current?.remove();
    if (valor) marca.current = L.circleMarker([valor.lat, valor.lng], { radius: 9, color: '#f8f4ee', weight: 3, fillColor: '#2e5b44', fillOpacity: 1 }).addTo(mapa.current);
  }, [valor]);

  return <div ref={caja} className="isolate h-72 cursor-crosshair overflow-hidden rounded-[20px] border border-line bg-surface" role="application" aria-label="Mapa: haz clic para marcar el local" />;
}
