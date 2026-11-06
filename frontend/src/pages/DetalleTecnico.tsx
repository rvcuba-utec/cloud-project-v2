import { useState, type FormEvent } from 'react';
import { Link, useParams } from 'react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { tecnicos } from '../api/recursos';
import { ESPECIALIDADES, hoyLima, sumarDias } from '../components/formato';
import { Boton, CAMPO, Campo, Encabezado, MensajeError, Tarjeta } from '../components/ui';

const DIAS_VISIBLES = 14;
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
  const hasta = sumarDias(hoy, DIAS_VISIBLES);
  const [fecha, setFecha] = useState(hoy);
  const [inicio, setInicio] = useState('08:00');
  const [fin, setFin] = useState('17:00');
  const [motivo, setMotivo] = useState('');

  const tecnico = useQuery({ queryKey: ['tecnico', id], queryFn: () => tecnicos.detalle(id) });
  const agenda = useQuery({ queryKey: ['jornadas', id, hoy], queryFn: () => tecnicos.jornadas(id, hoy, hasta) });
  const refrescar = () => consultas.invalidateQueries({ queryKey: ['jornadas', id] });

  const jornada = useMutation({ mutationFn: () => tecnicos.definirJornada(id, fecha, [{ inicio, fin }]), onSuccess: refrescar });
  const ausencia = useMutation({
    mutationFn: () => tecnicos.registrarAusencia(id, fecha, motivo),
    onSuccess: () => { setMotivo(''); refrescar(); },
  });
  const cambiarEstado = useMutation({
    mutationFn: (activo: boolean) => tecnicos.actualizar(id, { activo }),
    onSuccess: (t) => consultas.setQueryData(['tecnico', id], t),
  });

  if (tecnico.isLoading) return <p className="text-slate-600">Cargando…</p>;
  if (tecnico.error) return <MensajeError error={tecnico.error} />;
  const t = tecnico.data!;
  const ausentes = new Map(agenda.data?.ausencias.map((a) => [a.fecha, a.motivo]));

  return (
    <>
      <p className="mb-2 text-sm"><Link className="text-sky-800 underline" to="/tecnicos">← Técnicos</Link></p>
      <Encabezado titulo={t.nombre}>
        <Boton variante="secundario" disabled={cambiarEstado.isPending} onClick={() => cambiarEstado.mutate(!t.activo)}>
          {t.activo ? 'Desactivar' : 'Activar'}
        </Boton>
      </Encabezado>
      <MensajeError error={cambiarEstado.error} />
      <p className="mb-4 text-sm text-slate-700">{t.especialidades.map((e) => ESPECIALIDADES[e]).join(', ')} · {t.activo ? 'Activo' : 'Inactivo'}</p>

      <div className="grid gap-4 md:grid-cols-2">
        <Tarjeta>
          <h2 className="mb-2 font-semibold text-slate-900">Próximos {DIAS_VISIBLES} días</h2>
          <MensajeError error={agenda.error} />
          <ul className="space-y-1 text-sm">
            {agenda.data?.jornadas.map((j) => (
              <li key={j.fecha} className="flex justify-between gap-2">
                <span>{j.fecha}</span>
                <span className={ausentes.has(j.fecha) ? 'text-red-800' : 'text-slate-700'}>
                  {ausentes.has(j.fecha) ? `Ausente: ${ausentes.get(j.fecha)}` : j.intervalos.map((i) => `${i.inicio}–${i.fin}`).join(', ')}
                </span>
              </li>
            ))}
            {agenda.data?.jornadas.length === 0 && <li className="text-slate-500">Sin jornadas definidas.</li>}
          </ul>
        </Tarjeta>
        <Tarjeta>
          <h2 className="mb-2 font-semibold text-slate-900">Definir jornada o ausencia</h2>
          <form onSubmit={(e: FormEvent) => { e.preventDefault(); jornada.mutate(); }} className="space-y-3">
            <Campo etiqueta="Fecha"><input className={CAMPO} type="date" required value={fecha} onChange={(e) => setFecha(e.target.value)} /></Campo>
            <div className="grid grid-cols-2 gap-3">
              <SelectorHora etiqueta="Inicio" valor={inicio} onCambio={setInicio} />
              <SelectorHora etiqueta="Fin" valor={fin} onCambio={setFin} />
            </div>
            <Boton type="submit" disabled={jornada.isPending}>Guardar jornada</Boton>
            <MensajeError error={jornada.error} />
          </form>
          <form onSubmit={(e: FormEvent) => { e.preventDefault(); ausencia.mutate(); }} className="mt-4 space-y-3 border-t border-slate-100 pt-3">
            <Campo etiqueta="Motivo de ausencia"><input className={CAMPO} required value={motivo} onChange={(e) => setMotivo(e.target.value)} /></Campo>
            <Boton type="submit" variante="secundario" disabled={ausencia.isPending}>Registrar ausencia</Boton>
            <MensajeError error={ausencia.error} />
          </form>
        </Tarjeta>
      </div>
    </>
  );
}
