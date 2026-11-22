import { describe, expect, it, vi } from 'vitest';

vi.stubGlobal('sessionStorage', {
  getItem: () => null,
  setItem: () => undefined,
  removeItem: () => undefined,
});
vi.stubEnv('VITE_API_AGENDA', 'https://api.ejemplo/dev');

const { agenda, consulta } = await import('./recursos');

describe('consulta', () => {
  it('omite valores vacíos y codifica', () => {
    expect(consulta({ q: 'López & Cía', cursor: null, limit: 25, estado: '' })).toBe('?q=L%C3%B3pez+%26+C%C3%ADa&limit=25');
  });
  it('sin parámetros no agrega nada', () => {
    expect(consulta({ a: undefined })).toBe('');
  });
});

describe('contratos de agenda', () => {
  it('reprogramar envía exactamente tecnico_id, inicio, fin y version a /visitas/{id}/reprogramar', async () => {
    const fetchFalso = vi.fn().mockResolvedValue(new Response(JSON.stringify({ visita_id: 'VIS-1' }), { status: 200 }));
    vi.stubGlobal('fetch', fetchFalso);

    await agenda.reprogramar('VIS-1', {
      tecnico_id: 'TEC-2',
      inicio: '2026-11-22T15:00:00Z',
      fin: '2026-11-22T16:00:00Z',
      version: 3,
    });

    const [url, init] = fetchFalso.mock.calls[0];
    expect(url).toBe('https://api.ejemplo/dev/visitas/VIS-1/reprogramar');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual({
      tecnico_id: 'TEC-2',
      inicio: '2026-11-22T15:00:00Z',
      fin: '2026-11-22T16:00:00Z',
      version: 3,
    });
  });

  it('programar envía exactamente orden_id, tecnico_id, inicio y fin con Idempotency-Key a /visitas', async () => {
    const fetchFalso = vi.fn().mockResolvedValue(new Response(JSON.stringify({ visita_id: 'VIS-2' }), { status: 201 }));
    vi.stubGlobal('fetch', fetchFalso);

    await agenda.programar({
      orden_id: 'OT-1',
      tecnico_id: 'TEC-2',
      inicio: '2026-11-22T15:00:00Z',
      fin: '2026-11-22T16:00:00Z',
    }, 'clave-123');

    const [url, init] = fetchFalso.mock.calls[0];
    expect(url).toBe('https://api.ejemplo/dev/visitas');
    expect(init.method).toBe('POST');
    expect(init.headers['Idempotency-Key']).toBe('clave-123');
    expect(JSON.parse(init.body)).toEqual({
      orden_id: 'OT-1',
      tecnico_id: 'TEC-2',
      inicio: '2026-11-22T15:00:00Z',
      fin: '2026-11-22T16:00:00Z',
    });
  });
});
