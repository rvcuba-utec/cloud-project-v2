import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router';
import { useMutation, useQuery } from '@tanstack/react-query';
import { clientes, ordenes, type Cliente, type Especialidad, type Prioridad } from '../api/recursos';
import { ESPECIALIDADES, PRIORIDADES } from '../components/formato';
import { Boton, CAMPO, Campo, Encabezado, MensajeError, Tarjeta, useClaveIdempotencia } from '../components/ui';

export default function NuevaOrden() {
  const navegar = useNavigate();
  const idempotencia = useClaveIdempotencia();
  const [texto, setTexto] = useState('');
  const [busqueda, setBusqueda] = useState('');
  const [cliente, setCliente] = useState<Cliente | null>(null);
  const [ubicacion, setUbicacion] = useState('');
  const [tipo, setTipo] = useState<Especialidad>('REPARACION');
  const [prioridad, setPrioridad] = useState<Prioridad>('MEDIA');
  const [descripcion, setDescripcion] = useState('');

  const resultados = useQuery({
    queryKey: ['clientes', 'buscar', busqueda],
    queryFn: () => clientes.listar({ q: busqueda, limit: 10 }),
    enabled: Boolean(busqueda) && !cliente,
  });
  const ubicaciones = useQuery({
    queryKey: ['ubicaciones', cliente?.cliente_id],
    queryFn: () => clientes.ubicaciones(cliente!.cliente_id),
    enabled: Boolean(cliente),
  });
  const crear = useMutation({
    mutationFn: () => ordenes.crear({
      cliente_id: cliente!.cliente_id, ubicacion_id: ubicacion, tipo_servicio: tipo, prioridad, descripcion,
    }, idempotencia.clave()),
    onSuccess: (o) => navegar(`/ordenes/${o.orden_id}`),
  });
  const cambio = <T,>(fijar: (v: T) => void) => (v: T) => { idempotencia.renovar(); fijar(v); };

  return (
    <>
      <p className="mb-2 text-sm"><Link className="text-sky-800 underline" to="/ordenes">← Órdenes</Link></p>
      <Encabezado titulo="Nueva orden de trabajo" />
      <Tarjeta className="max-w-2xl">
        {!cliente ? (
          <form onSubmit={(e: FormEvent) => { e.preventDefault(); setBusqueda(texto.trim()); }}>
            <Campo etiqueta="Buscar cliente por inicio del nombre">
              <div className="flex gap-2">
                <input className={CAMPO} value={texto} onChange={(e) => setTexto(e.target.value)} />
                <Boton type="submit" variante="secundario" className="mt-1">Buscar</Boton>
              </div>
            </Campo>
            <MensajeError error={resultados.error} />
            <ul className="mt-2 space-y-1">
              {resultados.data?.items.filter((c) => c.activo).map((c) => (
                <li key={c.cliente_id}>
                  <button type="button" className="w-full rounded-md border border-slate-200 px-3 py-2 text-left text-sm hover:bg-slate-50"
                    onClick={() => { setCliente(c); idempotencia.renovar(); }}>{c.nombre}</button>
                </li>
              ))}
              {busqueda && resultados.data?.items.length === 0 && <li className="text-sm text-slate-500">Sin resultados. <Link className="text-sky-800 underline" to="/clientes">Registrar cliente</Link></li>}
            </ul>
          </form>
        ) : (
          <form onSubmit={(e: FormEvent) => { e.preventDefault(); crear.mutate(); }} className="space-y-3">
            <p className="text-sm text-slate-700">
              Cliente: <strong>{cliente.nombre}</strong>{' '}
              <button type="button" className="text-sky-800 underline" onClick={() => { setCliente(null); setUbicacion(''); }}>cambiar</button>
            </p>
            <MensajeError error={ubicaciones.error} />
            <Campo etiqueta="Ubicación">
              <select className={CAMPO} required value={ubicacion} onChange={(e) => cambio(setUbicacion)(e.target.value)}>
                <option value="">Selecciona una ubicación</option>
                {ubicaciones.data?.items.map((u) => <option key={u.ubicacion_id} value={u.ubicacion_id}>{u.nombre} — {u.direccion}, {u.distrito}</option>)}
              </select>
            </Campo>
            {ubicaciones.data?.items.length === 0 && (
              <p className="text-sm text-amber-900">Este cliente no tiene ubicaciones. <Link className="underline" to={`/clientes/${cliente.cliente_id}`}>Agregar una</Link></p>
            )}
            <div className="grid gap-3 md:grid-cols-2">
              <Campo etiqueta="Tipo de servicio">
                <select className={CAMPO} value={tipo} onChange={(e) => cambio(setTipo)(e.target.value as Especialidad)}>
                  {Object.entries(ESPECIALIDADES).map(([v, t]) => <option key={v} value={v}>{t}</option>)}
                </select>
              </Campo>
              <Campo etiqueta="Prioridad">
                <select className={CAMPO} value={prioridad} onChange={(e) => cambio(setPrioridad)(e.target.value as Prioridad)}>
                  {Object.entries(PRIORIDADES).map(([v, t]) => <option key={v} value={v}>{t}</option>)}
                </select>
              </Campo>
            </div>
            <Campo etiqueta="Descripción del problema">
              <textarea className={CAMPO} required rows={3} value={descripcion} onChange={(e) => cambio(setDescripcion)(e.target.value)} />
            </Campo>
            <Boton type="submit" disabled={crear.isPending}>{crear.isPending ? 'Guardando…' : 'Crear orden'}</Boton>
            <MensajeError error={crear.error} />
          </form>
        )}
      </Tarjeta>
    </>
  );
}
