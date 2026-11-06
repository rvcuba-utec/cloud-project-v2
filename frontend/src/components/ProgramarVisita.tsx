import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError } from '../api/client';
import { agenda, type Orden } from '../api/recursos';
import { hoyLima, instanteLima } from './formato';
import { Boton, CAMPO, Campo, MensajeError, Tarjeta, useClaveIdempotencia } from './ui';

const DURACIONES = [30, 60, 90, 120, 180, 240];

export default function ProgramarVisita({ orden, onProgramada, onCancelar }: {
  orden: Orden;
  onProgramada: () => void;
  onCancelar: () => void;
}) {
  const consultas = useQueryClient();
  const idempotencia = useClaveIdempotencia();
  const [fecha, setFecha] = useState(hoyLima());
  const [duracion, setDuracion] = useState(60);
  const clave = ['disponibilidad', fecha, duracion, orden.tipo_servicio];
  const opciones = useQuery({
    queryKey: clave,
    queryFn: () => agenda.disponibilidad({ fecha, especialidad: orden.tipo_servicio, duracion_min: duracion, sugerir: true }),
    enabled: Boolean(fecha),
  });
  const programar = useMutation({
    mutationFn: ({ tecnico_id, hora }: { tecnico_id: string; hora: string }) => {
      idempotencia.renovar(); // Cada elección es un intento distinto: otro técnico u horario.
      return agenda.programar({
        orden_id: orden.orden_id, tecnico_id,
        inicio: instanteLima(fecha, hora), fin: instanteLima(fecha, hora, duracion),
      }, idempotencia.clave());
    },
    onSuccess: onProgramada,
    onError: (e) => {
      // El horario pudo ocuparse mientras se decidía: se muestra lo que sigue libre.
      if (e instanceof ApiError && e.status === 409) consultas.invalidateQueries({ queryKey: clave });
    },
  });

  return (
    <Tarjeta className="mb-3">
      <div className="mb-3 grid gap-3 md:grid-cols-2">
        <Campo etiqueta="Fecha"><input className={CAMPO} type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} /></Campo>
        <Campo etiqueta="Duración">
          <select className={CAMPO} value={duracion} onChange={(e) => setDuracion(Number(e.target.value))}>
            {DURACIONES.map((d) => <option key={d} value={d}>{d} minutos</option>)}
          </select>
        </Campo>
      </div>
      <MensajeError error={programar.error} />
      <MensajeError error={opciones.error} />
      {opciones.isLoading && <p className="text-sm text-slate-600">Buscando técnicos…</p>}
      {opciones.data?.items.length === 0 && <p className="text-sm text-slate-600">No hay técnicos disponibles ese día.</p>}
      <ul className="space-y-3">
        {opciones.data?.items.map((t, i) => (
          <li key={t.tecnico_id} className={`rounded-md border p-3 ${i === 0 && t.justificacion ? 'border-sky-400 bg-sky-50' : 'border-slate-200'}`}>
            <p className="text-sm font-medium text-slate-900">
              {t.nombre}{i === 0 && t.justificacion && <span className="ml-2 text-sky-800">Sugerido</span>}
            </p>
            {t.justificacion && <p className="text-sm text-slate-600">{t.justificacion}</p>}
            <div className="mt-2 flex flex-wrap gap-1">
              {t.horarios.map((h) => (
                <button key={h} type="button" disabled={programar.isPending}
                  onClick={() => programar.mutate({ tecnico_id: t.tecnico_id, hora: h })}
                  className="rounded border border-slate-300 bg-white px-2 py-1 text-xs hover:bg-sky-100 disabled:opacity-50">{h}</button>
              ))}
            </div>
          </li>
        ))}
      </ul>
      <Boton variante="secundario" className="mt-3" onClick={onCancelar}>Cerrar</Boton>
    </Tarjeta>
  );
}
