import { describe, expect, it } from 'vitest';
import { duracionDe, horaDesdeY, moverBloque, validarSoltar, yDesdeHora, type ContextoSoltar } from './dnd';

const ALTO = 56; // px por hora
const base: ContextoSoltar = {
  ahora: new Date('2026-11-10T12:00:00Z'), // 07:00 en Lima
  intervalos: [{ inicio: '08:00', fin: '12:00' }, { inicio: '13:00', fin: '17:00' }],
  ocupadas: [],
  especialidades: ['REPARACION', 'MANTENIMIENTO'],
  especialidadRequerida: 'REPARACION',
};
const lima = (hora: string, extra = 0) => moverBloque('2026-11-10', hora, extra);

describe('horaDesdeY', () => {
  it('ajusta al bloque de 30 minutos más cercano', () => {
    expect(horaDesdeY(0, ALTO, 7, 19)).toBe('07:00');
    expect(horaDesdeY(ALTO, ALTO, 7, 19)).toBe('08:00');
    expect(horaDesdeY(ALTO * 1.4, ALTO, 7, 19)).toBe('08:30'); // 84 min → 08:24 → 08:30
    expect(horaDesdeY(ALTO * 1.2, ALTO, 7, 19)).toBe('08:00'); // 72 min → 08:12 → 08:00
  });
  it('no se sale de la rejilla', () => {
    expect(horaDesdeY(-300, ALTO, 7, 19)).toBe('07:00');
    expect(horaDesdeY(ALTO * 40, ALTO, 7, 19, 60)).toBe('18:00'); // un bloque de 60 min termina a las 19:00
    expect(horaDesdeY(ALTO * 40, ALTO, 7, 19)).toBe('18:30');
  });
  it('es inversa de yDesdeHora', () => {
    expect(horaDesdeY(yDesdeHora('10:30', ALTO, 7), ALTO, 7, 19)).toBe('10:30');
  });
});

describe('moverBloque', () => {
  it('conserva la duración y devuelve UTC', () => {
    const m = moverBloque('2026-11-10', '10:00', 90);
    expect(m).toEqual({ inicio: '2026-11-10T15:00:00Z', fin: '2026-11-10T16:30:00Z' });
    expect(duracionDe(m.inicio, m.fin)).toBe(90);
  });
});

describe('validarSoltar', () => {
  it('acepta un horario libre dentro de la jornada', () => {
    const { inicio, fin } = lima('09:00', 60);
    expect(validarSoltar(inicio, fin, base)).toBeNull();
  });
  it('rechaza una hora que ya pasó', () => {
    const { inicio, fin } = lima('09:00', 60);
    expect(validarSoltar(inicio, fin, { ...base, ahora: new Date('2026-11-10T16:00:00Z') })).toBe('PASADO');
  });
  it('rechaza fuera de la jornada, incluido el almuerzo', () => {
    expect(validarSoltar(...Object.values(lima('07:00', 60)) as [string, string], base)).toBe('FUERA_DE_JORNADA');
    expect(validarSoltar(...Object.values(lima('12:00', 60)) as [string, string], base)).toBe('FUERA_DE_JORNADA');
    expect(validarSoltar(...Object.values(lima('11:30', 60)) as [string, string], base)).toBe('FUERA_DE_JORNADA'); // cruza el almuerzo
  });
  it('rechaza si el técnico no trabaja o está ausente', () => {
    const { inicio, fin } = lima('09:00', 60);
    expect(validarSoltar(inicio, fin, { ...base, intervalos: undefined })).toBe('FUERA_DE_JORNADA');
  });
  it('rechaza una especialidad que el técnico no tiene', () => {
    const { inicio, fin } = lima('09:00', 60);
    expect(validarSoltar(inicio, fin, { ...base, especialidadRequerida: 'INSTALACION' })).toBe('ESPECIALIDAD');
  });
  it('rechaza el choque con otra visita, pero no consigo misma', () => {
    const otra = { visita_id: 'V1', ...lima('09:00', 60) };
    const { inicio, fin } = lima('09:30', 60);
    expect(validarSoltar(inicio, fin, { ...base, ocupadas: [otra] })).toBe('CHOCA');
    expect(validarSoltar(inicio, fin, { ...base, ocupadas: [otra], ignorarVisitaId: 'V1' })).toBeNull();
  });
  it('permite visitas pegadas una tras otra', () => {
    const otra = { visita_id: 'V1', ...lima('09:00', 60) };
    const { inicio, fin } = lima('10:00', 60);
    expect(validarSoltar(inicio, fin, { ...base, ocupadas: [otra] })).toBeNull();
  });
  it('rechaza duraciones fuera de 30 min a 4 h o que no sean múltiplos de 30', () => {
    expect(validarSoltar(...Object.values(lima('09:00', 15)) as [string, string], base)).toBe('DURACION');
    expect(validarSoltar(...Object.values(lima('09:00', 45)) as [string, string], base)).toBe('DURACION');
    expect(validarSoltar(...Object.values(lima('09:00', 270)) as [string, string], base)).toBe('DURACION');
  });
});
