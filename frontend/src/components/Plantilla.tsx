import { useEffect, useRef, useState } from 'react';
import { Link, NavLink, Navigate, Outlet } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { alertas, type Aviso } from '../api/recursos';
import { useAuth } from '../auth/AuthContext';
import { NOMBRE_ROL } from '../auth/roles';
import { Cargando } from './ui';

const ENLACES = [
  { a: '/panel', texto: 'Panel', roles: ['ADMIN', 'COORDINADOR'] },
  { a: '/ordenes', texto: 'Órdenes', roles: ['ADMIN', 'COORDINADOR'] },
  { a: '/agenda', texto: 'Agenda', roles: ['ADMIN', 'COORDINADOR'] },
  { a: '/mis-visitas', texto: 'Mi día', roles: ['TECNICO'] },
  { a: '/clientes', texto: 'Clientes', roles: ['ADMIN', 'COORDINADOR'] },
  { a: '/tecnicos', texto: 'Técnicos', roles: ['ADMIN', 'COORDINADOR'] },
  { a: '/usuarios', texto: 'Usuarios', roles: ['ADMIN'] },
];
const SONDEO_MS = 15_000;

export function Marca() {
  return (
    <span className="flex items-center gap-2 font-display text-[20px] text-ink">
      <svg viewBox="0 0 24 24" className="size-6" aria-hidden="true">
        <rect width="24" height="24" rx="6" fill="currentColor" />
        <path d="M6 7.5h12M12 7.5V18" stroke="var(--p-bg)" strokeWidth="2.4" strokeLinecap="round" />
        <circle cx="17.5" cy="16.5" r="2.2" fill="var(--color-good)" />
      </svg>
      Trazora
    </span>
  );
}

/** Lo que el sistema hizo solo aparece un momento abajo a la derecha: la reasignación se ve en vivo. */
function AvisosEnVivo({ recientes }: { recientes: Aviso[] }) {
  const visto = useRef<string | null>(null);
  const [mostrando, setMostrando] = useState<Aviso[]>([]);
  useEffect(() => {
    if (!recientes.length) return;
    const ultimo = recientes[0].creado_en;
    if (visto.current === null) { visto.current = ultimo; return; } // Al entrar no se repite lo anterior.
    const nuevos = recientes.filter((a) => a.creado_en > (visto.current ?? ''));
    visto.current = ultimo;
    if (!nuevos.length) return;
    setMostrando((m) => [...nuevos, ...m].slice(0, 3));
    const t = setTimeout(() => setMostrando((m) => m.slice(0, -nuevos.length)), 9000);
    return () => clearTimeout(t);
  }, [recientes]);
  if (!mostrando.length) return null;
  return (
    <div aria-live="polite" className="fixed bottom-4 right-4 z-50 flex w-[min(380px,calc(100vw-32px))] flex-col gap-2">
      {mostrando.map((a) => (
        <Link key={a.creado_en + a.visita_id} to={`/ordenes/${a.orden_id}`}
          className="entra card !gap-1 border-l-4 !p-4 shadow-xl" style={{ borderLeftColor: a.tipo === 'REASIGNADA' ? 'var(--color-good)' : 'var(--color-critical)' }}>
          <span className="text-[13px] font-medium text-muted">{a.tipo === 'REASIGNADA' ? 'Reasignada automáticamente' : 'Necesita reprogramación'}</span>
          <span className="font-medium text-ink">{a.cliente_nombre}</span>
          <span className="text-sm text-ink">{a.detalle}</span>
        </Link>
      ))}
    </div>
  );
}

export default function Plantilla() {
  const { usuario, cargando, cerrarSesion } = useAuth();
  const [menu, setMenu] = useState(false);
  const gestiona = usuario?.rol === 'ADMIN' || usuario?.rol === 'COORDINADOR';
  const avisos = useQuery({
    queryKey: ['alertas'],
    queryFn: alertas.listar,
    enabled: gestiona,
    refetchInterval: SONDEO_MS,
  });

  if (cargando) return <div className="p-6"><Cargando /></div>;
  if (!usuario) return <Navigate to="/login" replace />;
  const pendientes = avisos.data?.pendientes.length ?? 0;
  const enlaces = ENLACES.filter((e) => e.roles.includes(usuario.rol));

  return (
    <div className="min-h-screen bg-ground">
      <header className="sticky top-0 z-40 border-b border-line bg-ground">
        <div className="mx-auto flex h-16 max-w-[1280px] items-center gap-4 px-4 md:px-8">
          <a className="skip-link" href="#contenido">Saltar al contenido</a>
          <NavLink to="/" aria-label="Trazora, inicio"><Marca /></NavLink>
          <nav aria-label="Principal" className="mx-auto hidden items-center gap-6 lg:flex">
            {enlaces.map((e) => (
              <NavLink key={e.a} to={e.a}
                className={({ isActive }) => `relative py-1 text-[15px] font-medium transition-colors ${isActive ? 'text-ink after:absolute after:inset-x-0 after:-bottom-[19px] after:h-0.5 after:bg-ink' : 'text-muted hover:text-ink'}`}>
                {e.texto}
                {e.a === '/panel' && pendientes > 0 && (
                  <span className="ml-1.5 inline-flex min-w-5 items-center justify-center rounded-full bg-critical px-1.5 text-[12px] font-semibold text-white" aria-label={`${pendientes} alertas`}>{pendientes}</span>
                )}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto hidden items-center gap-3 lg:ml-0 lg:flex">
            <span className="text-right text-[13px] leading-tight text-muted">
              <span className="block font-medium text-ink">{usuario.nombre}</span>
              {usuario.tenant_nombre} · {NOMBRE_ROL[usuario.rol]}
            </span>
            <button type="button" onClick={cerrarSesion} className="btn btn--secondary btn--sm">Salir</button>
          </div>
          <button type="button" className="btn btn--secondary btn--sm ml-auto lg:hidden" aria-expanded={menu} aria-controls="menu-movil"
            onClick={() => setMenu((m) => !m)}>
            {menu ? 'Cerrar' : 'Menú'}{pendientes > 0 && !menu && <span className="size-2 rounded-full bg-critical" aria-label="Hay alertas" />}
          </button>
        </div>
        {menu && (
          <div id="menu-movil" className="border-t border-line bg-ground px-4 pb-4 lg:hidden">
            <nav aria-label="Principal" className="flex flex-col">
              {enlaces.map((e) => (
                <NavLink key={e.a} to={e.a} onClick={() => setMenu(false)}
                  className={({ isActive }) => `flex h-14 items-center justify-between border-b border-line text-[17px] ${isActive ? 'font-medium text-ink' : 'text-ink/80'}`}>
                  {e.texto}
                  {e.a === '/panel' && pendientes > 0 && <span className="rounded-full bg-critical px-2 text-[13px] font-semibold text-white">{pendientes} alertas</span>}
                </NavLink>
              ))}
            </nav>
            <div className="mt-4 flex items-center justify-between text-[14px] text-muted">
              <span>{usuario.tenant_nombre} · {NOMBRE_ROL[usuario.rol]}</span>
              <button type="button" onClick={cerrarSesion} className="btn btn--secondary btn--sm">Salir</button>
            </div>
          </div>
        )}
      </header>
      <div id="contenido" className="mx-auto max-w-[1280px] px-4 pb-16 pt-8 md:px-8">
        <Outlet />
      </div>
      {gestiona && <AvisosEnVivo recientes={avisos.data?.recientes ?? []} />}
    </div>
  );
}
