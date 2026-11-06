import { Navigate } from 'react-router';
import { useAuth } from '../auth/AuthContext';

export default function Inicio() {
  const { usuario } = useAuth();
  return <Navigate to={usuario?.rol === 'TECNICO' ? '/mis-visitas' : '/ordenes'} replace />;
}
