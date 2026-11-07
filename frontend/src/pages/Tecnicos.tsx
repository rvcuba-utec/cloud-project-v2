import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router';
import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query';
import { tecnicos, type Especialidad } from '../api/recursos';
import { ESPECIALIDADES } from '../components/formato';
import { Boton, CAMPO, Campo, Encabezado, MensajeError, Paginador, Tabla, Tarjeta, useClaveIdempotencia, usePaginacion } from '../components/ui';

const TODAS = Object.keys(ESPECIALIDADES) as Especialidad[];

export function SelectorEspecialidades({ valor, onCambio }: { valor: Especialidad[]; onCambio: (v: Especialidad[]) => void }) {
  return (
    <fieldset className="text-sm text-ink">
      <legend className="font-medium">Especialidades</legend>
      <div className="mt-1 flex flex-wrap gap-3">
        {TODAS.map((e) => (
          <label key={e} className="flex items-center gap-1">
            <input type="checkbox" checked={valor.includes(e)}
              onChange={() => onCambio(valor.includes(e) ? valor.filter((x) => x !== e) : [...valor, e])} />
            {ESPECIALIDADES[e]}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

export default function Tecnicos() {
  const navegar = useNavigate();
  const idempotencia = useClaveIdempotencia();
  const paginacion = usePaginacion();
  const [creando, setCreando] = useState(false);
  const [nombre, setNombre] = useState('');
  const [especialidades, setEspecialidades] = useState<Especialidad[]>([]);
  const { data, error, isLoading } = useQuery({
    queryKey: ['tecnicos', paginacion.cursor],
    queryFn: () => tecnicos.listar({ cursor: paginacion.cursor, limit: 25 }),
    placeholderData: keepPreviousData,
  });
  const crear = useMutation({
    mutationFn: () => tecnicos.crear({ nombre, especialidades }, idempotencia.clave()),
    onSuccess: (t) => navegar(`/tecnicos/${t.tecnico_id}`),
  });

  return (
    <>
      <Encabezado titulo="Técnicos">
        {!creando && <Boton onClick={() => setCreando(true)}>Nuevo técnico</Boton>}
      </Encabezado>
      {creando && (
        <Tarjeta className="mb-4">
          <form onSubmit={(e: FormEvent) => { e.preventDefault(); crear.mutate(); }} className="space-y-3">
            <Campo etiqueta="Nombre"><input className={CAMPO} required value={nombre} onChange={(e) => { setNombre(e.target.value); idempotencia.renovar(); }} /></Campo>
            <SelectorEspecialidades valor={especialidades} onCambio={(v) => { setEspecialidades(v); idempotencia.renovar(); }} />
            <div className="flex gap-2">
              <Boton type="submit" disabled={crear.isPending || !especialidades.length}>{crear.isPending ? 'Guardando…' : 'Guardar'}</Boton>
              <Boton variante="secundario" onClick={() => setCreando(false)}>Cancelar</Boton>
            </div>
            <MensajeError error={crear.error} />
          </form>
        </Tarjeta>
      )}
      <MensajeError error={error} />
      {isLoading ? <p className="text-muted">Cargando…</p> : (
        <Tabla columnas={['Nombre', 'Especialidades', 'Estado']} vacio={!data?.items.length}>
          {data?.items.map((t) => (
            <tr key={t.tecnico_id}>
              <td className="px-3 py-2"><Link className="font-medium text-accent underline" to={`/tecnicos/${t.tecnico_id}`}>{t.nombre}</Link></td>
              <td className="px-3 py-2">{t.especialidades.map((e) => ESPECIALIDADES[e]).join(', ')}</td>
              <td className="px-3 py-2">{t.activo ? 'Activo' : 'Inactivo'}</td>
            </tr>
          ))}
        </Tabla>
      )}
      <Paginador hayAnterior={paginacion.hayAnterior} siguiente={data?.next_cursor} onAnterior={paginacion.anterior} onSiguiente={paginacion.siguiente} />
    </>
  );
}
