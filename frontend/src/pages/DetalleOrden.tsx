import { Link, useParams } from 'react-router';
import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError } from '../api/client';
import { agenda, ordenes, partes, type Prioridad } from '../api/recursos';
import { ESPECIALIDADES, ESTADOS_ORDEN, ESTADOS_VISITA, PRIORIDADES, RESULTADOS, fechaHora, horaLima } from '../components/formato';
import ProgramarVisita from '../components/ProgramarVisita';
import { Boton, CAMPO, Campo, Cargando, Confirmacion, Encabezado, Insignia, MensajeError, Tarjeta, type Tono } from '../components/ui';
import { grupoDe } from '../components/MapaOrdenes';

export default function DetalleOrden() {
  const { id = '' } = useParams();
  const consultas = useQueryClient();
  const orden = useQuery({
    queryKey: ['orden', id],
    queryFn: () => ordenes.detalle(id),
    // Las visitas cambian la orden por eventos, unos segundos después.
    refetchInterval: (q) => (['CERRADA', 'CANCELADA'].includes(q.state.data?.estado ?? '') ? false : 10_000),
  });
  const historial = useQuery({ queryKey: ['historial', id], queryFn: () => ordenes.historial(id) });
  const visitas = useQuery({ queryKey: ['visitas-orden', id], queryFn: () => agenda.listar({ orden_id: id, limit: 50 }) });
  const partesOrden = useQuery({ queryKey: ['partes-orden', id], queryFn: () => partes.deOrden(id) });
  const [programando, setProgramando] = useState(false);
  const [confirmarCancelacion, setConfirmarCancelacion] = useState(false);
  const refrescar = () => {
    consultas.invalidateQueries({ queryKey: ['orden', id] });
    consultas.invalidateQueries({ queryKey: ['historial', id] });
    consultas.invalidateQueries({ queryKey: ['visitas-orden', id] });
    consultas.invalidateQueries({ queryKey: ['partes-orden', id] });
  };
  const versionOrden = orden.data?.version;
  useEffect(() => {
    if (versionOrden === undefined) return;
    consultas.invalidateQueries({ queryKey: ['historial', id] });
    consultas.invalidateQueries({ queryKey: ['visitas-orden', id] });
    consultas.invalidateQueries({ queryKey: ['partes-orden', id] });
  }, [versionOrden, consultas, id]);
  const cerrar = useMutation({ mutationFn: () => ordenes.cerrar(id), onSettled: refrescar });
  const cancelar = useMutation({ mutationFn: () => ordenes.cancelar(id), onSuccess: () => setConfirmarCancelacion(false), onSettled: refrescar });
  const prioridad = useMutation({
    mutationFn: (p: Prioridad) => ordenes.cambiarPrioridad(id, p, orden.data!.version),
    onSuccess: (o) => consultas.setQueryData(['orden', id], o),
    onError: (e) => {
      if (e instanceof ApiError && e.status === 409) consultas.invalidateQueries({ queryKey: ['orden', id] });
    },
  });

  if (orden.isLoading) return <Cargando />;
  if (orden.error) return <MensajeError error={orden.error} />;
  const o = orden.data!;
  const terminada = ['CERRADA', 'CANCELADA'].includes(o.estado);
  const lista = visitas.data?.items ?? [];
  const programadas = lista.filter((v) => v.estado === 'PROGRAMADA');
  const enAtencion = lista.filter((v) => v.estado === 'EN_ATENCION');
  const tono: Tono = grupoDe(o.estado).tono;

  return (
    <>
      <p className="mb-2 text-sm"><Link className="text-accent underline" to="/ordenes">← Órdenes</Link></p>
      <Encabezado titulo={o.cliente_nombre}>
        <div className="flex flex-wrap items-center gap-2">
          <Insignia tono={tono} vivo={o.estado === 'EN_ATENCION'}>{ESTADOS_ORDEN[o.estado]}</Insignia>
          {['PENDIENTE_DE_CIERRE', 'CIERRE_EN_PROCESO'].includes(o.estado) && (
            <Boton disabled={cerrar.isPending} onClick={() => cerrar.mutate()}>{cerrar.isPending ? 'Cerrando…' : 'Cerrar orden'}</Boton>
          )}
          {!terminada && (
            <Boton variante="secundario" disabled={cancelar.isPending}
              onClick={() => setConfirmarCancelacion(true)}>Cancelar orden</Boton>
          )}
        </div>
      </Encabezado>
      <MensajeError error={cerrar.error} />
      <MensajeError error={cancelar.error} />
      <div className="grid gap-4 md:grid-cols-2">
        <Tarjeta>
          <dl className="space-y-2 text-sm">
            <div><dt className="font-medium text-muted">Problema</dt><dd>{o.descripcion}</dd></div>
            <div><dt className="font-medium text-muted">Lugar</dt><dd>{o.direccion}, {o.distrito}</dd></div>
            <div><dt className="font-medium text-muted">Servicio</dt><dd>{ESPECIALIDADES[o.tipo_servicio]}</dd></div>
            <div><dt className="font-medium text-muted">Registrada</dt><dd>{fechaHora(o.creada_en)}</dd></div>
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
          <h2 className="mb-2 font-semibold text-ink">Historial</h2>
          <MensajeError error={historial.error} />
          <ul className="space-y-2 text-sm">
            {historial.data?.items.map((h, i) => (
              <li key={i}><span className="text-muted">{fechaHora(h.ocurrido_en)}</span> — {h.detalle}</li>
            ))}
          </ul>
        </Tarjeta>
      </div>

      <div className="mb-2 mt-6 flex items-center justify-between">
        <h2 className="font-semibold text-ink">Visitas</h2>
        {!terminada && !programando && <Boton onClick={() => setProgramando(true)}>Programar visita</Boton>}
      </div>
      {programando && (
        <ProgramarVisita orden={o} onCancelar={() => setProgramando(false)} onProgramada={() => { setProgramando(false); refrescar(); }} />
      )}
      <MensajeError error={visitas.error} />
      <ul className="space-y-2">
        {visitas.data?.items.map((v) => (
          <li key={v.visita_id} className="rounded-md border border-line bg-card p-3 text-sm">
            <strong>Visita {v.numero_visita_orden}</strong> · {v.fecha} {horaLima(v.inicio)}–{horaLima(v.fin)} · {v.tecnico_nombre} · {ESTADOS_VISITA[v.estado]}
          </li>
        ))}
        {visitas.data?.items.length === 0 && <li className="text-sm text-muted">Aún no hay visitas.</li>}
      </ul>

      <h2 className="mb-2 mt-6 font-semibold text-ink">Partes de trabajo</h2>
      <MensajeError error={partesOrden.error} />
      <ul className="space-y-2">
        {partesOrden.data?.items.map((p) => (
          <li key={p.parte_id} className="rounded-md border border-line bg-card p-3 text-sm">
            <Link className="font-medium text-accent underline" to={`/partes/${p.parte_id}`}>Visita {p.numero_visita_orden}</Link>
            {' · '}{p.tecnico_nombre} · {p.estado === 'FINALIZADO' && p.resultado ? RESULTADOS[p.resultado] : 'En borrador'}
          </li>
        ))}
        {partesOrden.data?.items.length === 0 && <li className="text-sm text-muted">Aún no hay partes.</li>}
      </ul>
      <Confirmacion abierta={confirmarCancelacion} peligro titulo="Cancelar la orden" confirmar={programadas.length ? `Cancelar orden y ${programadas.length} ${programadas.length === 1 ? 'visita' : 'visitas'}` : 'Cancelar orden'}
        cancelar="Volver" ocupado={cancelar.isPending || enAtencion.length > 0} onCancelar={() => setConfirmarCancelacion(false)} onConfirmar={() => cancelar.mutate()}>
        <p><strong>{o.cliente_nombre}</strong>: {o.descripcion}</p>
        {enAtencion.length > 0 ? (
          <p className="rounded-xl bg-critical-soft p-3 text-critical">Hay una visita en atención en este momento. Espera a que el técnico termine su parte para cancelar la orden.</p>
        ) : programadas.length > 0 ? (
          <>
            <p>Se cancelarán también <strong>{programadas.length === 1 ? 'esta visita programada' : `estas ${programadas.length} visitas programadas`}</strong>, y sus horarios quedarán libres:</p>
            <ul className="space-y-1 rounded-xl bg-surface/60 p-3 text-[15px]">
              {programadas.map((v) => <li key={v.visita_id}>Visita {v.numero_visita_orden}: {v.fecha}, {horaLima(v.inicio)} con {v.tecnico_nombre}</li>)}
            </ul>
          </>
        ) : <p>La orden no tiene visitas programadas.</p>}
        <p className="text-muted">No se puede deshacer.</p>
        <MensajeError error={cancelar.error} />
      </Confirmacion>
    </>
  );
}
