import { afterEach, describe, expect, it, vi } from 'vitest';
import { aLugar, direccionDe, puntoDe } from './geocodificar';

const responder = (cuerpo: unknown, ok = true) =>
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok, json: async () => cuerpo }));

afterEach(() => vi.unstubAllGlobals());

describe('geocodificar', () => {
  it('arma la dirección con calle y número, y el distrito', () => {
    const l = aLugar({ lat: '-12.1190012', lon: '-77.0310001', address: { road: 'Avenida Larco', house_number: '345', suburb: 'Miraflores', city: 'Lima' } });
    expect(l).toEqual({ lat: -12.119001, lng: -77.031, direccion: 'Avenida Larco 345', distrito: 'Miraflores' });
  });

  it('sin calle usa la primera parte del nombre completo', () => {
    const l = aLugar({ lat: '-12.0', lon: '-77.0', display_name: 'Parque Kennedy, Miraflores, Lima', address: { suburb: 'Miraflores' } });
    expect(l.direccion).toBe('Parque Kennedy');
  });

  it('clic en el mapa: conserva el punto del clic y devuelve el texto de la dirección', async () => {
    responder({ lat: '-12.12', lon: '-77.03', address: { road: 'Calle Berlín', suburb: 'Miraflores' } });
    const l = await direccionDe(-12.1201, -77.0299);
    expect(l).toMatchObject({ lat: -12.1201, lng: -77.0299, direccion: 'Calle Berlín', distrito: 'Miraflores' });
    const url = String((fetch as ReturnType<typeof vi.fn>).mock.calls[0][0]);
    expect(url).toContain('/reverse');
    expect(url).toContain('accept-language=es');
  });

  it('clic donde no hay dirección devuelve null', async () => {
    responder({ error: 'Unable to geocode' });
    expect(await direccionDe(0, 0)).toBeNull();
  });

  it('dirección escrita: busca solo en Lima y devuelve el punto', async () => {
    responder([{ lat: '-12.0464', lon: '-77.0428', address: { road: 'Jirón de la Unión', suburb: 'Cercado de Lima' } }]);
    const l = await puntoDe('Jirón de la Unión 500');
    expect(l).toMatchObject({ lat: -12.0464, lng: -77.0428 });
    const url = new URL(String((fetch as ReturnType<typeof vi.fn>).mock.calls[0][0]));
    expect(url.pathname).toBe('/search');
    expect(url.searchParams.get('q')).toBe('Jirón de la Unión 500');
    expect(url.searchParams.get('bounded')).toBe('1');
    expect(url.searchParams.get('countrycodes')).toBe('pe');
  });

  it('dirección que no existe devuelve null', async () => {
    responder([]);
    expect(await puntoDe('xxxxx')).toBeNull();
  });

  it('si el servicio falla, avisa en español', async () => {
    responder({}, false);
    await expect(puntoDe('Larco 345')).rejects.toThrow(/servicio de mapas/);
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('red')));
    await expect(direccionDe(-12, -77)).rejects.toThrow(/conexión/);
  });
});
