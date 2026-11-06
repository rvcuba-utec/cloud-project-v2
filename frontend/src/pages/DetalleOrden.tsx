import { Link, useParams } from 'react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError } from '../api/client';
import { ordenes, type Prioridad } from '../api/recursos';
import { ESPECIALIDADES, ESTADOS_ORDEN, PRIORIDADES, fechaHora } from '../components/formato';
import { CAMPO, Campo, Encabezado, MensajeError, Tarjeta } from '../components/ui';

export default function DetalleOrden() {
  const { id = '' } = useParams();
  const consultas = useQueryClient();
  const orden = useQuery({ queryKey: ['orden', id], queryFn: () => ordenes.detalle(id) });
  const historial = useQuery({ queryKey: ['historial', id], queryFn: () => ordenes.historial(id) });
  const prioridad = useMutation({
    mutationFn: (p: Prioridad) => ordenes.cambiarPrioridad(id, p, orden.data!.version),
    onSuccess: (o) => consultas.setQueryData(['orden', id], o),
    onError: (e) => {
      if (e instanceof ApiError && e.status === 409) consultas.invalidateQueries({ queryKey: ['orden', id] });
    },
  });

  if (orden.isLoading) return <p className="text-slate-600">Cargando…</p>;
  if (orden.error) return <MensajeError error={orden.error} />;
  const o = orden.data!;

  return (
    <>
      <p className="mb-2 text-sm"><Link className="text-sky-800 underline" to="/ordenes">← Órdenes</Link></p>
      <Encabezado titulo={o.cliente_nombre}>
        <span className="rounded-full bg-sky-100 px-3 py-1 text-sm font-medium text-sky-900">{ESTADOS_ORDEN[o.estado]}</span>
      </Encabezado>
      <div className="grid gap-4 md:grid-cols-2">
        <Tarjeta>
          <dl className="space-y-2 text-sm">
            <div><dt className="font-medium text-slate-600">Problema</dt><dd>{o.descripcion}</dd></div>
            <div><dt className="font-medium text-slate-600">Lugar</dt><dd>{o.direccion}, {o.distrito}</dd></div>
            <div><dt className="font-medium text-slate-600">Servicio</dt><dd>{ESPECIALIDADES[o.tipo_servicio]}</dd></div>
            <div><dt className="font-medium text-slate-600">Registrada</dt><dd>{fechaHora(o.creada_en)}</dd></div>
          </dl>
          <div className="mt-3 max-w-xs">
            <Campo etiqueta="Prioridad">
              <select className={CAMPO} value={o.prioridad} disabled={prioridad.isPending || ['CERRADA', 'CANCELADA'].includes(o.estado)}
                onChange={(e) => prioridad.mutate(e.target.value as Prioridad)}>
                {Object.entries(PRIORIDADES).map(([v, t]) => <option key={v} value={v}>{t}</option>)}
              </select>
            </Campo>
            <MensajeError error={prioridad.error} />
          </div>
        </Tarjeta>
        <Tarjeta>
          <h2 className="mb-2 font-semibold text-slate-900">Historial</h2>
          <MensajeError error={historial.error} />
          <ul className="space-y-2 text-sm">
            {historial.data?.items.map((h, i) => (
              <li key={i}><span className="text-slate-500">{fechaHora(h.ocurrido_en)}</span> — {h.detalle}</li>
            ))}
          </ul>
        </Tarjeta>
      </div>
    </>
  );
}
