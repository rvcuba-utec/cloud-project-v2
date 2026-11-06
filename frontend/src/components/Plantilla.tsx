import { Navigate, Outlet } from 'react-router';
import { useAuth } from '../auth/AuthContext';
import { NOMBRE_ROL } from '../auth/roles';

export default function Plantilla() {
  const { usuario, cargando, cerrarSesion } = useAuth();

  if (cargando) return <p className="p-6 text-slate-600">Cargando…</p>;
  if (!usuario) return <Navigate to="/login" replace />;

  return (
    <div className="min-h-screen bg-slate-100">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-white px-4 py-3">
        <span className="font-semibold text-slate-900">Trazora FSM</span>
        <div className="flex items-center gap-4 text-sm text-slate-700">
          <span>
            <strong>{usuario.tenant_nombre}</strong> · {NOMBRE_ROL[usuario.rol]}
          </span>
          <button onClick={cerrarSesion} className="rounded-md border border-slate-300 px-3 py-1 hover:bg-slate-50">
            Salir
          </button>
        </div>
      </header>
      <main className="mx-auto max-w-6xl p-4">
        <Outlet />
      </main>
    </div>
  );
}
