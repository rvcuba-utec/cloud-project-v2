import { Link, useParams } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { partes, type Parte } from '../api/recursos';
import { useAuth } from '../auth/AuthContext';
import { RESULTADOS, fechaHora } from '../components/formato';
import { Encabezado, MensajeError, Tarjeta } from '../components/ui';

export function ResumenParte({ parte }: { parte: Parte }) {
  const fotos = parte.evidencias?.filter((e) => e.url) ?? [];
  return (
    <Tarjeta>
      <dl className="space-y-3 text-sm">
        <div><dt className="font-medium text-slate-600">Resultado</dt><dd>{parte.resultado ? RESULTADOS[parte.resultado] : 'Sin definir'}</dd></div>
        <div><dt className="font-medium text-slate-600">Diagnóstico</dt><dd className="whitespace-pre-line">{parte.diagnostico || 'Sin registrar'}</dd></div>
        <div>
          <dt className="font-medium text-slate-600">Tareas</dt>
          <dd>{parte.tareas.length ? <ul className="list-disc pl-5">{parte.tareas.map((t, i) => <li key={i}>{t}</li>)}</ul> : 'Sin registrar'}</dd>
        </div>
        {parte.materiales.length > 0 && (
          <div><dt className="font-medium text-slate-600">Materiales</dt><dd><ul className="list-disc pl-5">{parte.materiales.map((m, i) => <li key={i}>{m}</li>)}</ul></dd></div>
        )}
        {parte.finalizado_en && <div><dt className="font-medium text-slate-600">Finalizado</dt><dd>{fechaHora(parte.finalizado_en)}</dd></div>}
      </dl>
      {fotos.length > 0 && (
        <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-4">
          {fotos.map((f) => (
            <a key={f.evidencia_id} href={f.url} target="_blank" rel="noreferrer">
              <img src={f.url} alt={f.nombre ?? 'Evidencia de la atención'} className="h-32 w-full rounded-md object-cover" />
            </a>
          ))}
        </div>
      )}
    </Tarjeta>
  );
}

export default function DetalleParte() {
  const { id = '' } = useParams();
  const { usuario } = useAuth();
  const { data, error, isLoading } = useQuery({ queryKey: ['parte', id], queryFn: () => partes.detalle(id) });

  if (isLoading) return <p className="text-slate-600">Cargando…</p>;
  if (error) return <MensajeError error={error} />;
  const parte = data!;
  const volver = usuario?.rol === 'TECNICO' ? '/mis-visitas' : `/ordenes/${parte.orden_id}`;

  return (
    <>
      <p className="mb-2 text-sm"><Link className="text-sky-800 underline" to={volver}>← Volver</Link></p>
      <Encabezado titulo={`Parte de la visita ${parte.numero_visita_orden}`} />
      <p className="mb-3 text-sm text-slate-600">{parte.cliente_nombre} · {parte.direccion}, {parte.distrito} · {parte.fecha} · {parte.tecnico_nombre}</p>
      <ResumenParte parte={parte} />
    </>
  );
}
