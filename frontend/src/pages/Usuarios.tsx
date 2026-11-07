import { useState, type FormEvent } from 'react';
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { tecnicos, usuarios, type CuentaUsuario } from '../api/recursos';
import type { Rol } from '../auth/AuthContext';
import { useAuth } from '../auth/AuthContext';
import { NOMBRE_ROL } from '../auth/roles';
import { Boton, CAMPO, Campo, Encabezado, MensajeError, Paginador, Tabla, Tarjeta, usePaginacion } from '../components/ui';

const ROLES = Object.keys(NOMBRE_ROL) as Rol[];
const VACIO = { nombre: '', email: '', password: '', rol: 'COORDINADOR' as Rol, tecnico_id: '' };

function NuevoUsuario({ onCreado, onCancelar }: { onCreado: () => void; onCancelar: () => void }) {
  const [datos, setDatos] = useState(VACIO);
  const opciones = useQuery({
    queryKey: ['tecnicos-opciones'],
    queryFn: () => tecnicos.listar({ limit: 100 }),
    enabled: datos.rol === 'TECNICO',
  });
  const crear = useMutation({
    mutationFn: () => usuarios.crear({ ...datos, tecnico_id: datos.rol === 'TECNICO' ? datos.tecnico_id : undefined }),
    onSuccess: onCreado,
  });
  const cambiar = (campo: keyof typeof VACIO, valor: string) => setDatos((d) => ({ ...d, [campo]: valor }));

  return (
    <Tarjeta className="mb-4">
      <form onSubmit={(e: FormEvent) => { e.preventDefault(); crear.mutate(); }} className="grid gap-3 md:grid-cols-2">
        <Campo etiqueta="Nombre"><input className={CAMPO} required value={datos.nombre} onChange={(e) => cambiar('nombre', e.target.value)} /></Campo>
        <Campo etiqueta="Correo"><input className={CAMPO} required type="email" value={datos.email} onChange={(e) => cambiar('email', e.target.value)} /></Campo>
        <Campo etiqueta="Contraseña inicial (mínimo 8 caracteres)">
          <input className={CAMPO} required type="password" minLength={8} autoComplete="new-password" value={datos.password} onChange={(e) => cambiar('password', e.target.value)} />
        </Campo>
        <Campo etiqueta="Rol">
          <select className={CAMPO} value={datos.rol} onChange={(e) => cambiar('rol', e.target.value)}>
            {ROLES.map((r) => <option key={r} value={r}>{NOMBRE_ROL[r]}</option>)}
          </select>
        </Campo>
        {datos.rol === 'TECNICO' && (
          <Campo etiqueta="Perfil de técnico">
            <select className={CAMPO} required value={datos.tecnico_id} onChange={(e) => cambiar('tecnico_id', e.target.value)}>
              <option value="">Elige un técnico</option>
              {opciones.data?.items.map((t) => <option key={t.tecnico_id} value={t.tecnico_id}>{t.nombre}</option>)}
            </select>
          </Campo>
        )}
        <div className="flex gap-2 md:col-span-2">
          <Boton type="submit" disabled={crear.isPending}>{crear.isPending ? 'Guardando…' : 'Crear usuario'}</Boton>
          <Boton variante="secundario" onClick={onCancelar}>Cancelar</Boton>
        </div>
        <div className="md:col-span-2"><MensajeError error={crear.error} /></div>
      </form>
    </Tarjeta>
  );
}

export default function Usuarios() {
  const consultas = useQueryClient();
  const { usuario: yo } = useAuth();
  const paginacion = usePaginacion();
  const [creando, setCreando] = useState(false);
  const { data, error, isLoading } = useQuery({
    queryKey: ['usuarios', paginacion.cursor],
    queryFn: () => usuarios.listar({ cursor: paginacion.cursor, limit: 25 }),
    placeholderData: keepPreviousData,
  });
  const refrescar = () => consultas.invalidateQueries({ queryKey: ['usuarios'] });
  const actualizar = useMutation({
    mutationFn: ({ id, cambios }: { id: string; cambios: Partial<CuentaUsuario> }) => usuarios.actualizar(id, cambios),
    onSettled: refrescar,
  });

  return (
    <>
      <Encabezado titulo="Usuarios y roles">
        {!creando && <Boton onClick={() => setCreando(true)}>Nuevo usuario</Boton>}
      </Encabezado>
      {creando && <NuevoUsuario onCancelar={() => setCreando(false)} onCreado={() => { setCreando(false); refrescar(); }} />}
      <MensajeError error={error} />
      <MensajeError error={actualizar.error} />
      {isLoading ? <p className="text-slate-600">Cargando…</p> : (
        <Tabla columnas={['Nombre', 'Correo', 'Rol', 'Estado', '']} vacio={!data?.items.length}>
          {data?.items.map((u) => {
            const propio = u.usuario_id === yo?.usuario_id; // El backend tampoco permite cambiarse a uno mismo.
            return (
              <tr key={u.usuario_id}>
                <td className="px-3 py-2 font-medium text-slate-900">{u.nombre}</td>
                <td className="px-3 py-2">{u.email}</td>
                <td className="px-3 py-2">
                  <select aria-label={`Rol de ${u.nombre}`} className="rounded border border-slate-300 bg-white px-2 py-1 disabled:opacity-60" value={u.rol}
                    disabled={propio || actualizar.isPending}
                    onChange={(e) => actualizar.mutate({ id: u.usuario_id, cambios: { rol: e.target.value as Rol } })}>
                    {ROLES.map((r) => <option key={r} value={r}>{NOMBRE_ROL[r]}</option>)}
                  </select>
                </td>
                <td className="px-3 py-2">{u.estado === 'ACTIVO' ? 'Activo' : 'Inactivo'}</td>
                <td className="px-3 py-2 text-right">
                  {!propio && (
                    <Boton variante="secundario" disabled={actualizar.isPending}
                      onClick={() => actualizar.mutate({ id: u.usuario_id, cambios: { estado: u.estado === 'ACTIVO' ? 'INACTIVO' : 'ACTIVO' } })}>
                      {u.estado === 'ACTIVO' ? 'Desactivar' : 'Activar'}
                    </Boton>
                  )}
                </td>
              </tr>
            );
          })}
        </Tabla>
      )}
      <Paginador hayAnterior={paginacion.hayAnterior} siguiente={data?.next_cursor} onAnterior={paginacion.anterior} onSiguiente={paginacion.siguiente} />
    </>
  );
}
