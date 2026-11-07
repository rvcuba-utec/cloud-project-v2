import { useCallback, useEffect, useRef, useState, type ButtonHTMLAttributes, type ReactNode } from 'react';
import { ApiError } from '../api/client';

/* Componentes base sobre el sistema del kit (public/assets/system.css): .btn, .card y sus tokens.
   Un botón principal por vista; el resto, secundarios. */

export const CAMPO =
  'mt-1 h-11 w-full rounded-lg border border-line-strong bg-card px-3 text-[16px] text-ink ' +
  'focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/25';
export const AREA = CAMPO.replace('h-11', 'min-h-24 py-2');

export function Campo({ etiqueta, children, ayuda }: { etiqueta: string; children: ReactNode; ayuda?: string }) {
  return (
    <label className="block text-sm font-medium text-ink">
      {etiqueta}
      {children}
      {ayuda && <span className="mt-1 block text-[13px] font-normal text-muted">{ayuda}</span>}
    </label>
  );
}

export function Boton({ variante = 'primario', pequeno = false, flecha = false, className = '', children, ...props }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variante?: 'primario' | 'secundario' | 'peligro'; pequeno?: boolean; flecha?: boolean }) {
  const estilo = variante === 'primario' ? 'btn--primary' : variante === 'peligro' ? 'btn--primary btn--peligro' : 'btn--secondary';
  return (
    <button type="button" {...props} className={`btn ${estilo} ${pequeno ? 'btn--sm' : ''} disabled:cursor-not-allowed disabled:opacity-55 ${className}`}>
      {children}
      {flecha && <Flecha />}
    </button>
  );
}

export function Flecha() {
  return (
    <svg className="m-arrow" viewBox="0 0 12 12" aria-hidden="true">
      <path className="m-arrow__stem" d="M1 6h8" /><path className="m-arrow__head" d="M4.5 2.5 8 6l-3.5 3.5" />
    </svg>
  );
}

export function MensajeError({ error }: { error: unknown }) {
  if (!error) return null;
  const texto = error instanceof ApiError ? error.message : 'Ocurrió un error inesperado';
  return (
    <p role="alert" className="flex items-start gap-2 rounded-lg border border-critical/25 bg-critical-soft px-3 py-2 text-sm text-critical">
      <span aria-hidden="true" className="mt-px font-semibold">!</span>{texto}
    </p>
  );
}

export function Tarjeta({ children, className = '', titulo, accion }: { children: ReactNode; className?: string; titulo?: string; accion?: ReactNode }) {
  return (
    <div className={`card m-nolift ${className}`}>
      {(titulo || accion) && (
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          {titulo && <h2 className="text-[17px] font-medium tracking-tight text-ink">{titulo}</h2>}
          {accion}
        </div>
      )}
      {children}
    </div>
  );
}

export function Encabezado({ titulo, subtitulo, children }: { titulo: string; subtitulo?: ReactNode; children?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="font-display text-[clamp(28px,2.4vw+14px,42px)] leading-[1.05] text-ink">{titulo}</h1>
        {subtitulo && <p className="mt-2 max-w-[62ch] text-muted">{subtitulo}</p>}
      </div>
      {children && <div className="flex flex-wrap items-center gap-3">{children}</div>}
    </div>
  );
}

export type Tono = 'critico' | 'aviso' | 'bien' | 'info' | 'neutro' | 'acento';
const TONOS: Record<Tono, string> = {
  critico: 'bg-critical-soft text-critical',
  aviso: 'bg-warning-soft text-warning',
  bien: 'bg-good-soft text-good',
  info: 'bg-info-soft text-info',
  neutro: 'bg-surface text-ink',
  acento: 'bg-accent-soft text-accent',
};
export const PUNTO: Record<Tono, string> = {
  critico: 'bg-critical', aviso: 'bg-warning', bien: 'bg-good', info: 'bg-info', neutro: 'bg-muted', acento: 'bg-accent',
};

