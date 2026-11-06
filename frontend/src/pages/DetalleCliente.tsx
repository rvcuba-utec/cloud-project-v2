import { useState, type FormEvent } from 'react';
import { Link, useParams } from 'react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { clientes } from '../api/recursos';
import { Boton, CAMPO, Campo, Encabezado, MensajeError, Tarjeta, useClaveIdempotencia } from '../components/ui';

export default function DetalleCliente() {
  const { id = '' } = useParams();
  const consultas = useQueryClient();
  const idempotencia = useClaveIdempotencia();
  const [form, setForm] = useState({ nombre: '', direccion: '', distrito: '', referencia: '' });
  const cliente = useQuery({ queryKey: ['cliente', id], queryFn: () => clientes.detalle(id) });
  const ubicaciones = useQuery({ queryKey: ['ubicaciones', id], queryFn: () => clientes.ubicaciones(id) });

  const crear = useMutation({
    mutationFn: () => clientes.crearUbicacion(id, form, idempotencia.clave()),
    onSuccess: () => {
      idempotencia.renovar();
      setForm({ nombre: '', direccion: '', distrito: '', referencia: '' });
      consultas.invalidateQueries({ queryKey: ['ubicaciones', id] });
    },
  });
  const cambiarEstado = useMutation({
    mutationFn: (activo: boolean) => clientes.actualizar(id, { activo }),
    onSuccess: (c) => consultas.setQueryData(['cliente', id], c),
  });

  const actualizar = (campo: keyof typeof form) => (e: { target: { value: string } }) => {
    idempotencia.renovar();
    setForm((f) => ({ ...f, [campo]: e.target.value }));
  };

  if (cliente.isLoading) return <p className="text-slate-600">Cargando…</p>;
  if (cliente.error) return <MensajeError error={cliente.error} />;
  const c = cliente.data!;

  return (
    <>
      <p className="mb-2 text-sm"><Link className="text-sky-800 underline" to="/clientes">← Clientes</Link></p>
      <Encabezado titulo={c.nombre}>
        <Boton variante="secundario" disabled={cambiarEstado.isPending} onClick={() => cambiarEstado.mutate(!c.activo)}>
          {c.activo ? 'Desactivar' : 'Activar'}
        </Boton>
      </Encabezado>
      <MensajeError error={cambiarEstado.error} />
      <Tarjeta className="mb-4">
        <p className="text-sm text-slate-700">Teléfono: {c.telefono || '—'} · Correo: {c.correo || '—'} · {c.activo ? 'Activo' : 'Inactivo'}</p>
      </Tarjeta>

      <h2 className="mb-2 font-semibold text-slate-900">Ubicaciones</h2>
      <MensajeError error={ubicaciones.error} />
      <ul className="mb-4 space-y-2">
        {ubicaciones.data?.items.map((u) => (
          <li key={u.ubicacion_id} className="rounded-md border border-slate-200 bg-white p-3 text-sm">
            <strong>{u.nombre}</strong> — {u.direccion}, {u.distrito}{u.referencia ? ` (${u.referencia})` : ''}
          </li>
        ))}
        {ubicaciones.data?.items.length === 0 && <li className="text-sm text-slate-500">Aún no tiene ubicaciones.</li>}
      </ul>

      {c.activo && (
        <Tarjeta>
          <h3 className="mb-2 font-medium text-slate-900">Agregar ubicación</h3>
          <form onSubmit={(e: FormEvent) => { e.preventDefault(); crear.mutate(); }} className="grid gap-3 md:grid-cols-2">
            <Campo etiqueta="Nombre"><input className={CAMPO} required value={form.nombre} onChange={actualizar('nombre')} /></Campo>
            <Campo etiqueta="Dirección"><input className={CAMPO} required value={form.direccion} onChange={actualizar('direccion')} /></Campo>
            <Campo etiqueta="Distrito"><input className={CAMPO} required value={form.distrito} onChange={actualizar('distrito')} /></Campo>
            <Campo etiqueta="Referencia"><input className={CAMPO} value={form.referencia} onChange={actualizar('referencia')} /></Campo>
            <div className="md:col-span-2"><Boton type="submit" disabled={crear.isPending}>{crear.isPending ? 'Guardando…' : 'Agregar'}</Boton></div>
            <div className="md:col-span-2"><MensajeError error={crear.error} /></div>
          </form>
        </Tarjeta>
      )}
    </>
  );
}
