import { useState } from 'react';
import { Link } from 'react-router';
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { agenda, type Visita } from '../api/recursos';
import { ESTADOS_VISITA, horaLima, hoyLima, instanteLima } from '../components/formato';
import { Boton, CAMPO, Campo, Encabezado, MensajeError, Paginador, Tabla, usePaginacion } from '../components/ui';

function Reprogramar({ visita, onListo, onCerrar }: { visita: Visita; onListo: () => void; onCerrar: () => void }) {
  const [fecha, setFecha] = useState(visita.fecha);
  const [hora, setHora] = useState(horaLima(visita.inicio));
  const duracion = (new Date(visita.fin).getTime() - new Date(visita.inicio).getTime()) / 60000;
  const guardar = useMutation({
    mutationFn: () => agenda.reprogramar(visita.visita_id, {
      inicio: instanteLima(fecha, hora), fin: instanteLima(fecha, hora, duracion), version: visita.version,
    }),
    onSuccess: onListo,
  });
  return (
    <div className="space-y-2 p-3">
      <div className="flex flex-wrap items-end gap-2">
        <Campo etiqueta="Nueva fecha"><input className={CAMPO} type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} /></Campo>
        <Campo etiqueta="Nueva hora"><input className={CAMPO} type="time" step={1800} value={hora} onChange={(e) => setHora(e.target.value)} /></Campo>
        <Boton disabled={guardar.isPending} onClick={() => guardar.mutate()}>Guardar</Boton>
        <Boton variante="secundario" onClick={onCerrar}>Cerrar</Boton>
      </div>
      <MensajeError error={guardar.error} />
    </div>
  );
}

export default function Agenda() {
  const consultas = useQueryClient();
  const [fecha, setFecha] = useState(hoyLima());
  const [editando, setEditando] = useState<string | null>(null);
  const paginacion = usePaginacion();
  const { data, error, isLoading } = useQuery({
    queryKey: ['agenda', fecha, paginacion.cursor],
    queryFn: () => agenda.listar({ fecha, cursor: paginacion.cursor, limit: 25 }),
    placeholderData: keepPreviousData,
  });
  const refrescar = () => consultas.invalidateQueries({ queryKey: ['agenda'] });
  const cancelar = useMutation({ mutationFn: (id: string) => agenda.cancelar(id), onSettled: refrescar });

  return (
    <>
      <Encabezado titulo="Agenda" />
      <div className="mb-3 max-w-xs">
        <Campo etiqueta="Fecha">
          <input className={CAMPO} type="date" value={fecha} onChange={(e) => { setFecha(e.target.value); paginacion.reiniciar(); }} />
        </Campo>
      </div>
      <MensajeError error={error} />
      <MensajeError error={cancelar.error} />
      {isLoading ? <p className="text-slate-600">Cargando…</p> : (
        <Tabla columnas={['Horario', 'Técnico', 'Cliente', 'Lugar', 'Estado', 'Acciones']} vacio={!data?.items.length}>
          {data?.items.map((v) => (
            <tr key={v.visita_id}>
              {editando === v.visita_id ? (
                <td colSpan={6}><Reprogramar visita={v} onCerrar={() => setEditando(null)} onListo={() => { setEditando(null); refrescar(); }} /></td>
              ) : (
                <>
                  <td className="whitespace-nowrap px-3 py-2">{horaLima(v.inicio)}–{horaLima(v.fin)}</td>
                  <td className="px-3 py-2">{v.tecnico_nombre}</td>
                  <td className="px-3 py-2"><Link className="text-sky-800 underline" to={`/ordenes/${v.orden_id}`}>{v.cliente_nombre}</Link></td>
                  <td className="px-3 py-2">{v.distrito}</td>
                  <td className="px-3 py-2">{ESTADOS_VISITA[v.estado]}</td>
                  <td className="whitespace-nowrap px-3 py-2">
                    {v.estado === 'PROGRAMADA' && (
                      <>
                        <button type="button" className="mr-3 text-sky-800 underline" onClick={() => setEditando(v.visita_id)}>Reprogramar</button>
                        <button type="button" className="text-red-800 underline" disabled={cancelar.isPending}
                          onClick={() => { if (window.confirm('¿Cancelar esta visita?')) cancelar.mutate(v.visita_id); }}>Cancelar</button>
                      </>
                    )}
                  </td>
                </>
              )}
            </tr>
          ))}
        </Tabla>
      )}
      <Paginador hayAnterior={paginacion.hayAnterior} siguiente={data?.next_cursor} onAnterior={paginacion.anterior} onSiguiente={paginacion.siguiente} />
    </>
  );
}
