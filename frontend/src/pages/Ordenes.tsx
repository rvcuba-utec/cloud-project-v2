import { useState } from 'react';
import { Link } from 'react-router';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { ordenes } from '../api/recursos';
import { ESTADOS_ORDEN, PRIORIDADES, fechaHora } from '../components/formato';
import { CAMPO, Encabezado, MensajeError, Paginador, Tabla, usePaginacion } from '../components/ui';

export default function Ordenes() {
  const [estado, setEstado] = useState('');
  const paginacion = usePaginacion();
  const { data, error, isLoading } = useQuery({
    queryKey: ['ordenes', estado, paginacion.cursor],
    queryFn: () => ordenes.listar({ estado, cursor: paginacion.cursor, limit: 25 }),
    placeholderData: keepPreviousData,
  });

  return (
    <>
      <Encabezado titulo="Órdenes de trabajo">
        <Link to="/ordenes/nueva" className="rounded-md bg-sky-800 px-4 py-2 text-sm font-medium text-white hover:bg-sky-900">Nueva orden</Link>
      </Encabezado>
      <select aria-label="Filtrar por estado" className={`${CAMPO} mb-3 max-w-xs`} value={estado}
        onChange={(e) => { setEstado(e.target.value); paginacion.reiniciar(); }}>
        <option value="">Todos los estados</option>
        {Object.entries(ESTADOS_ORDEN).map(([valor, texto]) => <option key={valor} value={valor}>{texto}</option>)}
      </select>
      <MensajeError error={error} />
      {isLoading ? <p className="text-slate-600">Cargando…</p> : (
        <Tabla columnas={['Cliente', 'Problema', 'Lugar', 'Prioridad', 'Estado', 'Registrada']} vacio={!data?.items.length}>
          {data?.items.map((o) => (
            <tr key={o.orden_id}>
              <td className="px-3 py-2"><Link className="font-medium text-sky-800 underline" to={`/ordenes/${o.orden_id}`}>{o.cliente_nombre}</Link></td>
              <td className="max-w-xs truncate px-3 py-2">{o.descripcion}</td>
              <td className="px-3 py-2">{o.distrito}</td>
              <td className="px-3 py-2">{PRIORIDADES[o.prioridad]}</td>
              <td className="px-3 py-2">{ESTADOS_ORDEN[o.estado]}</td>
              <td className="whitespace-nowrap px-3 py-2">{fechaHora(o.creada_en)}</td>
            </tr>
          ))}
        </Tabla>
      )}
      <Paginador hayAnterior={paginacion.hayAnterior} siguiente={data?.next_cursor} onAnterior={paginacion.anterior} onSiguiente={paginacion.siguiente} />
    </>
  );
}
