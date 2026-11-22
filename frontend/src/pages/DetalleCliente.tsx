import { useRef, useState, type FormEvent } from 'react';
import { Link, useParams } from 'react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { direccionDe, puntoDe } from '../api/geocodificar';
import { clientes } from '../api/recursos';
import ElegirPunto from '../components/ElegirPunto';
import { Boton, CAMPO, Campo, Cargando, Encabezado, Insignia, MensajeError, Tarjeta, useClaveIdempotencia } from '../components/ui';

export default function DetalleCliente() {
  const { id = '' } = useParams();
  const consultas = useQueryClient();
  const idempotencia = useClaveIdempotencia();
  const [form, setForm] = useState({ nombre: '', direccion: '', distrito: '', referencia: '' });
  const [punto, setPunto] = useState<{ lat: number; lng: number } | null>(null);
  const [foco, setFoco] = useState(0);
  const [buscando, setBuscando] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);
  const peticion = useRef(0);
  const cliente = useQuery({ queryKey: ['cliente', id], queryFn: () => clientes.detalle(id) });
  const ubicaciones = useQuery({ queryKey: ['ubicaciones', id], queryFn: () => clientes.ubicaciones(id) });

  const crear = useMutation({
    mutationFn: () => clientes.crearUbicacion(id, { ...form, ...(punto ?? {}) }, idempotencia.clave()),
    onSuccess: () => {
      idempotencia.renovar();
      setForm({ nombre: '', direccion: '', distrito: '', referencia: '' });
      setPunto(null);
      consultas.invalidateQueries({ queryKey: ['ubicaciones', id] });
    },
  });
  const cambiarEstado = useMutation({
    mutationFn: (activo: boolean) => clientes.actualizar(id, { activo }),
    onSuccess: (c) => consultas.setQueryData(['cliente', id], c),
  });

  const actualizar = (campo: keyof typeof form) => (e: { target: { value: string } }) => {
    idempotencia.renovar();
    setForm((f) => ({ ...f, [campo]: e.target.value }));
  };

  /** Clic en el mapa: se marca el punto y se rellenan dirección y distrito (siguen siendo editables). */
  const alElegirPunto = async (p: { lat: number; lng: number }) => {
    setPunto(p);
    idempotencia.renovar();
    const id = ++peticion.current;
    setBuscando(true);
    setAviso(null);
    try {
      const lugar = await direccionDe(p.lat, p.lng);
      if (id !== peticion.current) return;
      if (lugar) setForm((f) => ({ ...f, direccion: lugar.direccion || f.direccion, distrito: lugar.distrito || f.distrito }));
      else setAviso('No se encontró una dirección en ese punto. Escríbela a mano.');
    } catch (e) {
      if (id === peticion.current) setAviso(e instanceof Error ? e.message : 'No se pudo consultar el mapa.');
    } finally {
      if (id === peticion.current) setBuscando(false);
    }
  };

  /** Dirección escrita: se busca en Lima y el punto aparece en el mapa. No se pisa lo que escribió la persona. */
  const ubicarDireccion = async () => {
    if (!form.direccion.trim()) { setAviso('Escribe la dirección para buscarla en el mapa.'); return; }
    const id = ++peticion.current;
    setBuscando(true);
    setAviso(null);
    try {
      const lugar = await puntoDe([form.direccion, form.distrito].filter(Boolean).join(', '));
      if (id !== peticion.current) return;
      if (!lugar) { setAviso('No se encontró esa dirección en Lima. Revísala o marca el punto en el mapa.'); return; }
      setPunto({ lat: lugar.lat, lng: lugar.lng });
      setFoco((n) => n + 1);
      idempotencia.renovar();
      if (!form.distrito.trim() && lugar.distrito) setForm((f) => ({ ...f, distrito: lugar.distrito }));
    } catch (e) {
      if (id === peticion.current) setAviso(e instanceof Error ? e.message : 'No se pudo consultar el mapa.');
    } finally {
      if (id === peticion.current) setBuscando(false);
    }
  };

  if (cliente.isLoading) return <Cargando />;
  if (cliente.error) return <MensajeError error={cliente.error} />;
  const c = cliente.data!;

  return (
    <>
      <p className="mb-3 text-[15px]"><Link className="link" to="/clientes">← Clientes</Link></p>
      <Encabezado titulo={c.nombre} subtitulo={[c.telefono, c.correo].filter(Boolean).join(' · ') || undefined}>
        <Insignia tono={c.activo ? 'bien' : 'critico'}>{c.activo ? 'Activo' : 'Inactivo'}</Insignia>
        <Boton variante="secundario" disabled={cambiarEstado.isPending} onClick={() => cambiarEstado.mutate(!c.activo)}>
          {c.activo ? 'Desactivar' : 'Activar'}
        </Boton>
      </Encabezado>
      <MensajeError error={cambiarEstado.error} />
      <h2 className="mb-3 font-display text-2xl">Ubicaciones</h2>
      <MensajeError error={ubicaciones.error} />
      <ul className="mb-4 space-y-2">
        {ubicaciones.data?.items.map((u) => (
          <li key={u.ubicacion_id} className="card !flex-row flex-wrap items-center justify-between">
            <span><strong className="font-medium">{u.nombre}</strong> · {u.direccion}, {u.distrito}{u.referencia ? ` (${u.referencia})` : ''}</span>
            {u.lat !== undefined ? <Insignia tono="bien">En el mapa</Insignia> : <Insignia tono="neutro">Sin punto en el mapa</Insignia>}
          </li>
        ))}
        {ubicaciones.data?.items.length === 0 && <li className="text-sm text-muted">Aún no tiene ubicaciones.</li>}
      </ul>

      {c.activo && (
        <Tarjeta titulo="Agregar ubicación">
          <form onSubmit={(e: FormEvent) => { e.preventDefault(); crear.mutate(); }} className="grid gap-3 md:grid-cols-2">
            <Campo etiqueta="Nombre"><input className={CAMPO} required value={form.nombre} onChange={actualizar('nombre')} /></Campo>
            <Campo etiqueta="Dirección"><input className={CAMPO} required value={form.direccion} onChange={actualizar('direccion')} /></Campo>
            <Campo etiqueta="Distrito"><input className={CAMPO} required value={form.distrito} onChange={actualizar('distrito')} /></Campo>
            <Campo etiqueta="Referencia"><input className={CAMPO} value={form.referencia} onChange={actualizar('referencia')} /></Campo>
            <div className="md:col-span-2">
              <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-medium">Punto en el mapa <span className="font-normal text-muted">{punto ? `(${punto.lat}, ${punto.lng})` : '· haz clic donde está el local o busca la dirección'}</span></p>
                <Boton variante="secundario" pequeno disabled={buscando} onClick={ubicarDireccion}>{buscando ? 'Buscando…' : 'Buscar la dirección en el mapa'}</Boton>
              </div>
              <ElegirPunto valor={punto} foco={foco} onCambio={alElegirPunto}
                puntos={(ubicaciones.data?.items ?? []).filter((u) => u.lat !== undefined).map((u) => ({ lat: u.lat!, lng: u.lng!, nombre: u.nombre }))} />
              {aviso && <p role="status" className="mt-2 text-[14px] text-muted">{aviso}</p>}
            </div>
            <div className="md:col-span-2"><Boton type="submit" disabled={crear.isPending}>{crear.isPending ? 'Guardando…' : 'Agregar'}</Boton></div>
            <div className="md:col-span-2"><MensajeError error={crear.error} /></div>
          </form>
        </Tarjeta>
      )}
    </>
  );
}
