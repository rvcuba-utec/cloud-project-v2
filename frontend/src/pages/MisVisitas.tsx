import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { agenda } from '../api/recursos';
import { ESPECIALIDADES, ESTADOS_VISITA, horaLima, hoyLima } from '../components/formato';
import { Boton, Encabezado, MensajeError, Paginador, usePaginacion } from '../components/ui';

export default function MisVisitas() {
  const consultas = useQueryClient();
  const paginacion = usePaginacion();
  const desde = hoyLima();
  const { data, error, isLoading } = useQuery({
    queryKey: ['mis-visitas', desde, paginacion.cursor],
    queryFn: () => agenda.listar({ desde, cursor: paginacion.cursor, limit: 20 }),
    placeholderData: keepPreviousData,
  });
  const iniciar = useMutation({
    mutationFn: (id: string) => agenda.iniciar(id),
    onSettled: () => consultas.invalidateQueries({ queryKey: ['mis-visitas'] }),
  });

  return (
    <>
      <Encabezado titulo="Mis visitas" />
      <MensajeError error={error} />
      <MensajeError error={iniciar.error} />
      {isLoading && <p className="text-slate-600">Cargando…</p>}
      {data?.items.length === 0 && <p className="text-slate-600">No tienes visitas próximas.</p>}
      <ul className="space-y-3">
        {data?.items.map((v) => (
          <li key={v.visita_id} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <strong className="text-slate-900">{v.fecha} · {horaLima(v.inicio)}–{horaLima(v.fin)}</strong>
              <span className="text-sm text-slate-600">{ESTADOS_VISITA[v.estado]}</span>
            </div>
            <p className="mt-1 text-slate-800">{v.cliente_nombre}</p>
            <p className="text-sm text-slate-600">{v.direccion}, {v.distrito}</p>
            <p className="mt-1 text-sm text-slate-700">{ESPECIALIDADES[v.tipo_servicio]}: {v.orden_descripcion}</p>
            {v.estado === 'PROGRAMADA' && (
              <Boton className="mt-3 w-full md:w-auto" disabled={iniciar.isPending} onClick={() => iniciar.mutate(v.visita_id)}>Iniciar visita</Boton>
            )}
          </li>
        ))}
      </ul>
      <Paginador hayAnterior={paginacion.hayAnterior} siguiente={data?.next_cursor} onAnterior={paginacion.anterior} onSiguiente={paginacion.siguiente} />
    </>
  );
}
