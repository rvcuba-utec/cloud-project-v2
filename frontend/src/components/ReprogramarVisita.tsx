import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError } from '../api/client';
import { agenda, type Especialidad } from '../api/recursos';
import { ESPECIALIDADES, fechaLarga, horaLima, instanteLima } from './formato';
import { Boton, CAMPO, Campo, Confirmacion, Insignia, MensajeError } from './ui';

export interface VisitaAfectada {
  visita_id: string;
  cliente_nombre: string;
  tipo_servicio: Especialidad;
  fecha: string;
  inicio: string;
  fin: string;
  tecnico_nombre: string;
  motivo?: string;
}

/** Ventana de reprogramación: la sugerencia de Analítica primero, a la misma hora si se puede.
    "Asignar al mejor" elige por el coordinador; también puede escoger otro técnico u horario. */
export default function ReprogramarVisita({ visita, onCerrar, onHecho }: { visita: VisitaAfectada; onCerrar: () => void; onHecho: () => void }) {
  const consultas = useQueryClient();
  const duracion = Math.round((Date.parse(visita.fin) - Date.parse(visita.inicio)) / 60000);
  const horaOriginal = horaLima(visita.inicio);
  const [fecha, setFecha] = useState(visita.fecha);
  const detalle = useQuery({ queryKey: ['visita', visita.visita_id], queryFn: () => agenda.detalle(visita.visita_id) });
  const opciones = useQuery({
    queryKey: ['disponibilidad', fecha, duracion, visita.tipo_servicio, 'reprogramar'],
    queryFn: () => agenda.disponibilidad({ fecha, especialidad: visita.tipo_servicio, duracion_min: duracion, sugerir: true }),
  });
  const reprogramar = useMutation({
    mutationFn: ({ tecnico_id, hora }: { tecnico_id: string; hora: string }) => agenda.reprogramar(visita.visita_id, {
      tecnico_id, inicio: instanteLima(fecha, hora), fin: instanteLima(fecha, hora, duracion), version: detalle.data!.version,
    }),
    onSuccess: () => {
      ['alertas', 'visitas-dia', 'visitas-semana', 'dashboard'].forEach((k) => consultas.invalidateQueries({ queryKey: [k] }));
      onHecho();
    },
    onError: (e) => {
      if (e instanceof ApiError && e.status === 409) {
        consultas.invalidateQueries({ queryKey: ['visita', visita.visita_id] });
        consultas.invalidateQueries({ queryKey: ['disponibilidad', fecha] });
      }
    },
  });

  const lista = opciones.data?.items ?? [];
  const mejor = lista.find((t) => t.horarios.includes(horaOriginal) && fecha === visita.fecha) ?? lista[0];
  const horaMejor = mejor && (mejor.horarios.includes(horaOriginal) ? horaOriginal : mejor.horarios[0]);
  const ocupado = reprogramar.isPending || !detalle.data;

  return (
    <Confirmacion abierta titulo="Reprogramar visita" confirmar={mejor ? `Asignar a ${mejor.nombre}` : 'Sin opciones'}
      cancelar="Cerrar" ocupado={ocupado || !mejor}
      onCancelar={onCerrar} onConfirmar={() => mejor && horaMejor && reprogramar.mutate({ tecnico_id: mejor.tecnico_id, hora: horaMejor })}>
      <div className="rounded-xl bg-surface/60 p-4">
        <p className="font-medium">{visita.cliente_nombre}</p>
        <p className="text-sm text-muted">{ESPECIALIDADES[visita.tipo_servicio]} · {fechaLarga(visita.fecha)} · {horaOriginal}, {duracion} min · era de {visita.tecnico_nombre}</p>
        {visita.motivo && <p className="mt-2"><Insignia tono="critico">{visita.motivo}</Insignia></p>}
      </div>
      <Campo etiqueta="Fecha"><input className={CAMPO} type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} /></Campo>
      <MensajeError error={opciones.error ?? reprogramar.error} />
      {opciones.isLoading && <p className="text-muted">Buscando técnicos libres…</p>}
      {!opciones.isLoading && !lista.length && <p className="text-muted">Nadie está libre ese día con esa especialidad. Prueba otra fecha.</p>}
      {mejor && horaMejor && (
        <p className="text-[15px]">
          Recomendado: <strong>{mejor.nombre}</strong> a las <strong>{horaMejor}</strong>
          {mejor.justificacion && <span className="text-muted"> — {mejor.justificacion}</span>}
        </p>
      )}
      {lista.length > 0 && (
        <details className="group">
          <summary className="cursor-pointer text-[15px] font-medium text-accent">Elegir otro técnico u horario</summary>
          <ul className="mt-3 max-h-64 space-y-3 overflow-y-auto pr-1">
            {lista.map((t) => (
              <li key={t.tecnico_id}>
                <p className="text-sm font-medium">{t.nombre} {t.justificacion && <span className="font-normal text-muted">· {t.justificacion}</span>}</p>
                <div className="mt-1 flex flex-wrap gap-1">
                  {t.horarios.map((h) => (
                    <Boton key={h} variante="secundario" pequeno disabled={ocupado} onClick={() => reprogramar.mutate({ tecnico_id: t.tecnico_id, hora: h })}>{h}</Boton>
                  ))}
                </div>
              </li>
            ))}
          </ul>
        </details>
      )}
    </Confirmacion>
  );
}
