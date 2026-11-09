import { useEffect, useRef, useState } from 'react';
import { CAMPO } from './ui';
import { fechaDMA, fechaISO, mascaraFecha } from './fecha';

const CAMPO_FECHA = `${CAMPO.replace('mt-1 ', '')} pr-11`;

/** Fecha en DD/MM/AAAA, escrita a mano o con el calendario. Recibe y entrega AAAA-MM-DD. */
export default function InputFecha({ value, onChange, min, className = 'mt-1', required, 'aria-label': etiqueta }: {
  value: string;
  onChange: (fecha: string) => void;
  min?: string;
  className?: string;
  required?: boolean;
  'aria-label'?: string;
}) {
  const [texto, setTexto] = useState(fechaDMA(value));
  const calendario = useRef<HTMLInputElement>(null);
  useEffect(() => setTexto(fechaDMA(value)), [value]);

  const aceptar = (fecha: string) => { if (fecha && (!min || fecha >= min)) onChange(fecha); };
  const abrir = () => {
    try { calendario.current?.showPicker?.(); } catch { /* sin gesto del usuario no se abre */ }
  };

  return (
    <span className={`relative block ${className}`}>
      <input type="text" inputMode="numeric" autoComplete="off" placeholder="dd/mm/aaaa" maxLength={10}
        className={CAMPO_FECHA} required={required} aria-label={etiqueta}
        value={texto}
        onChange={(e) => { const t = mascaraFecha(e.target.value); setTexto(t); aceptar(fechaISO(t)); }}
        onBlur={() => setTexto(fechaDMA(value))} />
      <button type="button" aria-label="Abrir el calendario" onClick={abrir}
        className="absolute inset-y-0 right-0 flex w-11 items-center justify-center rounded-r-lg text-muted hover:text-ink">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <rect x="3" y="5" width="18" height="16" rx="2" /><path d="M3 10h18M8 3v4M16 3v4" />
        </svg>
      </button>
      <input ref={calendario} type="date" tabIndex={-1} aria-hidden="true" min={min} value={value}
        onChange={(e) => aceptar(e.target.value)}
        className="pointer-events-none absolute bottom-0 right-0 size-0 opacity-0" />
    </span>
  );
}
