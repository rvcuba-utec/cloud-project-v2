/** Dirección <-> punto del mapa con Nominatim (OpenStreetMap). No pasa por el backend de Trazora.
    Su política pide pocas consultas (1 por segundo como máximo), por eso solo se llama al hacer clic
    en el mapa o al pulsar «Buscar en el mapa», nunca mientras se escribe. */

const BASE = 'https://nominatim.openstreetmap.org';
/** Lima y Callao (lon_izq, lat_arriba, lon_der, lat_abajo): evita resultados de otras ciudades. */
const LIMA = '-77.20,-11.75,-76.75,-12.30';

export interface Lugar { lat: number; lng: number; direccion: string; distrito: string }

export interface RespuestaNominatim {
  lat: string;
  lon: string;
  display_name?: string;
  address?: Record<string, string>;
  error?: string;
}

/** Convierte lo que devuelve Nominatim en los campos de una ubicación de Trazora. */
export function aLugar(r: RespuestaNominatim): Lugar {
  const a = r.address ?? {};
  const calle = a.road ?? a.pedestrian ?? a.footway ?? a.neighbourhood ?? '';
  const direccion = calle ? [calle, a.house_number].filter(Boolean).join(' ') : (r.display_name ?? '').split(',')[0].trim();
  const distrito = a.suburb ?? a.city_district ?? a.town ?? a.village ?? a.city ?? '';
  return { lat: Number(Number(r.lat).toFixed(6)), lng: Number(Number(r.lon).toFixed(6)), direccion, distrito };
}

async function pedir<T>(ruta: string, params: Record<string, string>): Promise<T> {
  const url = `${BASE}${ruta}?${new URLSearchParams({ format: 'jsonv2', addressdetails: '1', 'accept-language': 'es', ...params })}`;
  let respuesta: Response;
  try {
    respuesta = await fetch(url);
  } catch {
    throw new Error('No se pudo consultar el servicio de mapas. Revisa tu conexión.');
  }
  if (!respuesta.ok) throw new Error('El servicio de mapas no respondió. Inténtalo en unos segundos.');
  return respuesta.json() as Promise<T>;
}

/** De un clic en el mapa a la dirección. null si ahí no hay una dirección conocida. */
export async function direccionDe(lat: number, lng: number): Promise<Lugar | null> {
  const r = await pedir<RespuestaNominatim>('/reverse', { lat: String(lat), lon: String(lng), zoom: '18' });
  if (r.error || !r.lat) return null;
  // Se conserva el punto donde se hizo clic; solo se toma el texto de la dirección.
  return { ...aLugar(r), lat, lng };
}

/** De una dirección escrita al punto en el mapa. null si no se encuentra en Lima.
    No se añade «Lima, Perú» al texto: el área y el país ya limitan la búsqueda, y con ese sufijo Nominatim no encuentra calles que sí existen. */
export async function puntoDe(texto: string): Promise<Lugar | null> {
  const r = await pedir<RespuestaNominatim[]>('/search', { q: texto, limit: '1', viewbox: LIMA, bounded: '1', countrycodes: 'pe' });
  return r[0] ? aLugar(r[0]) : null;
}
