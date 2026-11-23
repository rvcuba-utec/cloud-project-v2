import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import './index.css';
import App from './App';
import { AuthProvider } from './auth/AuthContext';
import { restaurarTema } from './theme/tema';

restaurarTema();

// Los avisos de los formularios los escribe el navegador en su propio idioma (en inglés, por ejemplo).
// Se reemplazan por textos en español, iguales en cualquier navegador.
document.addEventListener('invalid', (e) => {
  const c = e.target as HTMLInputElement;
  const v = c.validity;
  if (v.valueMissing) c.setCustomValidity('Completa este campo.');
  else if (v.typeMismatch && c.type === 'email') c.setCustomValidity('Escribe un correo válido, como nombre@empresa.com.');
  else if (v.tooShort) c.setCustomValidity(`Usa al menos ${c.minLength} caracteres.`);
  else if (v.patternMismatch) c.setCustomValidity(c.title || 'El formato no es válido.');
}, true);
document.addEventListener('input', (e) => (e.target as HTMLInputElement).setCustomValidity?.(''), true);

const clienteConsultas = new QueryClient({
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={clienteConsultas}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>,
);
