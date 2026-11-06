import { useState, type FormEvent } from 'react';
import { Navigate } from 'react-router';
import { ApiError } from '../api/client';
import { useAuth } from '../auth/AuthContext';

const CAMPO =
  'mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-slate-900 ' +
  'focus:border-sky-700 focus:outline-none focus:ring-2 focus:ring-sky-200';

export default function Login() {
  const { usuario, iniciarSesion, sesionExpirada } = useAuth();
  const [empresa, setEmpresa] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [enviando, setEnviando] = useState(false);

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
    <main className="flex min-h-screen items-center justify-center bg-slate-100 p-4">
      <div className="w-full max-w-sm">
        <h1 className="text-2xl font-semibold text-slate-900">Trazora FSM</h1>
        <p className="mb-6 text-slate-600">Cada visita bajo control</p>
        <form onSubmit={enviar} className="space-y-4 rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
          {sesionExpirada && !error && (
            <p role="status" className="rounded-md bg-amber-50 p-3 text-sm text-amber-900">
              Tu sesión terminó. Vuelve a iniciar sesión.
            </p>
          )}
          {error && (
            <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">
              {error}
            </p>
          )}
          <label className="block text-sm font-medium text-slate-700">
            Código de empresa
            <input className={`${CAMPO} uppercase`} required value={empresa} autoComplete="organization"
              onChange={(e) => setEmpresa(e.target.value)} />
          </label>
          <label className="block text-sm font-medium text-slate-700">
            Correo
            <input className={CAMPO} required type="email" value={email} autoComplete="username"
              onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label className="block text-sm font-medium text-slate-700">
            Contraseña
            <input className={CAMPO} required type="password" value={password} autoComplete="current-password"
              onChange={(e) => setPassword(e.target.value)} />
          </label>
          <button type="submit" disabled={enviando}
            className="w-full rounded-md bg-sky-800 px-4 py-2 font-medium text-white hover:bg-sky-900 disabled:opacity-60">
            {enviando ? 'Entrando…' : 'Iniciar sesión'}
          </button>
        </form>
      </div>
    </main>
  );
}
