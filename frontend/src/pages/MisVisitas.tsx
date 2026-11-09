import { useState } from 'react';
import { Link, useNavigate } from 'react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { agenda, tecnicos, todas, type Visita } from '../api/recursos';
import { useAuth } from '../auth/AuthContext';
import { ESPECIALIDADES, ESTADOS_VISITA, fechaLarga, horaLima, hoyLima, sumarDias } from '../components/formato';
import { AREA, Boton, Campo, Cargando, Confirmacion, Encabezado, Insignia, MensajeError, type Tono } from '../components/ui';

const TONO: Record<string, Tono> = { PROGRAMADA: 'aviso', EN_ATENCION: 'info', FINALIZADA: 'bien', CANCELADA: 'neutro' };
const DIAS = 14;

function TarjetaVisita({ v, onIniciar, iniciando, destacada = false }: { v: Visita; onIniciar: () => void; iniciando: boolean; destacada?: boolean }) {
  return (
    <li className={`card m-nolift !gap-1 ${destacada ? 'border-accent shadow-[inset_0_0_0_1px_var(--p-accent)]' : ''}`}>
      <div className="flex items-start justify-between gap-3">
        <p className="font-display tabular text-[26px] leading-none">{horaLima(v.inicio)}<span className="text-[16px] text-muted">–{horaLima(v.fin)}</span></p>
        <Insignia tono={TONO[v.estado]} vivo={v.estado === 'EN_ATENCION'}>{ESTADOS_VISITA[v.estado]}</Insignia>
      </div>
      <p className="mt-2 text-[17px] font-medium">{v.cliente_nombre}</p>
      <p className="text-[15px] text-ink/85">{v.direccion}, {v.distrito}</p>
      <p className="text-[15px] text-muted">{ESPECIALIDADES[v.tipo_servicio]}: {v.orden_descripcion}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {v.estado === 'PROGRAMADA' && <Boton className="w-full sm:w-auto" flecha disabled={iniciando} onClick={onIniciar}>Iniciar visita</Boton>}
        {v.estado === 'EN_ATENCION' && <Link className="btn btn--primary w-full sm:w-auto" to={`/mis-visitas/${v.visita_id}`}>Continuar la atención</Link>}
        {v.estado === 'FINALIZADA' && <Link className="link text-[15px]" to={`/mis-visitas/${v.visita_id}`}>Ver el parte</Link>}
        <a className="btn btn--secondary w-full sm:w-auto" target="_blank" rel="noreferrer"
          href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${v.direccion}, ${v.distrito}, Lima`)}`}>Cómo llegar</a>
      </div>
    </li>
  );
}

