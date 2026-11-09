import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { agenda, tecnicos, todas, type Especialidad, type Visita } from '../api/recursos';
import { BloqueVisita, Columna, Horas, LeyendaCalendario } from '../components/Calendario';
import InputFecha from '../components/InputFecha';
import ReprogramarVisita from '../components/ReprogramarVisita';
import { ESPECIALIDADES, ESTADOS_VISITA, fechaLarga, horaLima, hoyLima, sumarDias } from '../components/formato';
import { AREA, Boton, CAMPO, Campo, Cargando, Confirmacion, Encabezado, Insignia, MensajeError } from '../components/ui';

const ESPERA_MS = 30_000;
const POR_PAGINA = 8; // técnicos (columnas) por página

interface ColumnaTecnico { tecnico_id: string; nombre: string; especialidades: Especialidad[]; disponible: boolean; intervalos?: { inicio: string; fin: string }[] }

export default function Agenda() {
  const consultas = useQueryClient();
  const [fecha, setFecha] = useState(hoyLima());
  const [todos, setTodos] = useState(false);
  const [especialidad, setEspecialidad] = useState<Especialidad | ''>('');
  const [elegida, setElegida] = useState<Visita | null>(null);
  const [reprogramando, setReprogramando] = useState<Visita | null>(null);
  const [ausente, setAusente] = useState<ColumnaTecnico | null>(null);
  const [motivo, setMotivo] = useState('Enfermedad');
  const [esperando, setEsperando] = useState<number | null>(null);
  const [pagina, setPagina] = useState(0);
  useEffect(() => setPagina(0), [fecha, especialidad, todos]);

  const visitas = useQuery({
    queryKey: ['visitas-dia', fecha],
    queryFn: () => todas((cursor) => agenda.listar({ fecha, cursor, limit: 100 })),
    refetchInterval: esperando && Date.now() < esperando ? 2000 : 30_000,
  });
  const perfiles = useQuery({ queryKey: ['tecnicos-todos'], queryFn: () => todas((cursor) => tecnicos.listar({ cursor, limit: 100 })) });
  const libres = useQuery({ queryKey: ['tecnicos-disponibles', fecha], queryFn: () => tecnicos.disponibles(fecha) });
  useEffect(() => { if (esperando && Date.now() > esperando) setEsperando(null); }, [visitas.dataUpdatedAt, esperando]);

  const columnas = useMemo<ColumnaTecnico[]>(() => {
    const disponibles = new Map(libres.data?.items.map((t) => [t.tecnico_id, t.intervalos]));
    const conVisitas = new Set(visitas.data?.filter((v) => v.estado !== 'CANCELADA').map((v) => v.tecnico_id));
    return (perfiles.data ?? [])
      .filter((t) => t.activo && (!especialidad || t.especialidades.includes(especialidad)))
      .filter((t) => todos || conVisitas.has(t.tecnico_id))
      .map((t) => ({ tecnico_id: t.tecnico_id, nombre: t.nombre, especialidades: t.especialidades, disponible: disponibles.has(t.tecnico_id), intervalos: disponibles.get(t.tecnico_id) }))
      .sort((a, b) => Number(conVisitas.has(b.tecnico_id)) - Number(conVisitas.has(a.tecnico_id)) || Number(b.disponible) - Number(a.disponible) || a.nombre.localeCompare(b.nombre));
  }, [perfiles.data, libres.data, visitas.data, todos, especialidad]);

  const porTecnico = useMemo(() => {
    const m = new Map<string, Visita[]>();
    visitas.data?.forEach((v) => m.set(v.tecnico_id, [...(m.get(v.tecnico_id) ?? []), v]));
    return m;
  }, [visitas.data]);
  const paginas = Math.max(1, Math.ceil(columnas.length / POR_PAGINA));
  const actual = Math.min(pagina, paginas - 1); // si la lista se acorta, no se queda en una página vacía
  const visibles = columnas.slice(actual * POR_PAGINA, (actual + 1) * POR_PAGINA);
  const sinTecnico = visitas.data?.filter((v) => v.requiere_reprogramacion && v.estado === 'PROGRAMADA') ?? [];

  const refrescar = () => ['visitas-dia', 'alertas', 'tecnicos-disponibles'].forEach((k) => consultas.invalidateQueries({ queryKey: [k] }));
  const cancelar = useMutation({ mutationFn: (id: string) => agenda.cancelar(id), onSuccess: () => { setElegida(null); refrescar(); } });
  const marcarAusente = useMutation({
    mutationFn: (t: ColumnaTecnico) => tecnicos.registrarAusencia(t.tecnico_id, fecha, motivo),
    onSuccess: () => { setAusente(null); setEsperando(Date.now() + ESPERA_MS); refrescar(); },
  });
  const visitasDelAusente = ausente ? (porTecnico.get(ausente.tecnico_id) ?? []).filter((v) => v.estado === 'PROGRAMADA') : [];

  return (
    <>
      <Encabezado titulo="Agenda" subtitulo="Un tablero por día: cada columna es un técnico. Si alguien no puede venir, márcalo ausente y sus visitas se reasignan solas.">
        <div className="flex items-center gap-1">
          <Boton variante="secundario" pequeno aria-label="Día anterior" onClick={() => setFecha(sumarDias(fecha, -1))}>←</Boton>
          <Boton variante="secundario" pequeno onClick={() => setFecha(hoyLima())}>Hoy</Boton>
          <Boton variante="secundario" pequeno aria-label="Día siguiente" onClick={() => setFecha(sumarDias(fecha, 1))}>→</Boton>
        </div>
        <InputFecha aria-label="Fecha" className="w-44" value={fecha} onChange={setFecha} />
      </Encabezado>

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <p className="font-display text-2xl mayuscula-inicial">{fechaLarga(fecha)}</p>
        <div className="flex flex-wrap items-center gap-3">
          <select aria-label="Especialidad" className={`${CAMPO} !mt-0 w-48`} value={especialidad} onChange={(e) => setEspecialidad(e.target.value as Especialidad | '')}>
            <option value="">Todas las especialidades</option>
            {Object.entries(ESPECIALIDADES).map(([v, t]) => <option key={v} value={v}>{t}</option>)}
          </select>
          <label className="flex h-11 items-center gap-2 text-[15px]"><input type="checkbox" className="size-4 accent-[var(--p-accent)]" checked={todos} onChange={(e) => setTodos(e.target.checked)} />Ver todos los técnicos</label>
        </div>
      </div>

      {esperando && (
        <p role="status" className="entra mb-4 flex items-center gap-2 rounded-xl border border-good/30 bg-good-soft px-4 py-3 text-[15px] text-ink">
          <span className="size-2 animate-pulse rounded-full bg-good" />Ausencia registrada. Buscando al mejor técnico libre para cada visita…
        </p>
      )}
      {sinTecnico.length > 0 && (
        <div className="mb-4 rounded-xl border border-critical/30 bg-critical-soft/70 p-4">
          <p className="font-medium text-critical">{sinTecnico.length === 1 ? 'Una visita se quedó sin técnico' : `${sinTecnico.length} visitas se quedaron sin técnico`}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {sinTecnico.map((v) => <Boton key={v.visita_id} pequeno flecha onClick={() => setReprogramando(v)}>{horaLima(v.inicio)} {v.cliente_nombre}</Boton>)}
          </div>
        </div>
      )}

      <MensajeError error={visitas.error ?? perfiles.error ?? libres.error} />
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <LeyendaCalendario />
        {columnas.length > POR_PAGINA && (
          <div role="navigation" aria-label="Páginas de técnicos" className="flex items-center gap-2 text-[14px] text-muted">
            <span>Técnicos {actual * POR_PAGINA + 1}–{Math.min((actual + 1) * POR_PAGINA, columnas.length)} de {columnas.length}</span>
            <Boton variante="secundario" pequeno aria-label="Técnicos anteriores" disabled={actual === 0} onClick={() => setPagina(actual - 1)}>←</Boton>
            <Boton variante="secundario" pequeno aria-label="Técnicos siguientes" disabled={actual >= paginas - 1} onClick={() => setPagina(actual + 1)}>→</Boton>
          </div>
        )}
      </div>
      {visitas.isLoading || perfiles.isLoading ? <Cargando /> : columnas.length === 0 ? (
        <div className="card m-nolift items-start">
          <p className="text-[16px]">No hay visitas este día{especialidad ? ` para ${ESPECIALIDADES[especialidad].toLowerCase()}` : ''}.</p>
          <Boton variante="secundario" onClick={() => setTodos(true)}>Ver todos los técnicos</Boton>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-[20px] border border-line bg-surface/40">
          <div className="flex min-w-max">
            <div className="sticky left-0 z-10 bg-ground/95 pt-16"><Horas /></div>
            {visibles.map((t) => {
              const propias = (porTecnico.get(t.tecnico_id) ?? []).filter((v) => v.estado !== 'CANCELADA');
              return (
                <div key={t.tecnico_id} className="w-44">
                  <div className={`sticky top-0 flex h-16 flex-col justify-center border-b border-l border-line px-2 ${t.disponible ? 'bg-card' : 'bg-critical-soft'}`}>
                    <p className="truncate text-[14px] font-medium">{t.nombre}</p>
                    <div className="flex items-center justify-between gap-1">
                      <span className={`text-[12px] ${t.disponible ? 'text-muted' : 'font-medium text-critical'}`}>{t.disponible ? `${propias.length} visitas` : 'No disponible'}</span>
                      {t.disponible && fecha >= hoyLima() && (
                        <button type="button" className="text-[12px] font-medium text-critical hover:underline" onClick={() => setAusente(t)}>Marcar ausente</button>
                      )}
                    </div>
                  </div>
                  <Columna tono={t.disponible ? undefined : 'ausente'} intervalos={t.intervalos}>
                    {propias.map((v) => <BloqueVisita key={v.visita_id} v={v} onClick={() => setElegida(v)} />)}
                  </Columna>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {elegida && (
        <Confirmacion abierta titulo={elegida.cliente_nombre} confirmar="Reprogramar" cancelar="Cerrar"
          ocupado={elegida.estado !== 'PROGRAMADA' || cancelar.isPending}
          onCancelar={() => setElegida(null)} onConfirmar={() => { setReprogramando(elegida); setElegida(null); }}>
          <p className="text-muted">{horaLima(elegida.inicio)}–{horaLima(elegida.fin)} · {elegida.tecnico_nombre} · {elegida.direccion}, {elegida.distrito}</p>
          <p>{ESPECIALIDADES[elegida.tipo_servicio]}: {elegida.orden_descripcion}</p>
          <div className="flex flex-wrap items-center gap-3">
            <Insignia tono={elegida.requiere_reprogramacion ? 'critico' : elegida.estado === 'FINALIZADA' ? 'bien' : elegida.estado === 'EN_ATENCION' ? 'info' : 'aviso'}>
              {elegida.requiere_reprogramacion ? 'Sin técnico' : ESTADOS_VISITA[elegida.estado]}
            </Insignia>
            {elegida.reasignada_automaticamente && <Insignia tono="bien">Reasignada automáticamente</Insignia>}
            <Link className="link" to={`/ordenes/${elegida.orden_id}`}>Abrir la orden</Link>
            {elegida.estado === 'PROGRAMADA' && (
              <button type="button" className="text-[15px] font-medium text-critical hover:underline" disabled={cancelar.isPending}
                onClick={() => cancelar.mutate(elegida.visita_id)}>Cancelar la visita</button>
            )}
          </div>
          <MensajeError error={cancelar.error} />
        </Confirmacion>
      )}

      {ausente && (
        <Confirmacion abierta peligro titulo={`${ausente.nombre} no podrá trabajar`} confirmar="Registrar ausencia"
          ocupado={marcarAusente.isPending} onCancelar={() => setAusente(null)} onConfirmar={() => marcarAusente.mutate(ausente)}>
          <p>{fechaLarga(fecha)}. {visitasDelAusente.length === 0
            ? 'No tiene visitas programadas ese día.'
            : <>Sus <strong>{visitasDelAusente.length} visitas</strong> pasarán solas al técnico libre con menos carga y mejor resolución sin revisita. Si nadie puede, te aparecerán como alerta.</>}
          </p>
          <Campo etiqueta="Motivo"><textarea className={AREA} maxLength={300} value={motivo} onChange={(e) => setMotivo(e.target.value)} /></Campo>
          <MensajeError error={marcarAusente.error} />
        </Confirmacion>
      )}
      {reprogramando && <ReprogramarVisita visita={reprogramando} onCerrar={() => setReprogramando(null)} onHecho={() => { setReprogramando(null); refrescar(); }} />}
    </>
  );
}
