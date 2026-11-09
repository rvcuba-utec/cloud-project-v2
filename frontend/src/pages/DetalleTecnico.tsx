import { useMemo, useState, type FormEvent } from 'react';
import { Link, useParams } from 'react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { agenda, analitica, tecnicos, todas, type Visita } from '../api/recursos';
import { BloqueVisita, Columna, Horas, LeyendaCalendario } from '../components/Calendario';
import InputFecha from '../components/InputFecha';
import ReprogramarVisita from '../components/ReprogramarVisita';
import { ESPECIALIDADES, fechaCorta, fechaLarga, hoyLima, lunesDe, porcentaje, sumarDias } from '../components/formato';
import { AREA, Boton, CAMPO, Campo, Cargando, Cifra, Confirmacion, Encabezado, Insignia, MensajeError, Tarjeta } from '../components/ui';

const HORAS = Array.from({ length: 48 }, (_, i) => `${String(Math.floor(i / 2)).padStart(2, '0')}:${i % 2 ? '30' : '00'}`);

function SelectorHora({ etiqueta, valor, onCambio }: { etiqueta: string; valor: string; onCambio: (v: string) => void }) {
  return (
    <Campo etiqueta={etiqueta}>
      <select className={CAMPO} value={valor} onChange={(e) => onCambio(e.target.value)}>
        {HORAS.map((h) => <option key={h}>{h}</option>)}
      </select>
    </Campo>
  );
}

