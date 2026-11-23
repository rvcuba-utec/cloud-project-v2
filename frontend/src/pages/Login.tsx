import { useState, type FormEvent } from 'react';
import { Navigate } from 'react-router';
import { ApiError } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { MarcaIcono } from '../components/Plantilla';
import { CAMPO } from '../components/ui';

export default function Login() {
  const { usuario, iniciarSesion, sesionExpirada } = useAuth();
  const [empresa, setEmpresa] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [verClave, setVerClave] = useState(false);

  if (usuario) return <Navigate to="/" replace />;

  async function enviar(evento: FormEvent) {
    evento.preventDefault();
    setError('');
    setEnviando(true);
    try {
      await iniciarSesion({ tenant_id: empresa.trim().toUpperCase(), email: email.trim(), password });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Ocurrió un error inesperado');
      setEnviando(false);
    }
  }

  return (
    <main className="grid min-h-screen bg-ground lg:grid-cols-[1.05fr_1fr]">
      <section className="relative hidden overflow-hidden bg-inv p-12 text-inv-ink lg:flex lg:flex-col lg:justify-between" aria-label="Trazora">
        <p className="relative z-10 flex items-center gap-2.5 font-display text-[22px]">
          <MarcaIcono className="size-7" />
          Trazora
        </p>
        <div className="relative z-10 max-w-[32ch]">
          <h1 className="font-display text-[clamp(34px,2.4vw+14px,50px)] leading-[1.05]">Cada visita técnica, bajo control.</h1>
          <p className="mt-5 max-w-[46ch] text-[17px] leading-relaxed text-inv-muted">
            Órdenes, agenda, partes con fotos y técnicos en un solo lugar. Si alguien no puede llegar, sus visitas pasan solas al técnico mejor preparado.
          </p>
        </div>
        <ul className="relative z-10 grid max-w-xl grid-cols-3 gap-6 text-[14px] text-inv-muted">
          <li><span className="mb-1 block text-[15px] font-medium text-inv-ink">Sin dobles reservas</span>Cada media hora se reserva una sola vez.</li>
          <li><span className="mb-1 block text-[15px] font-medium text-inv-ink">Reasignación sola</span>Por carga del día y resolución sin revisita.</li>
          <li><span className="mb-1 block text-[15px] font-medium text-inv-ink">Partes con fotos</span>Desde el celular del técnico.</li>
        </ul>
        <svg className="absolute -right-24 top-1/2 w-[560px] -translate-y-1/2 text-inv-ink opacity-40" viewBox="0 0 400 400" aria-hidden="true">
          {[...Array(7)].map((_, i) => <circle key={i} cx="200" cy="200" r={40 + i * 26} fill="none" stroke="currentColor" strokeOpacity={0.22 - i * 0.025} />)}
          {[[150, 120, '--pin-critical'], [260, 160, '--pin-good'], [210, 260, '--pin-warning'], [120, 230, '--pin-good'], [300, 250, '--pin-good'], [180, 190, '--pin-info']].map(([x, y, c], i) => (
            <g key={i}><circle cx={x as number} cy={y as number} r="14" fill={`var(${c})`} opacity=".25" className="pulso" style={{ transformOrigin: `${x}px ${y}px`, animationDelay: `${i * 0.4}s` }} /><circle cx={x as number} cy={y as number} r="6" fill={`var(${c})`} /></g>
          ))}
        </svg>
      </section>
      <div className="flex items-center justify-center p-6">
        <div className="entra w-full max-w-sm">
          <p className="mb-8 flex items-center gap-2 font-display text-[22px] lg:hidden"><MarcaIcono className="size-7" />Trazora</p>
          <h2 className="font-display text-[30px] leading-tight">Inicia sesión</h2>
          <p className="mb-6 mt-1 text-muted">Con el código de tu empresa y tu correo.</p>
          <form onSubmit={enviar} className="space-y-4">
            {sesionExpirada && !error && (
              <p role="status" className="rounded-lg border border-warning/25 bg-warning-soft p-3 text-sm text-warning">Tu sesión terminó. Vuelve a iniciar sesión.</p>
            )}
            {error && <p role="alert" className="rounded-lg border border-critical/25 bg-critical-soft p-3 text-sm text-critical">{error}</p>}
            <label className="block text-sm font-medium text-ink">
              Código de empresa
              <input className={`${CAMPO} uppercase`} required value={empresa} autoComplete="organization" placeholder="CLIMALIMA"
                onChange={(e) => setEmpresa(e.target.value)} />
            </label>
            <label className="block text-sm font-medium text-ink">
              Correo
              <input className={CAMPO} required type="email" value={email} autoComplete="username"
                onChange={(e) => setEmail(e.target.value)} />
            </label>
            <label className="block text-sm font-medium text-ink">
              Contraseña
              <span className="relative block">
                <input className={`${CAMPO} pr-24`} required type={verClave ? 'text' : 'password'} value={password} autoComplete="current-password"
                  onChange={(e) => setPassword(e.target.value)} />
                <button type="button" aria-pressed={verClave} onClick={() => setVerClave((v) => !v)}
                  className="absolute inset-y-0 right-0 mt-1 flex h-11 items-center px-3 text-sm font-medium text-accent hover:underline">
                  {verClave ? 'Ocultar' : 'Mostrar'}
                </button>
              </span>
            </label>
            <button type="submit" disabled={enviando} className="btn btn--primary w-full disabled:opacity-60">
              {enviando ? 'Entrando…' : 'Iniciar sesión'}
            </button>
          </form>
          <p className="mt-6 text-[14px] text-muted"><a className="link" href="/presentacion/">Qué es Trazora</a></p>
        </div>
      </div>
    </main>
  );
}
