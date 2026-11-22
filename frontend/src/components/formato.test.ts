import { describe, expect, it } from 'vitest';
import { coincide, fechaHora, horaLima, instanteLima, normalizar, sumarDias } from './formato';

describe('formato', () => {
  it('muestra la hora de Lima a partir de UTC', () => {
    expect(fechaHora('2026-11-10T15:00:00Z')).toContain('10:00');
  });
  it('convierte la hora de Lima a UTC en el formato de la API', () => {
    expect(instanteLima('2026-11-10', '10:00')).toBe('2026-11-10T15:00:00Z');
    expect(instanteLima('2026-11-10', '10:00', 90)).toBe('2026-11-10T16:30:00Z');
    expect(instanteLima('2026-11-10', '22:00')).toBe('2026-11-11T03:00:00Z');
  });
  it('muestra la hora en formato de 24 horas', () => {
    expect(horaLima('2026-11-10T20:30:00Z')).toBe('15:30');
  });
  it('cruza el fin de mes', () => {
    expect(sumarDias('2026-11-30', 1)).toBe('2026-12-01');
  });
});

describe('búsqueda por texto', () => {
  it('ignora tildes, mayúsculas y espacios sobrantes', () => {
    expect(normalizar('  Sofía   PÉREZ ')).toBe('sofia perez');
  });
  it('encuentra por nombre sin importar tildes ni mayúsculas', () => {
    expect(coincide('Ana Huamán', 'huaman')).toBe(true);
    expect(coincide('Ana Huamán', 'ANA')).toBe(true);
  });
  it('exige todas las palabras, en cualquier orden', () => {
    expect(coincide('Ana Huamán', 'huaman ana')).toBe(true);
    expect(coincide('Ana Huamán', 'ana castillo')).toBe(false);
  });
  it('sin búsqueda, todo coincide', () => {
    expect(coincide('Ana Huamán', '')).toBe(true);
    expect(coincide('Ana Huamán', '   ')).toBe(true);
  });
});