/** El color nunca va solo: siempre con su texto. */
export function Insignia({ tono, children, vivo = false }: { tono: Tono; children: ReactNode; vivo?: boolean }) {
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-[13px] font-medium ${TONOS[tono]}`}>
      <span className="relative inline-flex size-2">
        {vivo && <span className={`pulso absolute inset-0 rounded-full ${PUNTO[tono]}`} />}
        <span className={`relative size-2 rounded-full ${PUNTO[tono]}`} />
      </span>
      {children}
    </span>
  );
}

export function Cifra({ etiqueta, valor, nota, tono }: { etiqueta: string; valor: ReactNode; nota?: ReactNode; tono?: Tono }) {
  return (
    <div className="card m-nolift !gap-1">
      <p className="flex items-center gap-2 text-[13px] font-medium text-muted">
        {tono && <span className={`size-2 rounded-full ${PUNTO[tono]}`} aria-hidden="true" />}{etiqueta}
      </p>
      <p className="font-display tabular text-[clamp(30px,2vw+16px,40px)] leading-none text-ink">{valor}</p>
      {nota && <p className="text-[13px] text-muted">{nota}</p>}
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
  if (!hayAnterior && !siguiente) return null;
  return (
    <div className="mt-4 flex justify-end gap-2">
      <Boton variante="secundario" pequeno disabled={!hayAnterior} onClick={onAnterior}>Anterior</Boton>
      <Boton variante="secundario" pequeno disabled={!siguiente} onClick={() => siguiente && onSiguiente(siguiente)}>Siguiente</Boton>
    </div>
  );
}

/** La clave se conserva entre reintentos del mismo formulario y cambia tras un envío correcto. */
export function useClaveIdempotencia() {
  const clave = useRef(crypto.randomUUID());
  return { clave: () => clave.current, renovar: () => { clave.current = crypto.randomUUID(); } };
}

export function Tabla({ columnas, children, vacio, cargando = false }: { columnas: string[]; children: ReactNode; vacio: boolean; cargando?: boolean }) {
  return (
    <div className="overflow-x-auto rounded-[20px] border border-line bg-card">
      <table className="w-full text-left text-[15px]">
        <thead className="border-b border-line text-[13px] text-muted">
          <tr>{columnas.map((c) => <th key={c} scope="col" className="px-4 py-3 font-medium">{c}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-line [&_td]:px-4 [&_td]:py-3 [&_tr]:transition-colors [&_tr:hover]:bg-surface/40">{children}</tbody>
      </table>
      {cargando && <p className="p-6 text-center text-muted">Cargando…</p>}
      {!cargando && vacio && <p className="p-6 text-center text-muted">No hay registros.</p>}
    </div>
  );
}

export function Cargando({ texto = 'Cargando…' }: { texto?: string }) {
  return <p className="flex items-center gap-2 text-muted"><span className="size-2 animate-pulse rounded-full bg-accent" />{texto}</p>;
}

/** Confirmación con el detalle de lo que pasará. Se cierra con Escape y devuelve el foco. */
export function Confirmacion({ abierta, titulo, children, confirmar, cancelar, onConfirmar, onCancelar, ocupado = false, peligro = false }: {
  abierta: boolean; titulo: string; children: ReactNode; confirmar: string; cancelar?: string;
  onConfirmar: () => void; onCancelar: () => void; ocupado?: boolean; peligro?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (abierta && !d.open) d.showModal();
    if (!abierta && d.open) d.close();
  }, [abierta]);
  return (
    <dialog ref={ref} onCancel={(e) => { e.preventDefault(); onCancelar(); }}
      className="m-auto w-[min(520px,calc(100vw-32px))] rounded-[20px] border border-line bg-card p-0 text-ink shadow-2xl backdrop:bg-ink/40">
      <div className="space-y-4 p-6">
        <h2 className="font-display text-2xl">{titulo}</h2>
        <div className="space-y-3 text-[16px] leading-relaxed">{children}</div>
        <div className="flex flex-col-reverse gap-2 pt-2 sm:flex-row sm:justify-end">
          <Boton variante="secundario" onClick={onCancelar} disabled={ocupado}>{cancelar ?? 'Volver'}</Boton>
          <Boton variante={peligro ? 'peligro' : 'primario'} onClick={onConfirmar} disabled={ocupado}>{confirmar}</Boton>
        </div>
      </div>
    </dialog>
  );
}
