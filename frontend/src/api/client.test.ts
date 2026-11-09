import { beforeEach, describe, expect, it, vi } from 'vitest';

const almacen = new Map<string, string>();
vi.stubGlobal('sessionStorage', {
  getItem: (k: string) => almacen.get(k) ?? null,
  setItem: (k: string, v: string) => void almacen.set(k, v),
  removeItem: (k: string) => void almacen.delete(k),
});
vi.stubEnv('VITE_API_ORDENES', 'https://api.ejemplo/dev');

const { api, ApiError, configurarSesionExpirada } = await import('./client');
const { MAX_BYTES, construirFormulario, problemaDeArchivo } = await import('./evidencias');

const fallar = (ruta: string, servicio: 'ordenes' | 'agenda' = 'ordenes') =>
  api(servicio, ruta).then(
    () => { throw new Error('Se esperaba un error'); },
    (e: InstanceType<typeof ApiError>) => e,
  );

const responder = (status: number, cuerpo?: unknown) =>
  vi.fn().mockResolvedValue(new Response(cuerpo === undefined ? null : JSON.stringify(cuerpo), { status }));

beforeEach(() => almacen.clear());

describe('api', () => {
  it('envía el token y la clave de idempotencia', async () => {
    almacen.set('trazora_token', 'abc');
    const fetchFalso = responder(200, { ok: true });
    vi.stubGlobal('fetch', fetchFalso);

    await api('ordenes', '/ordenes', { method: 'POST', body: { a: 1 }, idempotencyKey: 'k1' });

    const [url, init] = fetchFalso.mock.calls[0];
    expect(url).toBe('https://api.ejemplo/dev/ordenes');
    expect(init.headers.Authorization).toBe('Bearer abc');
    expect(init.headers['Idempotency-Key']).toBe('k1');
  });

  it('nunca añade tenant_id por su cuenta', async () => {
    const fetchFalso = responder(200, {});
    vi.stubGlobal('fetch', fetchFalso);
    await api('ordenes', '/ordenes', { method: 'POST', body: { descripcion: 'x' } });
    expect(fetchFalso.mock.calls[0][1].body).not.toContain('tenant_id');
  });

  it('traduce el formato de error del backend', async () => {
    vi.stubGlobal('fetch', responder(409, { error: { codigo: 'HORARIO_OCUPADO', mensaje: 'Ocupado', detalle: { version: 2 } } }));
    const error = await fallar('/x');
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(409);
    expect(error.codigo).toBe('HORARIO_OCUPADO');
    expect(error.detalle).toEqual({ version: 2 });
  });

  it('cierra la sesión ante un 401 con token', async () => {
    almacen.set('trazora_token', 'vencido');
    const expirar = vi.fn();
    configurarSesionExpirada(expirar);
    vi.stubGlobal('fetch', responder(401, { message: 'Unauthorized' }));
    await api('ordenes', '/x').catch(() => {});
    expect(almacen.has('trazora_token')).toBe(false);
    expect(expirar).toHaveBeenCalledOnce();
  });

  it('un 401 sin token, como credenciales incorrectas, no dispara la expiración', async () => {
    const expirar = vi.fn();
    configurarSesionExpirada(expirar);
    vi.stubGlobal('fetch', responder(401, { error: { codigo: 'NO_AUTENTICADO', mensaje: 'x' } }));
    await api('ordenes', '/x').catch(() => {});
    expect(expirar).not.toHaveBeenCalled();
  });

  it('distingue la falta de conexión', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('fail')));
    const error = await fallar('/x');
    expect(error.codigo).toBe('SIN_CONEXION');
  });

  it('avisa si falta la URL de un servicio', async () => {
    const error = await fallar('/x', 'agenda');
    expect(error.codigo).toBe('SIN_CONFIGURAR');
  });
});

describe('construirFormulario', () => {
  it('coloca el archivo al final', () => {
    const f = construirFormulario({ url: 'u', fields: { key: 'k', policy: 'p' } }, new Blob(['x']));
    expect([...f.keys()]).toEqual(['key', 'policy', 'file']);
  });
});

describe('problemaDeArchivo', () => {
  it('acepta JPEG y PNG de hasta 5 MB', () => {
    expect(problemaDeArchivo({ type: 'image/jpeg', size: MAX_BYTES })).toBeNull();
    expect(problemaDeArchivo({ type: 'image/png', size: 1 })).toBeNull();
  });

  it('explica el motivo del rechazo', () => {
    expect(problemaDeArchivo({ type: 'application/pdf', size: 10 })).toContain('JPEG');
    expect(problemaDeArchivo({ type: 'image/png', size: MAX_BYTES + 1 })).toContain('5 MB');
    expect(problemaDeArchivo({ type: 'image/png', size: 0 })).toContain('vacío');
  });
});
