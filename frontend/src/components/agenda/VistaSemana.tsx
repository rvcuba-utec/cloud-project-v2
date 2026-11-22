import { useEffect, useMemo, type PointerEvent } from 'react';
import { useQuery } from '@tanstack/react-query';
import { agenda, tecnicos, todas, type Intervalo, type Tecnico, type Visita } from '../../api/recursos';
import { BloqueVisita, Columna, Horas, type DestinoVisual } from '../Calendario';
import { ESPECIALIDADES, fechaCorta, hoyLima, lunesDe, sumarDias } from '../formato';
import { Boton, CAMPO, Cargando, MensajeError } from '../ui';

export interface DatosSemana {
  jornadas: Map<string, Intervalo[]>;
  ausencias: Map<string, string>;
  visitas: Visita[];
}

/** Vista semanal de un técnico (7 días) con el mismo arrastrar y soltar de la vista diaria. */
export default function VistaSemana({
  tecnicosActivos,
  tecnicoId,
  onElegirTecnico,
  lunes,
  onCambiarLunes,
  esperando,
  destino,
  arrastrandoId,
  enVuelo,
  onElegirVisita,
  onArrastrarVisita,
  onMarcarAusente,
  onDatosSemana,
}: {
  tecnicosActivos: Tecnico[];
  tecnicoId: string;
  onElegirTecnico: (id: string) => void;
  lunes: string;
  onCambiarLunes: (nuevoLunes: string) => void;
  esperando: number | null;
  destino: { tecnico_id: string; fecha: string; top: number; alto: number; hora: string; valido: boolean } | null;
  arrastrandoId?: string;
  enVuelo: ReadonlySet<string>;
  onElegirVisita: (v: Visita) => void;
  onArrastrarVisita: (e: PointerEvent<HTMLButtonElement>, v: Visita, offsetY: number) => void;
  onMarcarAusente: (tecnico: Tecnico, fecha: string, visitasDia: Visita[]) => void;
  onDatosSemana?: (datos: DatosSemana) => void;
}) {
  const hoy = hoyLima();
  const dias = useMemo(() => Array.from({ length: 7 }, (_, i) => sumarDias(lunes, i)), [lunes]);
  const domingo = dias[6];
  const tecnico = tecnicosActivos.find((t) => t.tecnico_id === tecnicoId) ?? tecnicosActivos[0];
  const idActivo = tecnico?.tecnico_id ?? '';

  const semana = useQuery({
    queryKey: ['jornadas', idActivo, lunes],
    queryFn: () => tecnicos.jornadas(idActivo, lunes, domingo),
    enabled: Boolean(idActivo),
  });
  const visitas = useQuery({
    queryKey: ['visitas-semana', idActivo, lunes],
    queryFn: () => todas((cursor) => agenda.listar({ tecnico_id: idActivo, desde: lunes, cursor, limit: 100 }), 4),
    enabled: Boolean(idActivo),
    refetchInterval: () => (esperando && Date.now() < esperando ? 2000 : 30_000),
  });

  const jornadas = useMemo(() => new Map(semana.data?.jornadas.map((j) => [j.fecha, j.intervalos])), [semana.data]);
  const ausencias = useMemo(() => new Map(semana.data?.ausencias.map((a) => [a.fecha, a.motivo])), [semana.data]);
  const visitasRango = useMemo(
    () => (visitas.data ?? []).filter((v) => v.estado !== 'CANCELADA' && v.fecha >= lunes && v.fecha <= domingo),
    [visitas.data, lunes, domingo],
  );
  const porDia = useMemo(() => {
    const m = new Map<string, Visita[]>();
    visitasRango.forEach((v) => m.set(v.fecha, [...(m.get(v.fecha) ?? []), v]));
    return m;
  }, [visitasRango]);

  // Exponemos el snapshot actual para que la validación en vivo del arrastre consulte jornadas y ocupadas sin re-pedirlas.
  useEffect(() => {
    onDatosSemana?.({ jornadas, ausencias, visitas: visitasRango });
  }, [onDatosSemana, jornadas, ausencias, visitasRango]);

  if (!tecnicosActivos.length) {
    return (
      <div className="card m-nolift items-start">
        <p className="text-[16px]">No hay técnicos activos para mostrar con ese filtro.</p>
      </div>
    );
  }

  return (
    <div className="min-w-0 flex-1">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <select aria-label="Técnico de la semana" className={`${CAMPO} !mt-0 !w-64`}
            value={idActivo} onChange={(e) => onElegirTecnico(e.target.value)}>
            {tecnicosActivos.map((t) => (
              <option key={t.tecnico_id} value={t.tecnico_id}>
                {t.nombre} ({t.especialidades.map((e) => ESPECIALIDADES[e]).join(', ')})
              </option>
            ))}
          </select>
          <span className="text-[14px] text-muted mayuscula-inicial">
            {fechaCorta(lunes)} – {fechaCorta(domingo)}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <Boton variante="secundario" pequeno aria-label="Semana anterior" onClick={() => onCambiarLunes(sumarDias(lunes, -7))}>←</Boton>
          <Boton variante="secundario" pequeno onClick={() => onCambiarLunes(lunesDe(hoy))}>Esta semana</Boton>
          <Boton variante="secundario" pequeno aria-label="Semana siguiente" onClick={() => onCambiarLunes(sumarDias(lunes, 7))}>→</Boton>
        </div>
      </div>

      <MensajeError error={semana.error ?? visitas.error} />
      {semana.isLoading || visitas.isLoading ? <Cargando /> : (
        <div data-scroll-agenda className="overflow-x-auto rounded-[20px] border border-line bg-surface/40">
          <div className="flex min-w-[920px]">
            <div className="sticky left-0 z-10 bg-ground/95 pt-[72px]"><Horas /></div>
            {dias.map((dia) => {
              const ausente = ausencias.get(dia);
              const intervalos = ausente ? undefined : jornadas.get(dia);
              const sinJornada = !intervalos?.length;
              const pasado = dia < hoy;
              const propias = porDia.get(dia) ?? [];
              const destinoDia: DestinoVisual | undefined =
                destino && destino.tecnico_id === idActivo && destino.fecha === dia ? destino : undefined;
              return (
                <div key={dia} className="min-w-[122px] flex-1">
                  <div className={`sticky top-0 flex h-[72px] flex-col justify-center border-b border-l border-line px-2 ${ausente ? 'bg-critical-soft' : dia === hoy ? 'bg-accent-soft' : 'bg-card'} ${pasado ? 'opacity-70' : ''}`}>
                    <p className={`text-[14px] font-medium mayuscula-inicial ${ausente ? 'text-critical' : ''}`}>
                      {fechaCorta(dia)}{dia === hoy && ' · hoy'}
                    </p>
                    {ausente ? (
                      <p className="truncate text-[12px] font-medium text-critical" title={ausente}>Ausente: {ausente}</p>
                    ) : sinJornada ? (
                      <p className="text-[12px] text-muted">Sin jornada</p>
                    ) : (
                      <div className="flex items-center justify-between gap-1">
                        <span className="text-[12px] text-muted">{propias.length} visitas</span>
                        {!pasado && tecnico && (
                          <button type="button" className="text-[12px] font-medium text-critical hover:underline"
                            onClick={() => onMarcarAusente(tecnico, dia, propias)}>Ausente</button>
                        )}
                      </div>
                    )}
                  </div>
                  <Columna
                    tono={ausente || sinJornada ? 'ausente' : undefined}
                    intervalos={intervalos}
                    tecnicoId={idActivo}
                    fecha={dia}
                    destino={destinoDia}
                    atenuada={pasado}>
                    {propias.map((v) => (
                      <BloqueVisita
                        key={v.visita_id}
                        v={v}
                        onClick={() => onElegirVisita(v)}
                        onArrastrar={(e, offsetY) => onArrastrarVisita(e, v, offsetY)}
                        arrastrando={arrastrandoId === v.visita_id}
                        enVuelo={enVuelo.has(v.visita_id)}
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
  );
}