export default function MisVisitas() {
  const consultas = useQueryClient();
  const navegar = useNavigate();
  const { usuario } = useAuth();
  const hoy = hoyLima();
  const [ausencia, setAusencia] = useState(false);
  const [motivo, setMotivo] = useState('');
  const [verTerminadas, setVerTerminadas] = useState(false);
  const { data, error, isLoading } = useQuery({
    queryKey: ['mis-visitas', hoy],
    queryFn: () => todas((cursor) => agenda.listar({ desde: hoy, cursor, limit: 100 }), 3),
  });
  const iniciar = useMutation({
    mutationFn: (id: string) => agenda.iniciar(id),
    onSuccess: (v) => navegar(`/mis-visitas/${v.visita_id}`),
    onSettled: () => consultas.invalidateQueries({ queryKey: ['mis-visitas'] }),
  });
  const reportar = useMutation({
    mutationFn: () => tecnicos.registrarAusencia(usuario!.tecnico_id!, hoy, motivo.trim() || 'No puede asistir'),
    onSuccess: () => { setAusencia(false); setTimeout(() => consultas.invalidateQueries({ queryKey: ['mis-visitas'] }), 4000); },
  });

  const limite = sumarDias(hoy, DIAS);
  const visitas = (data ?? []).filter((v) => v.estado !== 'CANCELADA' && v.fecha <= limite);
  const deHoy = visitas.filter((v) => v.fecha === hoy);
  const pendientesHoy = deHoy.filter((v) => v.estado !== 'FINALIZADA');
  const terminadasHoy = deHoy.filter((v) => v.estado === 'FINALIZADA');
  const proximas = visitas.filter((v) => v.fecha > hoy);
  const porDia = proximas.reduce<Record<string, Visita[]>>((m, v) => ({ ...m, [v.fecha]: [...(m[v.fecha] ?? []), v] }), {});
  const siguiente = pendientesHoy.find((v) => v.estado === 'EN_ATENCION') ?? pendientesHoy[0];

  return (
    <>
      <Encabezado titulo="Mi día" subtitulo={<span className="mayuscula-inicial">{fechaLarga(hoy)}</span>}>
        {usuario?.tecnico_id && pendientesHoy.length > 0 && (
          <Boton variante="secundario" onClick={() => setAusencia(true)}>No puedo trabajar hoy</Boton>
        )}
      </Encabezado>
      <MensajeError error={error ?? iniciar.error} />
      {reportar.isSuccess && (
        <p role="status" className="entra mb-4 rounded-xl border border-good/30 bg-good-soft px-4 py-3 text-[15px]">
          Avisamos a tu coordinación. Tus visitas de hoy se están pasando a otros técnicos.
        </p>
      )}
      {isLoading && <Cargando />}

      {!isLoading && (
        <section aria-labelledby="hoy" className="mb-8">
          <div className="mb-3 flex items-baseline justify-between">
            <h2 id="hoy" className="font-display text-2xl">Hoy</h2>
            <span className="text-[15px] text-muted">{pendientesHoy.length} por hacer · {terminadasHoy.length} terminadas</span>
          </div>
          {pendientesHoy.length === 0 && <p className="card m-nolift text-[16px]">{terminadasHoy.length ? 'Terminaste las visitas de hoy.' : 'No tienes visitas para hoy.'}</p>}
          <ul className="grid gap-3 md:grid-cols-2">
            {pendientesHoy.map((v) => (
              <TarjetaVisita key={v.visita_id} v={v} destacada={v === siguiente} iniciando={iniciar.isPending} onIniciar={() => iniciar.mutate(v.visita_id)} />
            ))}
          </ul>
          {terminadasHoy.length > 0 && (
            <div className="mt-4">
              <button type="button" className="text-[15px] font-medium text-accent hover:underline" aria-expanded={verTerminadas} onClick={() => setVerTerminadas((x) => !x)}>
                {verTerminadas ? 'Ocultar' : 'Ver'} las {terminadasHoy.length} terminadas
              </button>
              {verTerminadas && (
                <ul className="mt-3 grid gap-3 opacity-90 md:grid-cols-2">
                  {terminadasHoy.map((v) => <TarjetaVisita key={v.visita_id} v={v} iniciando={false} onIniciar={() => undefined} />)}
                </ul>
              )}
            </div>
          )}
        </section>
      )}

      {Object.keys(porDia).length > 0 && (
        <section aria-labelledby="proximas">
          <h2 id="proximas" className="mb-3 font-display text-2xl">Próximos días</h2>
          <div className="space-y-6">
            {Object.entries(porDia).map(([dia, lista]) => (
              <div key={dia}>
                <p className="mb-2 text-[15px] font-medium mayuscula-inicial text-muted">{fechaLarga(dia)}</p>
                <ul className="grid gap-3 md:grid-cols-2">
                  {lista.map((v) => <TarjetaVisita key={v.visita_id} v={v} iniciando={iniciar.isPending} onIniciar={() => iniciar.mutate(v.visita_id)} />)}
                </ul>
              </div>
            ))}
          </div>
        </section>
      )}

      <Confirmacion abierta={ausencia} peligro titulo="No puedes trabajar hoy" confirmar="Avisar a coordinación" ocupado={reportar.isPending}
        onCancelar={() => setAusencia(false)} onConfirmar={() => reportar.mutate()}>
        <p>Tus {pendientesHoy.filter((v) => v.estado === 'PROGRAMADA').length} visitas programadas de hoy pasarán a otro técnico. Las que ya empezaste siguen contigo.</p>
        <Campo etiqueta="Motivo (opcional)"><textarea className={AREA} maxLength={300} value={motivo} onChange={(e) => setMotivo(e.target.value)} /></Campo>
        <MensajeError error={reportar.error} />
      </Confirmacion>
    </>
  );
}
