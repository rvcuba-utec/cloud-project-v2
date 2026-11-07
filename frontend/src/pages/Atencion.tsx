import { useEffect, useState, type ChangeEvent } from 'react';
import { Link, useParams } from 'react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError } from '../api/client';
import { problemaDeArchivo, subirEvidencia } from '../api/evidencias';
import { agenda, partes, type CambiosParte, type Parte, type ResultadoParte } from '../api/recursos';
import { ESTADOS_VISITA, RESULTADOS, horaLima } from '../components/formato';
import { Boton, CAMPO, Campo, Encabezado, MensajeError, Tarjeta } from '../components/ui';
import { ResumenParte } from './DetalleParte';

const MAX_ESPERA_MS = 30_000;
const lineas = (texto: string) => texto.split('\n').map((l) => l.trim()).filter(Boolean);

/** Crea el borrador la primera vez: repetirlo devuelve el mismo, incluso con dos pestañas. */
async function abrirParte(visitaId: string, enAtencion: boolean): Promise<Parte | null> {
  try {
    return await partes.deVisita(visitaId);
  } catch (e) {
    if (!(e instanceof ApiError) || e.status !== 404) throw e;
    return enAtencion ? partes.crear(visitaId) : null;
  }
}

function FormularioParte({ parte, visitaId }: { parte: Parte; visitaId: string }) {
  const consultas = useQueryClient();
  const clave = ['parte-visita', visitaId];
  const [diagnostico, setDiagnostico] = useState(parte.diagnostico);
  const [tareas, setTareas] = useState(parte.tareas.join('\n'));
  const [materiales, setMateriales] = useState(parte.materiales.join('\n'));
  const [resultado, setResultado] = useState<ResultadoParte | ''>(parte.resultado);
  const [aviso, setAviso] = useState('');
  const [problemaFoto, setProblemaFoto] = useState('');

  const cambios = (): CambiosParte => ({ diagnostico, tareas: lineas(tareas), materiales: lineas(materiales), resultado });
  const conflicto = (e: unknown) => {
    if (e instanceof ApiError && e.status === 409) consultas.invalidateQueries({ queryKey: clave });
  };

  const guardar = useMutation({
    mutationFn: () => partes.guardar(parte.parte_id, parte.version, cambios()),
    onSuccess: (p) => { consultas.setQueryData(clave, p); setAviso('Borrador guardado.'); },
    onError: conflicto,
  });
  const finalizar = useMutation({
    // Guarda primero: se finaliza exactamente lo que se ve en pantalla.
    mutationFn: async () => {
      const guardado = await partes.guardar(parte.parte_id, parte.version, cambios());
      consultas.setQueryData(clave, guardado);
      return partes.finalizar(parte.parte_id, guardado.version);
    },
    onSuccess: (p) => {
      consultas.setQueryData(clave, p);
      consultas.invalidateQueries({ queryKey: ['visita', visitaId] });
    },
    onError: conflicto,
  });
  const subir = useMutation({
    mutationFn: (archivo: File) => subirEvidencia(parte.parte_id, archivo),
    onSettled: () => consultas.invalidateQueries({ queryKey: clave }),
  });

  const elegirFoto = (e: ChangeEvent<HTMLInputElement>) => {
    const archivo = e.target.files?.[0];
    e.target.value = ''; // Permite volver a elegir el mismo archivo.
    if (!archivo) return;
    const problema = problemaDeArchivo(archivo);
    setProblemaFoto(problema ?? '');
    if (!problema) subir.mutate(archivo);
  };

  const fotos = parte.evidencias ?? [];
  const ocupado = guardar.isPending || finalizar.isPending;

  return (
    <div className="space-y-4">
      <Tarjeta>
        <div className="space-y-3">
          <Campo etiqueta="Diagnóstico">
            <textarea className={CAMPO} rows={3} maxLength={2000} value={diagnostico} onChange={(e) => setDiagnostico(e.target.value)} />
          </Campo>
          <Campo etiqueta="Tareas realizadas (una por línea)">
            <textarea className={CAMPO} rows={3} value={tareas} onChange={(e) => setTareas(e.target.value)} />
          </Campo>
          <Campo etiqueta="Materiales usados o requeridos (uno por línea)">
            <textarea className={CAMPO} rows={2} value={materiales} onChange={(e) => setMateriales(e.target.value)} />
          </Campo>
          <Campo etiqueta="Resultado">
            <select className={CAMPO} value={resultado} onChange={(e) => setResultado(e.target.value as ResultadoParte | '')}>
              <option value="">Elige un resultado</option>
              {Object.entries(RESULTADOS).map(([v, t]) => <option key={v} value={v}>{t}</option>)}
            </select>
          </Campo>
        </div>
      </Tarjeta>

      <Tarjeta>
        <h2 className="font-semibold text-slate-900">Fotos de la atención</h2>
        <p className="mb-3 text-sm text-slate-600">JPEG o PNG, de hasta 5 MB.</p>
        <label className={`inline-block rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 ${subir.isPending ? 'opacity-60' : 'cursor-pointer hover:bg-slate-50'}`}>
          {subir.isPending ? 'Subiendo…' : 'Agregar foto'}
          <input type="file" accept="image/jpeg,image/png" className="sr-only" disabled={subir.isPending} onChange={elegirFoto} />
        </label>
        {problemaFoto && <p role="alert" className="mt-2 text-sm text-red-800">{problemaFoto}</p>}
        <div className="mt-2"><MensajeError error={subir.error} /></div>
        {fotos.length > 0 && (
          <ul className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">
            {fotos.map((f) => (
              <li key={f.evidencia_id} className="text-xs text-slate-600">
                {f.url
                  ? <img src={f.url} alt={f.nombre ?? 'Evidencia'} className="h-28 w-full rounded-md object-cover" />
                  : <div className="flex h-28 items-center justify-center rounded-md bg-slate-100 p-2 text-center">{f.estado === 'RECHAZADA' ? 'Archivo rechazado' : 'Sin subir o en revisión'}</div>}
              </li>
            ))}
          </ul>
        )}
      </Tarjeta>

      <MensajeError error={guardar.error} />
      <MensajeError error={finalizar.error} />
      {aviso && !guardar.isPending && <p role="status" className="text-sm text-slate-600">{aviso}</p>}
      <div className="flex flex-col gap-2 md:flex-row">
        <Boton variante="secundario" disabled={ocupado} onClick={() => guardar.mutate()}>{guardar.isPending ? 'Guardando…' : 'Guardar borrador'}</Boton>
        <Boton disabled={ocupado || subir.isPending}
          onClick={() => { if (window.confirm('Un parte finalizado ya no se puede modificar. ¿Finalizar?')) finalizar.mutate(); }}>
          {finalizar.isPending ? 'Finalizando…' : 'Finalizar parte'}
        </Boton>
      </div>
    </div>
  );
}

