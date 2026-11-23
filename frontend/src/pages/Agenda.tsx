import { useCallback, useEffect, useMemo, useRef, useState, type PointerEvent } from 'react';
import { Link } from 'react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { agenda, alertas, mapa, tecnicos, todas, type Especialidad, type Orden, type Tecnico, type Visita } from '../api/recursos';
import { BloqueVisita, Columna, Horas, LeyendaCalendario, type DestinoVisual } from '../components/Calendario';
import InputFecha from '../components/InputFecha';
import MapaOrdenes from '../components/MapaOrdenes';
import ReprogramarVisita from '../components/ReprogramarVisita';
import BandejaOrdenes, { DURACION_BANDEJA_MIN } from '../components/agenda/BandejaOrdenes';
import Fantasma from '../components/agenda/Fantasma';
import VistaSemana, { type DatosSemana } from '../components/agenda/VistaSemana';
import { TEXTO_MOTIVO, duracionDe, moverBloque, validarSoltar } from '../components/agenda/dnd';
import { useArrastre } from '../components/agenda/useArrastre';
import { useMoverVisita } from '../components/agenda/useMoverVisita';
import { ESPECIALIDADES, ESTADOS_VISITA, fechaLarga, hace, horaLima, hoyLima, lunesDe, sumarDias } from '../components/formato';
import { AREA, Boton, CAMPO, Campo, Cargando, Confirmacion, Encabezado, Insignia, MensajeError, Toast } from '../components/ui';

const ESPERA_MS = 30_000;
const POR_PAGINA = 8; // técnicos (columnas) por página

interface ColumnaTecnico { tecnico_id: string; nombre: string; especialidades: Especialidad[]; disponible: boolean; intervalos?: { inicio: string; fin: string }[] }
interface AusenciaObjetivo { tecnico_id: string; nombre: string; fecha: string; visitasProgramadas: number }
type Arrastrado = { tipo: 'visita'; visita: Visita } | { tipo: 'orden'; orden: Orden };

