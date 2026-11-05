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
