import { partes } from './recursos';

export interface FirmaSubida {
  url: string;
  fields: Record<string, string>;
}

export function construirFormulario(firma: FirmaSubida, archivo: Blob): FormData {
  const formulario = new FormData();
  Object.entries(firma.fields).forEach(([clave, valor]) => formulario.append(clave, valor));
  formulario.append('file', archivo); // Siempre al final: S3 ignora lo que venga después.
  return formulario;
}

export async function subirAS3(firma: FirmaSubida, archivo: Blob): Promise<void> {
  // Sin Authorization ni Content-Type: el navegador define el límite del multipart.
  const respuesta = await fetch(firma.url, { method: 'POST', body: construirFormulario(firma, archivo) });
  if (respuesta.status !== 204) throw new Error('No se pudo subir el archivo');
}

export const MAX_BYTES = 5 * 1024 * 1024;
const TIPOS = ['image/jpeg', 'image/png'];
const ESPERA_MS = 2000;
const INTENTOS_ESPERA = 5;

/** Solo para dar un mensaje claro: el límite real lo aplica S3. */
export function problemaDeArchivo(archivo: { type: string; size: number }): string | null {
  if (!TIPOS.includes(archivo.type)) return 'Solo se admiten fotos JPEG o PNG.';
  if (archivo.size > MAX_BYTES) return 'La foto supera los 5 MB.';
  if (archivo.size === 0) return 'El archivo está vacío.';
  return null;
}

const esperar = (ms: number) => new Promise((resolver) => setTimeout(resolver, ms));

/** La notificación de S3 confirma la foto; si no llega en 10 s, se pide confirmar. */
export async function subirEvidencia(parteId: string, archivo: File): Promise<void> {
  const firma = await partes.solicitarEvidencia(parteId, { content_type: archivo.type, nombre: archivo.name.slice(0, 200) });
  await subirAS3(firma, archivo);
  for (let i = 0; i < INTENTOS_ESPERA; i += 1) {
    await esperar(ESPERA_MS);
    const parte = await partes.detalle(parteId);
    const evidencia = parte.evidencias?.find((e) => e.evidencia_id === firma.evidencia_id);
    if (evidencia && evidencia.estado !== 'PENDIENTE') return;
  }
  await partes.confirmarEvidencia(firma.evidencia_id);
}
