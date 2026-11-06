import { useCallback, useRef, useState, type ButtonHTMLAttributes, type ReactNode } from 'react';
import { ApiError } from '../api/client';

export const CAMPO =
  'mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-slate-900 ' +
  'focus:border-sky-700 focus:outline-none focus:ring-2 focus:ring-sky-200';

export function Campo({ etiqueta, children }: { etiqueta: string; children: ReactNode }) {
  return (
    <label className="block text-sm font-medium text-slate-700">
      {etiqueta}
      {children}
    </label>
  );
}

export function Boton({ variante = 'primario', className = '', ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variante?: 'primario' | 'secundario' }) {
  const estilo = variante === 'primario'
    ? 'bg-sky-800 text-white hover:bg-sky-900'
    : 'border border-slate-300 bg-white text-slate-800 hover:bg-slate-50';
  return <button type="button" {...props} className={`rounded-md px-4 py-2 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-60 ${estilo} ${className}`} />;
}

export function MensajeError({ error }: { error: unknown }) {
  if (!error) return null;
  const texto = error instanceof ApiError ? error.message : 'Ocurrió un error inesperado';
  return <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">{texto}</p>;
}

export function Tarjeta({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-lg border border-slate-200 bg-white p-4 shadow-sm ${className}`}>{children}</section>;
}

export function Encabezado({ titulo, children }: { titulo: string; children?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
      <h1 className="text-xl font-semibold text-slate-900">{titulo}</h1>
      {children}
    </div>
  );
}

/** DynamoDB no permite saltar a la página N: se guarda la pila de cursores ya visitados. */
export function usePaginacion() {
  const [pila, setPila] = useState<(string | null)[]>([null]);
  const cursor = pila[pila.length - 1];
  return {
    cursor,
    hayAnterior: pila.length > 1,
    siguiente: useCallback((c: string) => setPila((p) => [...p, c]), []),
    anterior: useCallback(() => setPila((p) => p.slice(0, -1)), []),
    reiniciar: useCallback(() => setPila([null]), []),
  };
}

export function Paginador({ hayAnterior, siguiente, onAnterior, onSiguiente }: {
  hayAnterior: boolean;
  siguiente?: string | null;
  onAnterior: () => void;
  onSiguiente: (cursor: string) => void;
}) {
  return (
    <div className="mt-3 flex justify-end gap-2">
      <Boton variante="secundario" disabled={!hayAnterior} onClick={onAnterior}>Anterior</Boton>
      <Boton variante="secundario" disabled={!siguiente} onClick={() => siguiente && onSiguiente(siguiente)}>Siguiente</Boton>
    </div>
  );
}

/** La clave se conserva entre reintentos del mismo formulario y cambia tras un envío correcto. */
export function useClaveIdempotencia() {
  const clave = useRef(crypto.randomUUID());
  return { clave: () => clave.current, renovar: () => { clave.current = crypto.randomUUID(); } };
}

export function Tabla({ columnas, children, vacio }: { columnas: string[]; children: ReactNode; vacio: boolean }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-slate-200 bg-slate-50 text-slate-600">
          <tr>{columnas.map((c) => <th key={c} scope="col" className="px-3 py-2 font-medium">{c}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-slate-100">{children}</tbody>
      </table>
      {vacio && <p className="p-4 text-center text-slate-500">No hay registros.</p>}
    </div>
  );
}
