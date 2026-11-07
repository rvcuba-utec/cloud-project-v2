import { useMemo, useState } from 'react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { agenda, analitica, tecnicos } from '../api/recursos';
import { ESTADOS_VISITA, horaLima, hoyLima, porcentaje } from '../components/formato';
import { CAMPO, Campo, Encabezado, MensajeError, Tabla, Tarjeta } from '../components/ui';

function Cifra({ titulo, valor, nota }: { titulo: string; valor: string | number; nota?: string }) {
  return (
    <Tarjeta>
      <p className="text-sm text-slate-600">{titulo}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-900">{valor}</p>
      {nota && <p className="text-xs text-slate-500">{nota}</p>}
    </Tarjeta>
  );
}

export default function Panel() {
  const hoy = hoyLima();
  const [periodo, setPeriodo] = useState(hoy.slice(0, 7));
  const mes = useQuery({
    queryKey: ['dashboard', periodo],
    queryFn: () => analitica.dashboard(periodo),
    placeholderData: keepPreviousData,
    enabled: /^\d{4}-\d{2}$/.test(periodo),
  });
  const rendimiento = useQuery({ queryKey: ['rendimiento', hoy], queryFn: () => analitica.tecnicos(hoy) });
  const perfiles = useQuery({ queryKey: ['tecnicos-nombres'], queryFn: () => tecnicos.listar({ limit: 100 }) });
  const visitasHoy = useQuery({ queryKey: ['visitas-hoy', hoy], queryFn: () => agenda.listar({ fecha: hoy, limit: 20 }) });

  const nombres = useMemo(() => new Map(perfiles.data?.items.map((t) => [t.tecnico_id, t.nombre])), [perfiles.data]);
  const filas = useMemo(
    () => [...(rendimiento.data?.items ?? [])]
      .map((m) => ({ ...m, nombre: nombres.get(m.tecnico_id) ?? m.tecnico_id }))
      .sort((a, b) => b.carga_dia - a.carga_dia || a.nombre.localeCompare(b.nombre)),
    [rendimiento.data, nombres],
  );
  const d = mes.data;

  return (
    <>
      <Encabezado titulo="Panel">
        <div className="w-44"><Campo etiqueta="Mes"><input className={CAMPO} type="month" value={periodo} max={hoy.slice(0, 7)} onChange={(e) => setPeriodo(e.target.value)} /></Campo></div>
      </Encabezado>
      <MensajeError error={mes.error} />
      {d && (
        <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-3">
          <Cifra titulo="Órdenes abiertas" valor={d.ordenes_abiertas} nota={`${d.ordenes_creadas} creadas en el mes`} />
          <Cifra titulo="Órdenes cerradas" valor={d.ordenes_cerradas} />
          <Cifra titulo="Órdenes canceladas" valor={d.ordenes_canceladas} />
          <Cifra titulo="Visitas programadas" valor={d.visitas_programadas} />
          <Cifra titulo="Visitas completadas" valor={d.visitas_completadas} />
          <Cifra titulo="Tiempo de cierre" valor={d.tiempo_promedio_cierre_dias === undefined ? 'Sin datos' : `${d.tiempo_promedio_cierre_dias} días`} nota="Promedio" />
        </div>
      )}

      <h2 className="mb-2 font-semibold text-slate-900">Rendimiento de técnicos</h2>
      <MensajeError error={rendimiento.error} />
      <Tabla columnas={['Técnico', 'Visitas hoy', 'Completadas', 'Resolución sin revisita', 'Tiempo promedio', 'Revisitas']} vacio={filas.length === 0}>
        {filas.map((m) => (
          <tr key={m.tecnico_id} className="border-b border-slate-100 last:border-0">
            <td className="px-3 py-2 font-medium text-slate-900">{m.nombre}</td>
            <td className="px-3 py-2">{m.carga_dia}</td>
            <td className="px-3 py-2">{m.visitas_completadas_total}</td>
            <td className="px-3 py-2">{m.tasa_resolucion === undefined ? 'Sin historial' : porcentaje(m.tasa_resolucion)}</td>
            <td className="px-3 py-2">{m.tiempo_promedio_min === undefined ? '—' : `${m.tiempo_promedio_min} min`}</td>
            <td className="px-3 py-2">{m.revisitas_generadas}</td>
          </tr>
        ))}
      </Tabla>

      <h2 className="mb-2 mt-6 font-semibold text-slate-900">Visitas de hoy</h2>
      <MensajeError error={visitasHoy.error} />
      <ul className="space-y-2">
        {visitasHoy.data?.items.map((v) => (
          <li key={v.visita_id} className="rounded-md border border-slate-200 bg-white p-3 text-sm">
            <strong>{horaLima(v.inicio)}–{horaLima(v.fin)}</strong> · {v.cliente_nombre} · {v.tecnico_nombre} · {ESTADOS_VISITA[v.estado]}
          </li>
        ))}
        {visitasHoy.data?.items.length === 0 && <li className="text-sm text-slate-500">No hay visitas programadas para hoy.</li>}
      </ul>
    </>
  );
}