export default function Agenda() {
  const consultas = useQueryClient();
  const hoy = hoyLima();
  const [vista, setVista] = useState<'dia' | 'semana'>('dia');
  const [fecha, setFecha] = useState(hoy);
  const [lunes, setLunes] = useState(() => lunesDe(hoy));
  const [tecnicoSemana, setTecnicoSemana] = useState('');
  const [bandejaAbierta, setBandejaAbierta] = useState(() => (typeof window !== 'undefined' ? window.innerWidth >= 1024 : true));
  const [todos, setTodos] = useState(false);
  const [especialidad, setEspecialidad] = useState<Especialidad | ''>('');
  const [elegida, setElegida] = useState<Visita | null>(null);
  const [reprogramando, setReprogramando] = useState<Visita | null>(null);
  const [ausente, setAusente] = useState<AusenciaObjetivo | null>(null);
  const [motivo, setMotivo] = useState('Enfermedad');
  const [esperando, setEsperando] = useState<number | null>(null);
  const [pagina, setPagina] = useState(0);
  const [resaltada, setResaltada] = useState<string | null>(null);
  useEffect(() => setPagina(0), [fecha, especialidad, todos]);

  const arrastradoRef = useRef<Arrastrado | null>(null);
  const datosSemanaRef = useRef<DatosSemana>({ jornadas: new Map(), ausencias: new Map(), visitas: [] });
  const guardarDatosSemana = useCallback((d: DatosSemana) => { datosSemanaRef.current = d; }, []);

  const visitas = useQuery({
    queryKey: ['visitas-dia', fecha],
    queryFn: () => todas((cursor) => agenda.listar({ fecha, cursor, limit: 100 })),
    enabled: vista === 'dia',
    refetchInterval: () => (esperando && Date.now() < esperando ? 2000 : 30_000),
  });
  const puntosMapa = useQuery({ queryKey: ['mapa'], queryFn: mapa.ordenes, refetchInterval: 30_000 });
  const avisos = useQuery({ queryKey: ['alertas'], queryFn: alertas.listar, refetchInterval: 15_000 });
  const perfiles = useQuery({ queryKey: ['tecnicos-todos'], queryFn: () => todas((cursor) => tecnicos.listar({ cursor, limit: 100 })) });
  const libres = useQuery({
    queryKey: ['tecnicos-disponibles', fecha],
    queryFn: () => tecnicos.disponibles(fecha),
    enabled: vista === 'dia',
  });
  useEffect(() => { if (esperando && Date.now() > esperando) setEsperando(null); }, [visitas.dataUpdatedAt, esperando]);

  const tecnicosActivos = useMemo<Tecnico[]>(
    () => (perfiles.data ?? [])
      .filter((t) => t.activo && (!especialidad || t.especialidades.includes(especialidad)))
      .sort((a, b) => a.nombre.localeCompare(b.nombre)),
    [perfiles.data, especialidad],
  );
  const perfilesPorId = useMemo(() => new Map((perfiles.data ?? []).map((t) => [t.tecnico_id, t])), [perfiles.data]);
  const libresPorId = useMemo(() => new Map(libres.data?.items.map((t) => [t.tecnico_id, t.intervalos])), [libres.data]);

  const columnas = useMemo<ColumnaTecnico[]>(() => {
    const conVisitas = new Set(visitas.data?.filter((v) => v.estado !== 'CANCELADA').map((v) => v.tecnico_id));
    return tecnicosActivos
      .filter((t) => todos || conVisitas.has(t.tecnico_id))
      .map((t) => ({
        tecnico_id: t.tecnico_id,
        nombre: t.nombre,
        especialidades: t.especialidades,
        disponible: libresPorId.has(t.tecnico_id),
        intervalos: libresPorId.get(t.tecnico_id),
      }))
      .sort((a, b) => Number(conVisitas.has(b.tecnico_id)) - Number(conVisitas.has(a.tecnico_id)) || Number(b.disponible) - Number(a.disponible) || a.nombre.localeCompare(b.nombre));
  }, [tecnicosActivos, libresPorId, visitas.data, todos]);

  const porTecnico = useMemo(() => {
    const m = new Map<string, Visita[]>();
    visitas.data?.forEach((v) => m.set(v.tecnico_id, [...(m.get(v.tecnico_id) ?? []), v]));
    return m;
  }, [visitas.data]);
  const paginas = Math.max(1, Math.ceil(columnas.length / POR_PAGINA));
  const actual = Math.min(pagina, paginas - 1); // si la lista se acorta, no se queda en una página vacía
  const visibles = columnas.slice(actual * POR_PAGINA, (actual + 1) * POR_PAGINA);
  const avisoReciente = useMemo(() => {
    const a = avisos.data?.recientes.find((x) => x.tipo === 'REASIGNADA');
    return a && avisos.dataUpdatedAt - new Date(a.creado_en).getTime() < 6 * 3600_000 ? a : undefined;
  }, [avisos.data, avisos.dataUpdatedAt]);
  const sinTecnico = visitas.data?.filter((v) => v.requiere_reprogramacion && v.estado === 'PROGRAMADA') ?? [];

  const movimiento = useMoverVisita();
  const refrescar = () => ['visitas-dia', 'visitas-semana', 'alertas', 'tecnicos-disponibles', 'jornadas', 'bandeja-ordenes'].forEach((k) => consultas.invalidateQueries({ queryKey: [k] }));

  const cancelar = useMutation({ mutationFn: (id: string) => agenda.cancelar(id), onSuccess: () => { setElegida(null); refrescar(); } });
  const marcarAusente = useMutation({
    mutationFn: (a: AusenciaObjetivo) => tecnicos.registrarAusencia(a.tecnico_id, a.fecha, motivo),
    onSuccess: () => { setAusente(null); setEsperando(Date.now() + ESPERA_MS); refrescar(); },
  });

  const arrastre = useArrastre({
    evaluar: (carga, donde) => {
      const item = arrastradoRef.current;
      const perfil = perfilesPorId.get(donde.tecnico_id);
      if (!item || !perfil) return 'FUERA_DE_JORNADA';
      const { inicio, fin } = moverBloque(donde.fecha, donde.hora, carga.duracionMin);
      const especialidadRequerida = item.tipo === 'visita' ? item.visita.tipo_servicio : item.orden.tipo_servicio;
      const ignorarVisitaId = item.tipo === 'visita' ? item.visita.visita_id : undefined;

      const intervalos = vista === 'dia'
        ? libresPorId.get(donde.tecnico_id)
        : (datosSemanaRef.current.ausencias.has(donde.fecha) ? undefined : datosSemanaRef.current.jornadas.get(donde.fecha));
      const ocupadas = vista === 'dia'
        ? (porTecnico.get(donde.tecnico_id) ?? []).filter((v) => v.estado !== 'CANCELADA')
        : datosSemanaRef.current.visitas;

      return validarSoltar(inicio, fin, {
        ahora: new Date(),
        intervalos,
        ocupadas,
        especialidades: perfil.especialidades,
        especialidadRequerida,
        ignorarVisitaId,
      });
    },
    onSoltar: (carga, destino) => {
      const item = arrastradoRef.current;
      const perfil = perfilesPorId.get(destino.tecnico_id);
      if (!item) return;
      const tecnico_nombre = perfil?.nombre ?? destino.tecnico_id;
      if (item.tipo === 'visita') {
        const v = item.visita;
        // Si cayó en el mismo técnico, fecha y hora (y no estaba sin técnico), no se hace nada.
        if (!v.requiere_reprogramacion && destino.tecnico_id === v.tecnico_id && destino.fecha === v.fecha && destino.hora === horaLima(v.inicio)) return;
        movimiento.mover.mutate({ visita: v, tecnico_id: destino.tecnico_id, tecnico_nombre, fecha: destino.fecha, hora: destino.hora });
        return;
      }
      movimiento.programar.mutate({
        orden: item.orden,
        tecnico_id: destino.tecnico_id,
        tecnico_nombre,
        fecha: destino.fecha,
        hora: destino.hora,
        duracionMin: carga.duracionMin,
      });
    },
    onInvalido: (_carga, destino) => {
      movimiento.mostrar({
        tono: 'error',
        texto: destino.motivo ? TEXTO_MOTIVO[destino.motivo] : 'No se puede soltar en ese horario.',
      });
    },
  });

  const iniciarArrastreVisita = (e: PointerEvent<HTMLButtonElement>, v: Visita, offsetY: number) => {
    arrastradoRef.current = { tipo: 'visita', visita: v };
    arrastre.empezar(e, {
      tipo: 'visita',
      id: v.visita_id,
      titulo: v.cliente_nombre,
      subtitulo: v.distrito,
      duracionMin: duracionDe(v.inicio, v.fin),
      offsetY,
    });
  };

  const iniciarArrastreOrden = (e: PointerEvent<HTMLElement>, orden: Orden) => {
    arrastradoRef.current = { tipo: 'orden', orden };
    arrastre.empezar(e, {
      tipo: 'orden',
      id: orden.orden_id,
      titulo: orden.cliente_nombre,
      subtitulo: `${orden.distrito} · ${ESPECIALIDADES[orden.tipo_servicio]}`,
      duracionMin: DURACION_BANDEJA_MIN,
      offsetY: 18,
    });
  };

  const abrirVisita = (v: Visita) => {
    if (arrastre.huboArrastre()) return;
    setElegida(v);
  };

  const cambiarVista = (nueva: 'dia' | 'semana') => {
    setVista(nueva);
    if (nueva === 'semana') {
      setLunes(lunesDe(fecha));
      if (!tecnicoSemana && columnas[0]) setTecnicoSemana(columnas[0].tecnico_id);
      else if (!tecnicoSemana && tecnicosActivos[0]) setTecnicoSemana(tecnicosActivos[0].tecnico_id);
    }
  };

  const idArrastrandoVisita = arrastre.arrastrando?.tipo === 'visita' ? arrastre.arrastrando.id : undefined;
  const idArrastrandoOrden = arrastre.arrastrando?.tipo === 'orden' ? arrastre.arrastrando.id : undefined;

  return (
    <>
      <Encabezado titulo="Agenda" subtitulo="Arrastra visitas para reprogramarlas o suelta órdenes sin visita sobre un técnico libre. Si alguien no puede venir, márcalo ausente y sus visitas se reasignan solas.">
        <div role="group" aria-label="Modo de vista" className="inline-flex rounded-xl border border-line bg-card p-0.5">
          <button type="button" onClick={() => cambiarVista('dia')} aria-pressed={vista === 'dia'}
            className={`rounded-lg px-3.5 py-1.5 text-[14px] font-medium transition-[background-color,color,transform] duration-150 active:scale-95 ${vista === 'dia' ? 'bg-accent text-accent-ink' : 'text-muted hover:text-ink'}`}>Día</button>
          <button type="button" onClick={() => cambiarVista('semana')} aria-pressed={vista === 'semana'}
            className={`rounded-lg px-3.5 py-1.5 text-[14px] font-medium transition-[background-color,color,transform] duration-150 active:scale-95 ${vista === 'semana' ? 'bg-accent text-accent-ink' : 'text-muted hover:text-ink'}`}>Semana</button>
        </div>
        {vista === 'dia' && (
          <>
            <div className="flex items-center gap-1">
              <Boton variante="secundario" pequeno aria-label="Día anterior" onClick={() => setFecha(sumarDias(fecha, -1))}>←</Boton>
              <Boton variante="secundario" pequeno onClick={() => setFecha(hoyLima())}>Hoy</Boton>
              <Boton variante="secundario" pequeno aria-label="Día siguiente" onClick={() => setFecha(sumarDias(fecha, 1))}>→</Boton>
            </div>
            <InputFecha aria-label="Fecha" className="w-44" value={fecha} onChange={setFecha} />
          </>
        )}
      </Encabezado>

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <p className="font-display text-2xl mayuscula-inicial">{vista === 'dia' ? fechaLarga(fecha) : 'Agenda semanal'}</p>
        <div className="flex flex-wrap items-center gap-3">
          <select aria-label="Especialidad" className={`${CAMPO} !mt-0 !w-64 max-w-full`} value={especialidad} onChange={(e) => setEspecialidad(e.target.value as Especialidad | '')}>
            <option value="">Todas las especialidades</option>
            {Object.entries(ESPECIALIDADES).map(([v, t]) => <option key={v} value={v}>{t}</option>)}
          </select>
          {vista === 'dia' && (
            <label className="flex h-11 items-center gap-2 text-[15px]">
              <input type="checkbox" className="size-4 accent-[var(--p-accent)]" checked={todos} onChange={(e) => setTodos(e.target.checked)} />Ver todos los técnicos
            </label>
          )}
        </div>
      </div>

      {esperando && (
        <p role="status" className="entra mb-3 flex items-center gap-2 rounded-xl border border-good/30 bg-good-soft px-4 py-3 text-[15px] text-ink">
          <span className="size-2 animate-pulse rounded-full bg-good" />Ausencia registrada. Buscando al mejor técnico libre para cada visita…
        </p>
      )}
      {(avisoReciente || (vista === 'dia' && sinTecnico.length > 0)) && (
        <div className="mb-3 grid gap-2 xl:grid-cols-2">
          {vista === 'dia' && sinTecnico.length > 0 && (
            <div role="alert" className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-xl border border-critical/35 bg-critical-soft px-4 py-2.5">
              <p className="flex items-center gap-2 font-medium text-critical">
                <svg viewBox="0 0 24 24" className="size-4 fill-none stroke-current" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 4 2.5 20h19L12 4Z" /><path d="M12 10v4.5M12 17.5v.01" /></svg>
                {sinTecnico.length === 1 ? 'Una visita se quedó sin técnico' : `${sinTecnico.length} visitas se quedaron sin técnico`}
              </p>
              <div className="flex flex-wrap gap-2">
                {sinTecnico.map((v) => <Boton key={v.visita_id} pequeno flecha onClick={() => setReprogramando(v)}>{horaLima(v.inicio)} {v.cliente_nombre}</Boton>)}
              </div>
            </div>
          )}
          {avisoReciente && (
            <p role="status" className="flex items-center gap-2 rounded-xl border border-good/35 bg-good-soft px-4 py-2.5 text-[15px] text-ink">
              <svg viewBox="0 0 24 24" className="size-4 shrink-0 fill-none stroke-good" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M4 8h13M13 4l4 4-4 4M20 16H7M11 12l-4 4 4 4" /></svg>
              <span className="font-medium text-good">Reasignada automáticamente</span>
              <span className="min-w-0 truncate">{avisoReciente.cliente_nombre}: {avisoReciente.detalle}</span>
              <span className="ml-auto shrink-0 text-[13px] text-muted">{hace(avisoReciente.creado_en)}</span>
            </p>
          )}
        </div>
      )}

      <MensajeError error={perfiles.error ?? (vista === 'dia' ? (visitas.error ?? libres.error) : null)} />
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <LeyendaCalendario />
        {vista === 'dia' && columnas.length > POR_PAGINA && (
          <div role="navigation" aria-label="Páginas de técnicos" className="flex items-center gap-2 text-[14px] text-muted">
            <span>Técnicos {actual * POR_PAGINA + 1}–{Math.min((actual + 1) * POR_PAGINA, columnas.length)} de {columnas.length}</span>
            <Boton variante="secundario" pequeno aria-label="Técnicos anteriores" disabled={actual === 0} onClick={() => setPagina(actual - 1)}>←</Boton>
            <Boton variante="secundario" pequeno aria-label="Técnicos siguientes" disabled={actual >= paginas - 1} onClick={() => setPagina(actual + 1)}>→</Boton>
          </div>
        )}
      </div>

      <div className="flex flex-col items-start gap-4 lg:flex-row">
        <div className={`flex w-full shrink-0 flex-col gap-4 lg:sticky lg:top-[72px] lg:self-start ${bandejaAbierta ? 'lg:w-[330px]' : 'lg:w-12'}`}>
          <BandejaOrdenes
            especialidad={especialidad}
            abierta={bandejaAbierta}
            onAlternar={() => setBandejaAbierta((a) => !a)}
            onArrastrar={iniciarArrastreOrden}
            arrastrandoId={idArrastrandoOrden}
            ocupado={movimiento.programar.isPending}
            onResaltar={setResaltada}
          />
          {bandejaAbierta && (
            <section aria-label="Mapa de órdenes" className="rounded-2xl border border-line bg-card p-3">
              <div className="mb-2 flex items-center justify-between px-1">
                <h2 className="text-[15px] font-semibold text-ink">Mapa de órdenes</h2>
                <span className="text-[12px] text-muted">Lima · vivas y cerradas</span>
              </div>
              <MensajeError error={puntosMapa.error} />
              <MapaOrdenes puntos={puntosMapa.data?.puntos ?? []} alto={220} denso resaltar={resaltada} />
            </section>
          )}
        </div>
        {vista === 'dia' ? (
          <div className="w-full min-w-0 flex-1">
            {visitas.isLoading || perfiles.isLoading ? <Cargando /> : columnas.length === 0 ? (
              <div className="card items-start">
                <p className="text-[16px]">No hay visitas este día{especialidad ? ` para ${ESPECIALIDADES[especialidad].toLowerCase()}` : ''}.</p>
                <Boton variante="secundario" onClick={() => setTodos(true)}>Ver todos los técnicos</Boton>
              </div>
            ) : (
              <div data-scroll-agenda className="overflow-x-auto rounded-2xl border border-line bg-card">
                <div className="flex min-w-max">
                  <div className="sticky left-0 z-10 bg-ground/95 pt-16"><Horas /></div>
                  {visibles.map((t) => {
                    const propias = (porTecnico.get(t.tecnico_id) ?? []).filter((v) => v.estado !== 'CANCELADA');
                    const destinoCol: DestinoVisual | undefined =
                      arrastre.destino && arrastre.destino.tecnico_id === t.tecnico_id && arrastre.destino.fecha === fecha ? arrastre.destino : undefined;
                    return (
                      <div key={t.tecnico_id} className="w-44">
                        <div className={`sticky top-0 flex h-16 flex-col justify-center border-b border-l border-line px-2 ${t.disponible ? 'bg-card' : 'bg-critical-soft'}`}>
                          <p className="truncate text-[14px] font-medium">{t.nombre}</p>
                          <div className="flex items-center justify-between gap-1">
                            <span className={`text-[12px] ${t.disponible ? 'text-muted' : 'font-medium text-critical'}`}>{t.disponible ? `${propias.length} visitas` : 'No disponible'}</span>
                            {t.disponible && fecha >= hoy && (
                              <button type="button" className="text-[12px] font-medium text-critical hover:underline"
                                onClick={() => setAusente({
                                  tecnico_id: t.tecnico_id,
                                  nombre: t.nombre,
                                  fecha,
                                  visitasProgramadas: propias.filter((v) => v.estado === 'PROGRAMADA').length,
                                })}>Marcar ausente</button>
                            )}
                          </div>
                        </div>
                        <Columna
                          tono={t.disponible ? undefined : 'ausente'}
                          intervalos={t.intervalos}
                          tecnicoId={t.tecnico_id}
                          fecha={fecha}
                          destino={destinoCol}
                          atenuada={fecha < hoy}>
                          {propias.map((v) => (
                            <BloqueVisita
                              key={v.visita_id}
                              v={v}
                              onClick={() => abrirVisita(v)}
                              onArrastrar={(e, offsetY) => iniciarArrastreVisita(e, v, offsetY)}
                              arrastrando={idArrastrandoVisita === v.visita_id}
                              enVuelo={movimiento.enVuelo.has(v.visita_id)}
                            />
                          ))}
                        </Columna>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        ) : perfiles.isLoading ? <Cargando /> : (
        <VistaSemana
          tecnicosActivos={tecnicosActivos}
          tecnicoId={tecnicoSemana}
          onElegirTecnico={setTecnicoSemana}
          lunes={lunes}
          onCambiarLunes={setLunes}
          esperando={esperando}
          destino={arrastre.destino}
          arrastrandoId={idArrastrandoVisita}
          enVuelo={movimiento.enVuelo}
          onElegirVisita={abrirVisita}
          onArrastrarVisita={iniciarArrastreVisita}
          onMarcarAusente={(t, f, propias) => setAusente({
            tecnico_id: t.tecnico_id,
            nombre: t.nombre,
            fecha: f,
            visitasProgramadas: propias.filter((v) => v.estado === 'PROGRAMADA').length,
          })}
          onDatosSemana={guardarDatosSemana}
        />
        )}
      </div>

      {arrastre.arrastrando && arrastre.puntero && (
        <Fantasma carga={arrastre.arrastrando} puntero={arrastre.puntero} destino={arrastre.destino} />
      )}
      <Toast aviso={movimiento.aviso} onCerrar={movimiento.cerrar} />

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
          <p>{fechaLarga(ausente.fecha)}. {ausente.visitasProgramadas === 0
            ? 'No tiene visitas programadas ese día.'
            : <>Sus <strong>{ausente.visitasProgramadas} visitas</strong> pasarán solas al técnico libre con menos carga y mejor resolución sin revisita. Si nadie puede, te aparecerán como alerta.</>}
          </p>
          <Campo etiqueta="Motivo"><textarea className={AREA} maxLength={300} value={motivo} onChange={(e) => setMotivo(e.target.value)} /></Campo>
          <MensajeError error={marcarAusente.error} />
        </Confirmacion>
      )}
      {reprogramando && <ReprogramarVisita visita={reprogramando} onCerrar={() => setReprogramando(null)} onHecho={() => { setReprogramando(null); refrescar(); }} />}
    </>
  );
}
