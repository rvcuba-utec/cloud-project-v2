import { describe, expect, it } from 'vitest';
import { fechaDMA, fechaISO, mascaraFecha } from './fecha';

describe('fecha DD/MM/AAAA', () => {
  it('muestra día, mes y año', () => {
    expect(fechaDMA('2026-11-09')).toBe('09/11/2026');
    expect(fechaDMA('')).toBe('');
  });
  it('lee DD/MM/AAAA como AAAA-MM-DD', () => {
    expect(fechaISO('09/11/2026')).toBe('2026-11-09');
    expect(fechaISO('12/01/2027')).toBe('2027-01-12'); // 12 de enero, no 1 de diciembre
  });
  it('rechaza fechas que no existen o incompletas', () => {
    expect(fechaISO('31/02/2026')).toBe('');
    expect(fechaISO('09/13/2026')).toBe('');
    expect(fechaISO('09/11/26')).toBe('');
    expect(fechaISO('')).toBe('');
  });
  it('pone las barras al escribir', () => {
    expect(mascaraFecha('1')).toBe('1');
    expect(mascaraFecha('091')).toBe('09/1');
    expect(mascaraFecha('09112026')).toBe('09/11/2026');
    expect(mascaraFecha('09/11/2026999')).toBe('09/11/2026');
    expect(mascaraFecha('ab09')).toBe('09');
  });
});
