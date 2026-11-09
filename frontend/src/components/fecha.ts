/* Fechas escritas como DD/MM/AAAA, igual en cualquier navegador.
   El selector nativo (<input type="date">) usa el idioma del navegador y en inglés muestra MM/DD/AAAA. */

/** De AAAA-MM-DD a DD/MM/AAAA. */
export function fechaDMA(fecha: string): string {
  const [a, m, d] = fecha.split('-');
  return a && m && d ? `${d}/${m}/${a}` : '';
}

/** De DD/MM/AAAA a AAAA-MM-DD. Devuelve '' si no es una fecha real (31/02/2026, por ejemplo). */
export function fechaISO(texto: string): string {
  const partes = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(texto);
  if (!partes) return '';
  const [, d, m, a] = partes;
  const iso = `${a}-${m}-${d}`;
  const control = new Date(`${iso}T12:00:00Z`);
  return !Number.isNaN(control.getTime()) && control.toISOString().slice(0, 10) === iso ? iso : '';
}

/** Pone las barras mientras se escribe: 10112026 pasa a 10/11/2026. */
export function mascaraFecha(texto: string): string {
  const n = texto.replace(/\D/g, '').slice(0, 8);
  return [n.slice(0, 2), n.slice(2, 4), n.slice(4)].filter(Boolean).join('/');
}
