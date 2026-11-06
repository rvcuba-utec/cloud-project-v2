import { useAuth } from '../auth/AuthContext';

export default function Inicio() {
  const { usuario } = useAuth();
  return (
    <section>
      <h1 className="text-xl font-semibold text-slate-900">Hola, {usuario?.nombre}</h1>
      <p className="mt-1 text-slate-600">Sesión activa en {usuario?.tenant_nombre}.</p>
    </section>
  );
}
