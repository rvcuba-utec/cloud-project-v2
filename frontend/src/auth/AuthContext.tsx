import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, configurarSesionExpirada } from '../api/client';
import { borrarToken, guardarToken, obtenerToken } from './sesion';

export type Rol = 'ADMIN' | 'COORDINADOR' | 'TECNICO';

export interface Usuario {
  usuario_id: string;
  tenant_id: string;
  tenant_nombre: string;
  nombre: string;
  email: string;
  rol: Rol;
  tecnico_id?: string;
}

interface Credenciales {
  tenant_id: string;
  email: string;
  password: string;
}

interface Valor {
  usuario?: Usuario;
  cargando: boolean;
  sesionExpirada: boolean;
  iniciarSesion: (credenciales: Credenciales) => Promise<void>;
  cerrarSesion: () => void;
}

const Contexto = createContext<Valor | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const clienteConsultas = useQueryClient();
  const [token, setToken] = useState(obtenerToken);
  const [sesionExpirada, setSesionExpirada] = useState(false);

  const limpiar = useCallback(() => {
    borrarToken();
    setToken(null);
    clienteConsultas.clear(); // Ningún dato de una empresa debe quedar para la siguiente sesión.
  }, [clienteConsultas]);

  useEffect(() => {
    configurarSesionExpirada(() => {
      setSesionExpirada(true);
      limpiar();
    });
  }, [limpiar]);

  const { data: usuario, isLoading } = useQuery({
    queryKey: ['usuario-actual', token],
    queryFn: () => api<Usuario>('usuarios', '/usuarios/me'),
    enabled: Boolean(token),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  const iniciarSesion = useCallback(async (credenciales: Credenciales) => {
    const { token: nuevo } = await api<{ token: string }>('usuarios', '/auth/login', {
      method: 'POST',
      body: credenciales,
    });
    guardarToken(nuevo);
    setSesionExpirada(false);
    setToken(nuevo);
  }, []);

  const valor = useMemo(
    () => ({ usuario, cargando: Boolean(token) && isLoading, sesionExpirada, iniciarSesion, cerrarSesion: limpiar }),
    [usuario, token, isLoading, sesionExpirada, iniciarSesion, limpiar],
  );
  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>;
}

export function useAuth() {
  const valor = useContext(Contexto);
  if (!valor) throw new Error('useAuth debe usarse dentro de AuthProvider');
  return valor;
}
