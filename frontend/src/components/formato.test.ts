import { describe, expect, it } from 'vitest';
import { fechaHora, sumarDias } from './formato';

describe('formato', () => {
  it('muestra la hora de Lima a partir de UTC', () => {
    expect(fechaHora('2026-11-10T15:00:00Z')).toContain('10:00');
  });
  it('cruza el fin de mes', () => {
    expect(sumarDias('2026-11-30', 1)).toBe('2026-12-01');
  });
});