export default function Atencion() {
  const { id = '' } = useParams();
  const [limiteEspera, setLimiteEspera] = useState<number | null>(null);
  const visita = useQuery({
    queryKey: ['visita', id],
    queryFn: () => agenda.detalle(id),
    // Tras finalizar, Agenda aplica el cambio por eventos: se consulta durante 30 s como máximo.
    refetchInterval: (q) => (limiteEspera && Date.now() < limiteEspera && q.state.data?.estado === 'EN_ATENCION' ? 2000 : false),
  });
  const estadoVisita = visita.data?.estado;
  const parte = useQuery({
    queryKey: ['parte-visita', id],
    queryFn: () => abrirParte(id, estadoVisita === 'EN_ATENCION'),
    enabled: Boolean(estadoVisita),
  });
  const finalizado = parte.data?.estado === 'FINALIZADO';
  useEffect(() => {
    if (finalizado) setLimiteEspera((l) => l ?? Date.now() + MAX_ESPERA_MS);
  }, [finalizado]);

  if (visita.isLoading || (estadoVisita && parte.isLoading)) return <p className="text-slate-600">Cargando…</p>;
  if (visita.error) return <MensajeError error={visita.error} />;
  const v = visita.data!;
  const actualizando = finalizado && v.estado === 'EN_ATENCION';

  return (
    <>
      <p className="mb-2 text-sm"><Link className="text-sky-800 underline" to="/mis-visitas">← Mis visitas</Link></p>
      <Encabezado titulo={v.cliente_nombre}>
        <span className="rounded-full bg-sky-100 px-3 py-1 text-sm font-medium text-sky-900">{ESTADOS_VISITA[v.estado]}</span>
      </Encabezado>
      <p className="text-sm text-slate-700">{v.direccion}, {v.distrito}</p>
      <p className="mb-4 text-sm text-slate-600">{v.fecha} · {horaLima(v.inicio)}–{horaLima(v.fin)} · {v.orden_descripcion}</p>
      <MensajeError error={parte.error} />
      {parte.data && !finalizado && <FormularioParte key={parte.data.parte_id} parte={parte.data} visitaId={id} />}
      {parte.data && finalizado && (
        <>
          {actualizando && (
            <p role="status" className="mb-3 rounded-md bg-sky-50 p-3 text-sm text-sky-900">
              Parte finalizado. Actualizando la visita…{' '}
              {limiteEspera && Date.now() >= limiteEspera && <button type="button" className="underline" onClick={() => visita.refetch()}>Refrescar</button>}
            </p>
          )}
          <ResumenParte parte={parte.data} />
        </>
      )}
      {!parte.data && !parte.isLoading && !parte.error && <p className="text-slate-600">Esta visita no tiene parte registrado.</p>}
    </>
  );
}
