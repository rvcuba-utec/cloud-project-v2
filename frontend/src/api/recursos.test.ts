import { describe, expect, it } from 'vitest';
import { consulta } from './recursos';

describe('consulta', () => {
  it('omite valores vacíos y codifica', () => {
    expect(consulta({ q: 'López & Cía', cursor: null, limit: 25, estado: '' })).toBe('?q=L%C3%B3pez+%26+C%C3%ADa&limit=25');
  });
  it('sin parámetros no agrega nada', () => {
    expect(consulta({ a: undefined })).toBe('');
  });
});
