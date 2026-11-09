import { Navigate, Outlet } from 'react-router';
import { useAuth, type Rol } from '../auth/AuthContext';

/** Solo mejora la navegación: la seguridad real está en el backend. */
export default function RutaPorRol({ roles }: { roles: Rol[] }) {
  const { usuario } = useAuth();
  return usuario && roles.includes(usuario.rol) ? <Outlet /> : <Navigate to="/" replace />;
}
