import { useMemo, useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { tecnicos, todas, type Especialidad } from '../api/recursos';
import { ESPECIALIDADES, coincide } from '../components/formato';
import { Boton, CAMPO, Campo, Encabezado, MensajeError, Tabla, Tarjeta, useClaveIdempotencia } from '../components/ui';

const TODAS = Object.keys(ESPECIALIDADES) as Especialidad[];
const POR_PAGINA = 25;

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
  const consultas = useQueryClient();
  const [busqueda, setBusqueda] = useState('');
  const [pagina, setPagina] = useState(0);
  const [creando, setCreando] = useState(false);
  const [nombre, setNombre] = useState('');
  const [especialidades, setEspecialidades] = useState<Especialidad[]>([]);
  // Una empresa tiene decenas de técnicos: se traen todos y la búsqueda se hace aquí, sin llamadas extra al escribir.
  const { data, error, isLoading } = useQuery({
    queryKey: ['tecnicos-todos'],
    queryFn: () => todas((cursor) => tecnicos.listar({ cursor, limit: 100 })),
  });
  const crear = useMutation({
    mutationFn: () => tecnicos.crear({ nombre, especialidades }, idempotencia.clave()),
    onSuccess: (t) => { consultas.invalidateQueries({ queryKey: ['tecnicos-todos'] }); navegar(`/tecnicos/${t.tecnico_id}`); },
  });

  const filtrados = useMemo(
    () => (data ?? []).filter((t) => coincide(t.nombre, busqueda)).sort((a, b) => a.nombre.localeCompare(b.nombre, 'es')),
    [data, busqueda],
  );
  const paginas = Math.max(1, Math.ceil(filtrados.length / POR_PAGINA));
  const actual = Math.min(pagina, paginas - 1);
  const visibles = filtrados.slice(actual * POR_PAGINA, (actual + 1) * POR_PAGINA);

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
      <div className="mb-3 flex flex-wrap items-end gap-3">
        <div className="min-w-0 flex-1 sm:max-w-sm">
          <Campo etiqueta="Buscar técnico">
            <input type="search" className={CAMPO} placeholder="Nombre del técnico" autoComplete="off" value={busqueda}
              onChange={(e) => { setBusqueda(e.target.value); setPagina(0); }} />
          </Campo>
        </div>
        {data && (
          <p role="status" className="pb-3 text-[14px] text-muted">
            {busqueda.trim() ? `${filtrados.length} de ${data.length} técnicos` : `${data.length} técnicos`}
          </p>
        )}
      </div>
      {isLoading ? <p className="text-muted">Cargando…</p> : (
        <Tabla columnas={['Nombre', 'Especialidades', 'Estado']} vacio={!visibles.length}>
          {visibles.map((t) => (
            <tr key={t.tecnico_id}>
              <td className="px-3 py-2"><Link className="font-medium text-accent underline" to={`/tecnicos/${t.tecnico_id}`}>{t.nombre}</Link></td>
              <td className="px-3 py-2">{t.especialidades.map((e) => ESPECIALIDADES[e]).join(', ')}</td>
              <td className="px-3 py-2">{t.activo ? 'Activo' : 'Inactivo'}</td>
            </tr>
          ))}
        </Tabla>
      )}
      {paginas > 1 && (
        <div className="mt-4 flex items-center justify-end gap-2">
          <span className="text-[14px] text-muted">Página {actual + 1} de {paginas}</span>
          <Boton variante="secundario" pequeno disabled={actual === 0} onClick={() => setPagina(actual - 1)}>Anterior</Boton>
          <Boton variante="secundario" pequeno disabled={actual >= paginas - 1} onClick={() => setPagina(actual + 1)}>Siguiente</Boton>
        </div>
      )}
    </>
  );
}
