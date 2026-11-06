import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router';
import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query';
import { clientes } from '../api/recursos';
import { Boton, CAMPO, Campo, Encabezado, MensajeError, Paginador, Tabla, Tarjeta, useClaveIdempotencia, usePaginacion } from '../components/ui';

function FormularioCliente({ onCancelar }: { onCancelar: () => void }) {
  const navegar = useNavigate();
  const idempotencia = useClaveIdempotencia();
  const [nombre, setNombre] = useState('');
  const [telefono, setTelefono] = useState('');
  const [correo, setCorreo] = useState('');
  const crear = useMutation({
    mutationFn: () => clientes.crear({ nombre, telefono, correo }, idempotencia.clave()),
    onSuccess: (c) => navegar(`/clientes/${c.cliente_id}`),
  });

  return (
    <Tarjeta className="mb-4">
      <form onSubmit={(e: FormEvent) => { e.preventDefault(); crear.mutate(); }} className="grid gap-3 md:grid-cols-3">
        <Campo etiqueta="Nombre"><input className={CAMPO} required value={nombre} onChange={(e) => { setNombre(e.target.value); idempotencia.renovar(); }} /></Campo>
        <Campo etiqueta="Teléfono"><input className={CAMPO} value={telefono} onChange={(e) => { setTelefono(e.target.value); idempotencia.renovar(); }} /></Campo>
        <Campo etiqueta="Correo"><input className={CAMPO} type="email" value={correo} onChange={(e) => { setCorreo(e.target.value); idempotencia.renovar(); }} /></Campo>
        <div className="flex gap-2 md:col-span-3">
          <Boton type="submit" disabled={crear.isPending}>{crear.isPending ? 'Guardando…' : 'Guardar'}</Boton>
          <Boton variante="secundario" onClick={onCancelar}>Cancelar</Boton>
        </div>
        <div className="md:col-span-3"><MensajeError error={crear.error} /></div>
      </form>
    </Tarjeta>
  );
}

export default function Clientes() {
  const [texto, setTexto] = useState('');
  const [busqueda, setBusqueda] = useState('');
  const [creando, setCreando] = useState(false);
  const paginacion = usePaginacion();
  const { data, error, isLoading } = useQuery({
    queryKey: ['clientes', busqueda, paginacion.cursor],
    queryFn: () => clientes.listar({ q: busqueda, cursor: paginacion.cursor, limit: 25 }),
    placeholderData: keepPreviousData,
  });

  function buscar(e: FormEvent) {
    e.preventDefault();
    paginacion.reiniciar();
    setBusqueda(texto.trim());
  }

  return (
    <>
      <Encabezado titulo="Clientes">
        {!creando && <Boton onClick={() => setCreando(true)}>Nuevo cliente</Boton>}
      </Encabezado>
      {creando && <FormularioCliente onCancelar={() => setCreando(false)} />}
      <form onSubmit={buscar} className="mb-3 flex gap-2">
        <input aria-label="Buscar por nombre" placeholder="Buscar por inicio del nombre" className={`${CAMPO} mt-0`} value={texto} onChange={(e) => setTexto(e.target.value)} />
        <Boton type="submit" variante="secundario">Buscar</Boton>
      </form>
      <MensajeError error={error} />
      {isLoading ? <p className="text-slate-600">Cargando…</p> : (
        <Tabla columnas={['Nombre', 'Teléfono', 'Correo', 'Estado']} vacio={!data?.items.length}>
          {data?.items.map((c) => (
            <tr key={c.cliente_id}>
              <td className="px-3 py-2"><Link className="font-medium text-sky-800 underline" to={`/clientes/${c.cliente_id}`}>{c.nombre}</Link></td>
              <td className="px-3 py-2">{c.telefono}</td>
              <td className="px-3 py-2">{c.correo}</td>
              <td className="px-3 py-2">{c.activo ? 'Activo' : 'Inactivo'}</td>
            </tr>
          ))}
        </Tabla>
      )}
      <Paginador hayAnterior={paginacion.hayAnterior} siguiente={data?.next_cursor} onAnterior={paginacion.anterior} onSiguiente={paginacion.siguiente} />
    </>
  );
}
