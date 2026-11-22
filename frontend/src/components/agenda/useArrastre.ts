import { useCallback, useEffect, useRef, useState, type PointerEvent as EventoPuntero } from 'react';
import { ALTO_HORA, HORA_FIN, HORA_INICIO } from '../Calendario';
import { horaDesdeY, yDesdeHora, type Motivo } from './dnd';

/** Lo que se está arrastrando: una visita ya programada o una orden de la bandeja. */
export interface Carga {
  tipo: 'visita' | 'orden';
  id: string;
  titulo: string;
  subtitulo?: string;
  duracionMin: number;
  /** Distancia vertical entre el puntero y la parte de arriba del bloque al agarrarlo. */
  offsetY: number;
}

export interface Soltado { tecnico_id: string; fecha: string; hora: string }
export interface Destino extends Soltado { top: number; alto: number; valido: boolean; motivo: Motivo | null }

interface Opciones {
  /** Motivo por el que no cabe, o null. Solo ayuda visual. */
  evaluar: (carga: Carga, donde: Soltado) => Motivo | null;
  onSoltar: (carga: Carga, destino: Destino) => void;
  /** Se soltó sobre una zona que no cabe. */
  onInvalido?: (carga: Carga, destino: Destino) => void;
}

const UMBRAL_RATON = 4;
const PULSACION_LARGA_MS = 250;
const BORDE_PX = 48;
const VELOCIDAD_PX = 14;

/** Arrastrar y soltar con Pointer Events: ratón (al mover unos píxeles) y táctil (con pulsación larga,
    para no bloquear el desplazamiento de la página). Se ajusta a bloques de 30 minutos. Escape cancela. */
export function useArrastre(opciones: Opciones) {
  const ops = useRef(opciones);
  useEffect(() => { ops.current = opciones; });

  const [activo, setActivo] = useState<{ carga: Carga; x: number; y: number } | null>(null);
  const [destino, setDestino] = useState<Destino | null>(null);
  const reciente = useRef(false);
  const detener = useRef<(() => void) | null>(null);

  useEffect(() => () => detener.current?.(), []);

  const empezar = useCallback((e: EventoPuntero<HTMLElement>, carga: Carga) => {
    if (e.button !== 0 || detener.current) return;
    const esAsa = e.target instanceof Element && Boolean(e.target.closest('.asa-arrastre'));
    const tactil = e.pointerType === 'touch' && !esAsa;
    const origen = { x: e.clientX, y: e.clientY };
    let ultimo = origen;
    let arrastrando = false;
    let marca = '';
    let temporizador: ReturnType<typeof setTimeout> | undefined;
    let intervalo: ReturnType<typeof setInterval> | undefined;

    const calcular = (): Destino | null => {
      const columna = document.elementsFromPoint(ultimo.x, ultimo.y)
        .find((n): n is HTMLElement => n instanceof HTMLElement && n.dataset.colTecnico !== undefined);
      if (!columna) return null;
      const caja = columna.getBoundingClientRect();
      const hora = horaDesdeY(ultimo.y - caja.top - carga.offsetY, ALTO_HORA, HORA_INICIO, HORA_FIN, carga.duracionMin);
      const donde = { tecnico_id: columna.dataset.colTecnico!, fecha: columna.dataset.colFecha ?? '', hora };
      const motivo = ops.current.evaluar(carga, donde);
      return { ...donde, top: yDesdeHora(hora, ALTO_HORA, HORA_INICIO), alto: (carga.duracionMin / 60) * ALTO_HORA, valido: motivo === null, motivo };
    };

    const refrescar = () => {
      setActivo({ carga, x: ultimo.x, y: ultimo.y });
      const d = calcular();
      const nueva = d ? `${d.tecnico_id}|${d.fecha}|${d.hora}|${d.valido}` : '';
      if (nueva !== marca) { marca = nueva; setDestino(d); }
    };

    const bloquearDesplazamiento = (ev: Event) => { if (ev.cancelable) ev.preventDefault(); };
    const bloquearMenu = (ev: Event) => ev.preventDefault();

    const activar = () => {
      arrastrando = true;
      window.addEventListener('touchmove', bloquearDesplazamiento, { passive: false });
      document.body.style.userSelect = 'none';
      // Al acercarse a un borde, la lista y la página se desplazan solas.
      intervalo = setInterval(() => {
        const lista = document.querySelector<HTMLElement>('[data-scroll-agenda]');
        if (lista) {
          const c = lista.getBoundingClientRect();
          if (ultimo.x > c.right - BORDE_PX) lista.scrollLeft += VELOCIDAD_PX;
          else if (ultimo.x < c.left + BORDE_PX) lista.scrollLeft -= VELOCIDAD_PX;
        }
        if (ultimo.y > window.innerHeight - BORDE_PX) window.scrollBy(0, VELOCIDAD_PX);
        else if (ultimo.y < BORDE_PX) window.scrollBy(0, -VELOCIDAD_PX);
        refrescar();
      }, 32);
      refrescar();
    };

    const terminar = (soltar: boolean) => {
      clearTimeout(temporizador);
      clearInterval(intervalo);
      window.removeEventListener('pointermove', mover);
      window.removeEventListener('pointerup', alSoltar);
      window.removeEventListener('pointercancel', alCancelar);
      window.removeEventListener('keydown', alTeclear);
      window.removeEventListener('contextmenu', bloquearMenu);
      window.removeEventListener('touchmove', bloquearDesplazamiento);
      document.body.style.userSelect = '';
      detener.current = null;
      if (arrastrando) {
        const final = soltar ? calcular() : null;
        reciente.current = true; // El clic que sigue a soltar no debe abrir el diálogo del bloque.
        setTimeout(() => { reciente.current = false; }, 80);
        if (final?.valido) ops.current.onSoltar(carga, final);
        else if (final) ops.current.onInvalido?.(carga, final);
      }
      setActivo(null);
      setDestino(null);
    };

    function mover(ev: PointerEvent) {
      ultimo = { x: ev.clientX, y: ev.clientY };
      if (!arrastrando) {
        const distancia = Math.hypot(ultimo.x - origen.x, ultimo.y - origen.y);
        if (tactil) { if (distancia > 10) terminar(false); return; } // Se está desplazando, no arrastrando.
        if (distancia < UMBRAL_RATON) return;
        activar();
      }
      refrescar();
    }
    function alSoltar() { terminar(true); }
    function alCancelar() { terminar(false); }
    function alTeclear(ev: KeyboardEvent) { if (ev.key === 'Escape') terminar(false); }

    window.addEventListener('pointermove', mover);
    window.addEventListener('pointerup', alSoltar);
    window.addEventListener('pointercancel', alCancelar);
    window.addEventListener('keydown', alTeclear);
    window.addEventListener('contextmenu', bloquearMenu);
    detener.current = () => terminar(false);
    if (tactil) temporizador = setTimeout(activar, PULSACION_LARGA_MS);
  }, []);

  return {
    arrastrando: activo?.carga ?? null,
    puntero: activo ? { x: activo.x, y: activo.y } : null,
    destino,
    empezar,
    /** Verdadero justo después de soltar: sirve para ignorar el clic que el navegador dispara. */
    huboArrastre: () => reciente.current,
  };
}
