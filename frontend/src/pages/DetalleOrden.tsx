import { Link, useParams } from 'react-router';
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError } from '../api/client';
import { agenda, ordenes, type Prioridad } from '../api/recursos';
import { ESPECIALIDADES, ESTADOS_ORDEN, ESTADOS_VISITA, PRIORIDADES, fechaHora, horaLima } from '../components/formato';
import ProgramarVisita from '../components/ProgramarVisita';
import { Boton, CAMPO, Campo, Encabezado, MensajeError, Tarjeta } from '../components/ui';

export default function DetalleOrden() {
  const { id = '' } = useParams();
  const consultas = useQueryClient();
  const orden = useQuery({ queryKey: ['orden', id], queryFn: () => ordenes.detalle(id) });
  const historial = useQuery({ queryKey: ['historial', id], queryFn: () => ordenes.historial(id) });
  const visitas = useQuery({ queryKey: ['visitas-orden', id], queryFn: () => agenda.listar({ orden_id: id, limit: 50 }) });
  const [programando, setProgramando] = useState(false);
  const refrescar = () => {
    consultas.invalidateQueries({ queryKey: ['orden', id] });
    consultas.invalidateQueries({ queryKey: ['historial', id] });
    consultas.invalidateQueries({ queryKey: ['visitas-orden', id] });
  };
  const cerrar = useMutation({ mutationFn: () => ordenes.cerrar(id), onSettled: refrescar });
  const cancelar = useMutation({ mutationFn: () => ordenes.cancelar(id), onSettled: refrescar });
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
  const terminada = ['CERRADA', 'CANCELADA'].includes(o.estado);

  return (
    <>
      <p className="mb-2 text-sm"><Link className="text-sky-800 underline" to="/ordenes">← Órdenes</Link></p>
      <Encabezado titulo={o.cliente_nombre}>
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-sky-100 px-3 py-1 text-sm font-medium text-sky-900">{ESTADOS_ORDEN[o.estado]}</span>
          {['PENDIENTE_DE_CIERRE', 'CIERRE_EN_PROCESO'].includes(o.estado) && (
            <Boton disabled={cerrar.isPending} onClick={() => cerrar.mutate()}>{cerrar.isPending ? 'Cerrando…' : 'Cerrar orden'}</Boton>
          )}
          {!terminada && (
            <Boton variante="secundario" disabled={cancelar.isPending}
              onClick={() => { if (window.confirm('¿Cancelar esta orden?')) cancelar.mutate(); }}>Cancelar orden</Boton>
          )}
        </div>
      </Encabezado>
      <MensajeError error={cerrar.error} />
      <MensajeError error={cancelar.error} />
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

      <div className="mb-2 mt-6 flex items-center justify-between">
        <h2 className="font-semibold text-slate-900">Visitas</h2>
        {!terminada && !programando && <Boton onClick={() => setProgramando(true)}>Programar visita</Boton>}
      </div>
      {programando && (
        <ProgramarVisita orden={o} onCancelar={() => setProgramando(false)} onProgramada={() => { setProgramando(false); refrescar(); }} />
      )}
      <MensajeError error={visitas.error} />
      <ul className="space-y-2">
        {visitas.data?.items.map((v) => (
          <li key={v.visita_id} className="rounded-md border border-slate-200 bg-white p-3 text-sm">
            <strong>Visita {v.numero_visita_orden}</strong> · {v.fecha} {horaLima(v.inicio)}–{horaLima(v.fin)} · {v.tecnico_nombre} · {ESTADOS_VISITA[v.estado]}
          </li>
        ))}
        {visitas.data?.items.length === 0 && <li className="text-sm text-slate-500">Aún no hay visitas.</li>}
      </ul>
    </>
  );
}