export default function DetalleTecnico() {
  const { id = '' } = useParams();
  const consultas = useQueryClient();
  const hoy = hoyLima();
  const [lunes, setLunes] = useState(lunesDe(hoy));
  const dias = useMemo(() => Array.from({ length: 7 }, (_, i) => sumarDias(lunes, i)), [lunes]);
  const domingo = dias[6];
  const [diaAusencia, setDiaAusencia] = useState<string | null>(null);
  const [motivo, setMotivo] = useState('Enfermedad');
  const [jornadaDia, setJornadaDia] = useState(hoy);
  const [inicio, setInicio] = useState('08:00');
  const [fin, setFin] = useState('17:00');
  const [esperar, setEsperar] = useState(0);
  const [reprogramando, setReprogramando] = useState<Visita | null>(null);

  const tecnico = useQuery({ queryKey: ['tecnico', id], queryFn: () => tecnicos.detalle(id) });
  const semana = useQuery({ queryKey: ['jornadas', id, lunes], queryFn: () => tecnicos.jornadas(id, lunes, domingo) });
  const visitas = useQuery({
    queryKey: ['visitas-semana', id, lunes],
    queryFn: () => todas((cursor) => agenda.listar({ tecnico_id: id, desde: lunes, cursor, limit: 100 }), 4),
    refetchInterval: esperar > Date.now() ? 2000 : false,
  });
  const metricas = useQuery({ queryKey: ['rendimiento', hoy], queryFn: () => analitica.tecnicos(hoy) });
  const refrescar = () => ['jornadas', 'visitas-semana', 'alertas', 'visitas-dia'].forEach((k) => consultas.invalidateQueries({ queryKey: [k] }));

  const jornada = useMutation({ mutationFn: () => tecnicos.definirJornada(id, jornadaDia, [{ inicio, fin }]), onSuccess: refrescar });
  const ausencia = useMutation({
    mutationFn: (fecha: string) => tecnicos.registrarAusencia(id, fecha, motivo),
    onSuccess: () => { setDiaAusencia(null); setEsperar(Date.now() + 30_000); refrescar(); },
  });
  const cambiarEstado = useMutation({
    mutationFn: (activo: boolean) => tecnicos.actualizar(id, { activo }),
    onSuccess: (t) => consultas.setQueryData(['tecnico', id], t),
  });

  if (tecnico.isLoading) return <Cargando />;
  if (tecnico.error) return <MensajeError error={tecnico.error} />;
  const t = tecnico.data!;
  const jornadas = new Map(semana.data?.jornadas.map((j) => [j.fecha, j.intervalos]));
  const ausentes = new Map(semana.data?.ausencias.map((a) => [a.fecha, a.motivo]));
  const porDia = (visitas.data ?? []).filter((v) => v.estado !== 'CANCELADA' && v.fecha <= domingo)
    .reduce<Record<string, Visita[]>>((m, v) => ({ ...m, [v.fecha]: [...(m[v.fecha] ?? []), v] }), {});
  const m = metricas.data?.items.find((x) => x.tecnico_id === id);
  const programadasEn = (fecha: string) => (porDia[fecha] ?? []).filter((v) => v.estado === 'PROGRAMADA').length;

  return (
    <>
      <p className="mb-3 text-[15px]"><Link className="link" to="/tecnicos">← Técnicos</Link></p>
      <Encabezado titulo={t.nombre} subtitulo={t.especialidades.map((e) => ESPECIALIDADES[e]).join(' · ')}>
        <Insignia tono={t.activo ? 'bien' : 'critico'}>{t.activo ? 'Activo' : 'Inactivo'}</Insignia>
        <Boton variante="secundario" disabled={cambiarEstado.isPending} onClick={() => cambiarEstado.mutate(!t.activo)}>{t.activo ? 'Desactivar' : 'Activar'}</Boton>
      </Encabezado>
      <MensajeError error={cambiarEstado.error} />

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Cifra etiqueta="Visitas hoy" valor={m?.carga_dia ?? 0} />
        <Cifra etiqueta="Resolución sin revisita" valor={m?.tasa_resolucion === undefined ? '—' : porcentaje(m.tasa_resolucion)} tono="bien" />
        <Cifra etiqueta="Tiempo medio de atención" valor={m?.tiempo_promedio_min === undefined ? '—' : `${Math.round(m.tiempo_promedio_min)} min`} />
        <Cifra etiqueta="Visitas completadas" valor={m?.visitas_completadas_total ?? 0} nota={`${m?.revisitas_generadas ?? 0} dejaron revisita`} />
      </div>

      {esperar > Date.now() && (
        <p role="status" className="entra mb-4 flex items-center gap-2 rounded-xl border border-good/30 bg-good-soft px-4 py-3 text-[15px]">
          <span className="size-2 animate-pulse rounded-full bg-good" />Ausencia registrada. Sus visitas se están reasignando al mejor técnico libre…
        </p>
      )}

      <Tarjeta titulo="Semana" accion={
        <div className="flex items-center gap-1">
          <Boton variante="secundario" pequeno aria-label="Semana anterior" onClick={() => setLunes(sumarDias(lunes, -7))}>←</Boton>
          <Boton variante="secundario" pequeno onClick={() => setLunes(lunesDe(hoy))}>Esta semana</Boton>
          <Boton variante="secundario" pequeno aria-label="Semana siguiente" onClick={() => setLunes(sumarDias(lunes, 7))}>→</Boton>
        </div>
      }>
        <div className="mb-3"><LeyendaCalendario /></div>
        <MensajeError error={semana.error ?? visitas.error} />
        <div className="overflow-x-auto">
          <div className="flex min-w-[860px]">
            <div className="pt-[72px]"><Horas /></div>
            {dias.map((dia) => {
              const ausente = ausentes.get(dia);
              const sinJornada = !jornadas.has(dia);
              return (
                <div key={dia} className="min-w-0 flex-1">
                  <div className={`flex h-[72px] flex-col justify-center border-b border-l border-line px-2 ${dia === hoy ? 'bg-accent-soft' : ''} ${ausente ? 'bg-critical-soft' : ''}`}>
                    <p className={`text-[14px] font-medium mayuscula-inicial ${ausente ? 'text-critical' : ''}`}>{fechaCorta(dia)}{dia === hoy && ' · hoy'}</p>
                    {ausente ? <p className="truncate text-[12px] font-medium text-critical" title={ausente}>Ausente: {ausente}</p>
                      : sinJornada ? <p className="text-[12px] text-muted">Sin jornada</p>
                      : dia >= hoy && <button type="button" className="text-left text-[12px] font-medium text-critical hover:underline" onClick={() => setDiaAusencia(dia)}>Marcar ausente</button>}
                  </div>
                  <Columna tono={ausente || sinJornada ? 'ausente' : undefined} intervalos={jornadas.get(dia)}>
                    {(porDia[dia] ?? []).map((v) => <BloqueVisita key={v.visita_id} v={v} onClick={() => v.estado === 'PROGRAMADA' ? setReprogramando(v) : undefined} />)}
                  </Columna>
                </div>
              );
            })}
          </div>
        </div>
        {visitas.isLoading && <Cargando />}
      </Tarjeta>

      <div className="mt-6 max-w-xl">
        <Tarjeta titulo="Definir jornada">
          <form onSubmit={(e: FormEvent) => { e.preventDefault(); jornada.mutate(); }} className="space-y-3">
            <Campo etiqueta="Fecha"><InputFecha required value={jornadaDia} onChange={setJornadaDia} /></Campo>
            <div className="grid grid-cols-2 gap-3">
              <SelectorHora etiqueta="Inicio" valor={inicio} onCambio={setInicio} />
              <SelectorHora etiqueta="Fin" valor={fin} onCambio={setFin} />
            </div>
            <Boton type="submit" disabled={jornada.isPending}>Guardar jornada</Boton>
            <MensajeError error={jornada.error} />
          </form>
        </Tarjeta>
      </div>

      {diaAusencia && (
        <Confirmacion abierta peligro titulo={`${t.nombre} no podrá trabajar`} confirmar="Registrar ausencia" ocupado={ausencia.isPending}
          onCancelar={() => setDiaAusencia(null)} onConfirmar={() => ausencia.mutate(diaAusencia)}>
          <p className="mayuscula-inicial">{fechaLarga(diaAusencia)}. {programadasEn(diaAusencia)
            ? <>Sus <strong>{programadasEn(diaAusencia)} visitas</strong> pasarán solas al técnico libre con menos carga y mejor resolución.</>
            : 'No tiene visitas programadas ese día.'}</p>
          <Campo etiqueta="Motivo"><textarea className={AREA} maxLength={300} value={motivo} onChange={(e) => setMotivo(e.target.value)} /></Campo>
          <MensajeError error={ausencia.error} />
        </Confirmacion>
      )}
      {reprogramando && <ReprogramarVisita visita={reprogramando} onCerrar={() => setReprogramando(null)} onHecho={() => { setReprogramando(null); refrescar(); }} />}
    </>
  );
}
