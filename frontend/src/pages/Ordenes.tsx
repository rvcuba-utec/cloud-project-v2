import { useState } from 'react';
import { Link } from 'react-router';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { ordenes } from '../api/recursos';
import { ESTADOS_ORDEN, PRIORIDADES, fechaHora } from '../components/formato';
import { grupoDe } from '../components/MapaOrdenes';
import { Encabezado, Flecha, Insignia, MensajeError, Paginador, Tabla, usePaginacion } from '../components/ui';

const FILTROS: [string, string][] = [['', 'Todas'], ['ABIERTA', 'Sin atender'], ['REQUIERE_REVISITA', 'Requieren otra visita'], ['PROGRAMADA', 'Programadas'], ['EN_ATENCION', 'En atención'], ['PENDIENTE_DE_CIERRE', 'Por cerrar'], ['CERRADA', 'Cerradas'], ['CANCELADA', 'Canceladas']];

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
      <Encabezado titulo="Órdenes de trabajo" subtitulo="De la más reciente a la más antigua.">
        <Link to="/ordenes/nueva" className="btn btn--primary">Nueva orden<Flecha /></Link>
      </Encabezado>
      <div className="mb-4 flex flex-wrap gap-2" role="group" aria-label="Filtrar por estado">
        {FILTROS.map(([valor, texto]) => (
          <button key={valor} type="button" aria-pressed={estado === valor} onClick={() => { setEstado(valor); paginacion.reiniciar(); }}
            className={`h-9 rounded-full border px-3 text-[14px] font-medium transition-colors ${estado === valor ? 'border-ink bg-ink text-ground' : 'border-line-strong bg-card text-ink hover:bg-surface/60'}`}>
            {texto}
          </button>
        ))}
      </div>
      <MensajeError error={error} />
      {(
        <Tabla cargando={isLoading} columnas={['Cliente', 'Problema', 'Lugar', 'Prioridad', 'Estado', 'Registrada']} vacio={!data?.items.length}>
          {data?.items.map((o) => (
            <tr key={o.orden_id}>
              <td><Link className="font-medium text-ink hover:underline" to={`/ordenes/${o.orden_id}`}>{o.cliente_nombre}</Link></td>
              <td className="max-w-xs truncate">{o.descripcion}</td>
              <td>{o.distrito}</td>
              <td>{o.prioridad === 'ALTA' ? <Insignia tono="critico">Alta</Insignia> : PRIORIDADES[o.prioridad]}</td>
              <td><Insignia tono={o.estado === 'CANCELADA' ? 'neutro' : grupoDe(o.estado).tono}>{ESTADOS_ORDEN[o.estado]}</Insignia></td>
              <td className="whitespace-nowrap text-muted">{fechaHora(o.creada_en)}</td>
            </tr>
          ))}
        </Tabla>
      )}
      <Paginador hayAnterior={paginacion.hayAnterior} siguiente={data?.next_cursor} onAnterior={paginacion.anterior} onSiguiente={paginacion.siguiente} />
    </>
  );
}
