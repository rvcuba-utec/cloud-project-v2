import { useEffect, useRef, useState } from 'react';
import { Link, NavLink, Navigate, Outlet, useLocation } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { alertas, type Aviso } from '../api/recursos';
import { useAuth } from '../auth/AuthContext';
import { NOMBRE_ROL } from '../auth/roles';
import { useTema } from '../theme/tema';
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

export function MarcaIcono({ className = 'size-7' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <rect width="24" height="24" rx="7" fill="var(--p-accent)" />
      <path d="M7 8h10M12 8v9" stroke="var(--p-accent-ink)" strokeWidth="2.4" strokeLinecap="round" fill="none" />
    </svg>
  );
}

export function Marca() {
  return (
    <span className="flex items-center gap-2 font-display text-[20px] text-ink">
      <MarcaIcono className="size-6" />
      Trazora
    </span>
  );
}

function BotonTema() {
  const { tema, alternar } = useTema();
  return (
    <button type="button" onClick={alternar} aria-label={tema === 'dark' ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'}
      className="grid size-9 place-items-center rounded-lg border border-line text-ink transition-[border-color,transform] duration-150 hover:border-ink active:scale-95">
      <svg viewBox="0 0 24 24" className="size-[18px] fill-none stroke-current" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        {tema === 'dark'
          ? <><circle cx="12" cy="12" r="4" /><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6 7 7M17 17l1.4 1.4M5.6 18.4 7 17M17 7l1.4-1.4" /></>
          : <path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5Z" />}
      </svg>
    </button>
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
      {mostrando.map((a) => {
        const ok = a.tipo === 'REASIGNADA';
        return (
          <Link key={a.creado_en + a.visita_id} to={`/ordenes/${a.orden_id}`}
            className="entra card !gap-1 !p-4 shadow-xl transition-colors hover:border-line-strong">
            <span className={`flex items-center gap-2 text-[13px] font-medium ${ok ? 'text-good' : 'text-critical'}`}>
              <span className={`size-2 rounded-full ${ok ? 'bg-good' : 'bg-critical'}`} aria-hidden="true" />
              {ok ? 'Reasignada automáticamente' : 'Necesita reprogramación'}
            </span>
            <span className="font-medium text-ink">{a.cliente_nombre}</span>
            <span className="text-sm text-ink">{a.detalle}</span>
          </Link>
        );
      })}
    </div>
  );
}

export default function Plantilla() {
  const { usuario, cargando, cerrarSesion } = useAuth();
  const { pathname } = useLocation();
  const [menu, setMenu] = useState(false);
  const gestiona = usuario?.rol === 'ADMIN' || usuario?.rol === 'COORDINADOR';
  const avisos = useQuery({
    queryKey: ['alertas'],
    queryFn: alertas.listar,
    enabled: gestiona,
    refetchInterval: SONDEO_MS,
  });

  if (cargando) return <div className="p-6"><Cargando /></div>;
  if (!usuario) {
    // Sin sesión, la raíz muestra la portada pública (estática, fuera de la SPA).
    if (window.location.pathname === '/') { window.location.replace('/presentacion/'); return null; }
    return <Navigate to="/login" replace />;
  }
  const pendientes = avisos.data?.pendientes.length ?? 0;
  const enlaces = ENLACES.filter((e) => e.roles.includes(usuario.rol));
  // La agenda necesita todo el ancho: bandeja, mapa y calendario en una pantalla.
  const ancho = pathname.startsWith('/agenda') ? 'max-w-[1760px]' : 'max-w-[1280px]';

  return (
    <div className="min-h-screen bg-ground">
      <header className="sticky top-0 z-40 border-b border-line bg-card">
        <div className={`mx-auto flex h-14 items-center gap-4 px-4 md:px-7 ${ancho}`}>
          <a className="skip-link" href="#contenido">Saltar al contenido</a>
          <NavLink to="/" aria-label="Trazora, inicio"><Marca /></NavLink>
          <nav aria-label="Principal" className="ml-6 hidden items-center gap-1 lg:flex">
            {enlaces.map((e) => (
              <NavLink key={e.a} to={e.a}
                className={({ isActive }) => `relative flex h-9 items-center gap-1.5 rounded-lg px-3 text-[15px] font-medium transition-colors duration-150 ${isActive ? 'text-ink after:absolute after:inset-x-3 after:-bottom-[11px] after:h-0.5 after:rounded-full after:bg-accent' : 'text-muted hover:bg-surface hover:text-ink'}`}>
                {e.texto}
                {e.a === '/panel' && pendientes > 0 && (
                  <span className="inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-critical px-1.5 text-[11px] font-semibold text-card" aria-label={`${pendientes} alertas`}>{pendientes}</span>
                )}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto hidden items-center gap-3 lg:flex">
            <span className="text-right text-[12px] leading-tight text-muted">
              <span className="block text-[13px] font-medium text-ink">{usuario.nombre}</span>
              {usuario.tenant_nombre} · {NOMBRE_ROL[usuario.rol]}
            </span>
            <BotonTema />
            <button type="button" onClick={cerrarSesion} className="btn btn--secondary btn--sm">Salir</button>
          </div>
          <div className="ml-auto flex items-center gap-2 lg:hidden">
            <BotonTema />
            <button type="button" className="btn btn--secondary btn--sm" aria-expanded={menu} aria-controls="menu-movil"
              onClick={() => setMenu((m) => !m)}>
              {menu ? 'Cerrar' : 'Menú'}{pendientes > 0 && !menu && <span className="size-2 rounded-full bg-critical" aria-label="Hay alertas" />}
            </button>
          </div>
        </div>
        {menu && (
          <div id="menu-movil" className="border-t border-line bg-card px-4 pb-4 lg:hidden">
            <nav aria-label="Principal" className="flex flex-col">
              {enlaces.map((e) => (
                <NavLink key={e.a} to={e.a} onClick={() => setMenu(false)}
                  className={({ isActive }) => `flex h-14 items-center justify-between border-b border-line text-[17px] ${isActive ? 'font-medium text-ink' : 'text-ink/80'}`}>
                  {e.texto}
                  {e.a === '/panel' && pendientes > 0 && <span className="rounded-full bg-critical px-2 text-[13px] font-semibold text-card">{pendientes} alertas</span>}
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
      <div id="contenido" className={`mx-auto px-4 pb-16 pt-6 md:px-7 ${ancho}`}>
        <Outlet />
      </div>
      {gestiona && <AvisosEnVivo recientes={avisos.data?.recientes ?? []} />}
    </div>
  );
}
