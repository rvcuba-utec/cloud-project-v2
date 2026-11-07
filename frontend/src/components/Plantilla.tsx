import { NavLink, Navigate, Outlet } from 'react-router';
import { useAuth } from '../auth/AuthContext';
import { NOMBRE_ROL } from '../auth/roles';

const ENLACES = [
  { a: '/panel', texto: 'Panel', roles: ['ADMIN', 'COORDINADOR'] },
  { a: '/ordenes', texto: 'Órdenes', roles: ['ADMIN', 'COORDINADOR'] },
  { a: '/agenda', texto: 'Agenda', roles: ['ADMIN', 'COORDINADOR'] },
  { a: '/mis-visitas', texto: 'Mis visitas', roles: ['TECNICO'] },
  { a: '/clientes', texto: 'Clientes', roles: ['ADMIN', 'COORDINADOR'] },
  { a: '/tecnicos', texto: 'Técnicos', roles: ['ADMIN', 'COORDINADOR'] },
];

export default function Plantilla() {
  const { usuario, cargando, cerrarSesion } = useAuth();

  if (cargando) return <p className="p-6 text-slate-600">Cargando…</p>;
  if (!usuario) return <Navigate to="/login" replace />;

  return (
    <div className="min-h-screen bg-slate-100">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-white px-4 py-3">
        <div className="flex flex-wrap items-center gap-4">
          <NavLink to="/" className="font-semibold text-slate-900">Trazora FSM</NavLink>
          <nav className="flex gap-3 text-sm">
            {ENLACES.filter((e) => e.roles.includes(usuario.rol)).map((e) => (
              <NavLink key={e.a} to={e.a} className={({ isActive }) => (isActive ? 'font-semibold text-sky-800' : 'text-slate-700 hover:text-sky-800')}>
                {e.texto}
              </NavLink>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-4 text-sm text-slate-700">
          <span><strong>{usuario.tenant_nombre}</strong> · {NOMBRE_ROL[usuario.rol]}</span>
          <button onClick={cerrarSesion} className="rounded-md border border-slate-300 px-3 py-1 hover:bg-slate-50">Salir</button>
        </div>
      </header>
      <main className="mx-auto max-w-6xl p-4">
        <Outlet />
      </main>
    </div>
  );
}
