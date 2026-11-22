import { useCallback, useSyncExternalStore } from 'react';

/** Modo claro u oscuro: la elección se guarda y se aplica como data-theme en <html>; sin elección manda el sistema. */
export type Tema = 'light' | 'dark';
const CLAVE = 'trazora_tema';
const EVENTO = 'trazora:tema';

const sistemaOscuro = () => typeof matchMedia === 'function' && matchMedia('(prefers-color-scheme: dark)').matches;

export function temaActual(): Tema {
  const elegido = document.documentElement.getAttribute('data-theme');
  if (elegido === 'light' || elegido === 'dark') return elegido;
  return sistemaOscuro() ? 'dark' : 'light';
}

export function aplicarTema(tema: Tema) {
  document.documentElement.setAttribute('data-theme', tema);
  try { localStorage.setItem(CLAVE, tema); } catch { /* sin almacenamiento: el cambio dura la sesión */ }
  window.dispatchEvent(new Event(EVENTO));
}

/** Se llama una vez al arrancar, antes de pintar, para que no haya destello del otro modo. */
export function restaurarTema() {
  try {
    const guardado = localStorage.getItem(CLAVE);
    if (guardado === 'light' || guardado === 'dark') document.documentElement.setAttribute('data-theme', guardado);
  } catch { /* se queda con el sistema */ }
}

function suscribir(avisar: () => void) {
  window.addEventListener(EVENTO, avisar);
  const mq = matchMedia('(prefers-color-scheme: dark)');
  mq.addEventListener('change', avisar);
  return () => { window.removeEventListener(EVENTO, avisar); mq.removeEventListener('change', avisar); };
}

export function useTema() {
  const tema = useSyncExternalStore(suscribir, temaActual, () => 'light' as Tema);
  const alternar = useCallback(() => aplicarTema(temaActual() === 'dark' ? 'light' : 'dark'), []);
  return { tema, alternar };
}

/** Lee un token de color ya resuelto, para librerías que no entienden var(--x), como las marcas de Leaflet. */
export const colorToken = (nombre: string) => getComputedStyle(document.documentElement).getPropertyValue(nombre).trim();
