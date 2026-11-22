import { useCallback, useRef, useState } from 'react';
import { useMutation, useQueryClient, type QueryClient, type QueryKey } from '@tanstack/react-query';
import { ApiError } from '../../api/client';
import { agenda, type Orden, type Pagina, type Visita } from '../../api/recursos';
import { horaLima, lunesDe } from '../formato';
import type { AvisoToast } from '../ui';
import { duracionDe, moverBloque } from './dnd';

export interface Movimiento {
  visita: Visita;
  tecnico_id: string;
  tecnico_nombre: string;
  fecha: string;
  hora: string;
  esDeshacer?: boolean;
}

export interface Programacion {
  orden: Orden;
  tecnico_id: string;
  tecnico_nombre: string;
  fecha: string;
  hora: string;
  duracionMin: number;
}

const BASES = ['visitas-dia', 'visitas-semana'];
const A_REFRESCAR = ['visitas-dia', 'visitas-semana', 'alertas', 'tecnicos-disponibles', 'jornadas', 'dashboard', 'mapa', 'bandeja-ordenes', 'ordenes'];

type Instantanea = [QueryKey, Visita[]][];

/** Solo las listas de visitas (arreglos): el Panel guarda otra forma con la misma clave base. */
function instantanea(c: QueryClient): Instantanea {
  return BASES.flatMap((base) => c.getQueriesData<Visita[]>({ queryKey: [base] })
    .filter((par): par is [QueryKey, Visita[]] => Array.isArray(par[1])));
}

/** Mueve la visita en las listas ya cargadas: sale de donde estaba y entra donde cae. */
function aplicar(c: QueryClient, m: Movimiento, inicio: string, fin: string) {
  const nueva: Visita = { ...m.visita, tecnico_id: m.tecnico_id, tecnico_nombre: m.tecnico_nombre, fecha: m.fecha, inicio, fin, requiere_reprogramacion: false };
  instantanea(c).forEach(([clave, datos]) => {
    const pertenece = clave[0] === 'visitas-dia'
      ? clave[1] === m.fecha
      : clave[1] === m.tecnico_id && clave[2] === lunesDe(m.fecha);
    const resto = datos.filter((v) => v.visita_id !== m.visita.visita_id);
    c.setQueryData(clave, pertenece ? [...resto, nueva] : resto);
  });
}

const texto = (e: unknown, defecto: string) => (e instanceof ApiError ? e.message : defecto);

/** Reprogramar y programar visitas desde la Agenda. Las llamadas son las mismas de siempre:
    POST /visitas/{id}/reprogramar y POST /visitas. Reprogramar es optimista: el bloque se mueve al
    instante y vuelve a su sitio si el backend lo rechaza (409, jornada, etc.). */
export function useMoverVisita() {
  const consultas = useQueryClient();
  const [aviso, setAviso] = useState<AvisoToast | null>(null);
  const [enVuelo, setEnVuelo] = useState<ReadonlySet<string>>(new Set());
  const contador = useRef(0);

  const mostrar = useCallback((a: Omit<AvisoToast, 'id'>) => { contador.current += 1; setAviso({ ...a, id: contador.current }); }, []);
  const cerrar = useCallback(() => setAviso(null), []);
  const refrescar = useCallback(() => { A_REFRESCAR.forEach((k) => consultas.invalidateQueries({ queryKey: [k] })); }, [consultas]);
  const marcar = (id: string, dentro: boolean) => setEnVuelo((s) => { const n = new Set(s); if (dentro) n.add(id); else n.delete(id); return n; });

  const mover = useMutation({
    mutationFn: (m: Movimiento) => {
      const h = moverBloque(m.fecha, m.hora, duracionDe(m.visita.inicio, m.visita.fin));
      return agenda.reprogramar(m.visita.visita_id, { tecnico_id: m.tecnico_id, inicio: h.inicio, fin: h.fin, version: m.visita.version });
    },
    onMutate: async (m) => {
      await Promise.all(BASES.map((b) => consultas.cancelQueries({ queryKey: [b] })));
      const previo = instantanea(consultas);
      const h = moverBloque(m.fecha, m.hora, duracionDe(m.visita.inicio, m.visita.fin));
      aplicar(consultas, m, h.inicio, h.fin);
      marcar(m.visita.visita_id, true);
      return { previo };
    },
    onError: (e, _m, ctx) => {
      ctx?.previo.forEach(([clave, datos]) => consultas.setQueryData(clave, datos));
      mostrar({ tono: 'error', texto: `La visita volvió a su lugar. ${texto(e, 'No se pudo reprogramar.')}` });
    },
    onSuccess: (nueva, m) => {
      // Actualiza versión y campos reales devueltos por el backend antes de que termine el refresco.
      aplicar(consultas, { ...m, visita: nueva }, nueva.inicio, nueva.fin);
      const original = m.visita;
      // El backend no tiene «deshacer»: se reprograma de vuelta al horario y técnico anteriores.
      // Si la visita estaba sin técnico no se ofrece: volver a quien se ausentó no es posible.
      const puedeDeshacer = !m.esDeshacer && !original.requiere_reprogramacion;
      mostrar({
        tono: 'bien',
        texto: m.esDeshacer ? 'Visita devuelta a su horario anterior.' : `Visita reprogramada con ${m.tecnico_nombre} a las ${m.hora}.`,
        deshacer: puedeDih(puedeDeshacer, () => mover.mutate({
          visita: nueva, tecnico_id: original.tecnico_id, tecnico_nombre: original.tecnico_nombre,
          fecha: original.fecha, hora: horaLima(original.inicio), esDeshacer: true,
        })),
        enlace: { a: `/ordenes/${original.orden_id}`, texto: 'Abrir la orden' },
      });
    },
    onSettled: (_r, _e, m) => { marcar(m.visita.visita_id, false); refrescar(); },
  });

  const programar = useMutation({
    mutationFn: (p: Programacion) => {
      const h = moverBloque(p.fecha, p.hora, p.duracionMin);
      // Cada soltado es un intento distinto: otra clave de idempotencia.
      return agenda.programar({ orden_id: p.orden.orden_id, tecnico_id: p.tecnico_id, inicio: h.inicio, fin: h.fin }, crypto.randomUUID());
    },
    onSuccess: (nueva, p) => {
      // Quita la orden de la bandeja al instante mientras el evento VisitaProgramada actualiza MS3 Órdenes.
      consultas.getQueriesData<Pagina<Orden>>({ queryKey: ['bandeja-ordenes'] }).forEach(([clave, pagina]) => {
        if (pagina?.items) {
          consultas.setQueryData<Pagina<Orden>>(clave, {
            ...pagina,
            items: pagina.items.filter((o) => o.orden_id !== p.orden.orden_id),
          });
        }
      });
      // Añade la visita recién creada a la caché visible sin esperar el refresco.
      instantanea(consultas).forEach(([clave, datos]) => {
        const pertenece = clave[0] === 'visitas-dia'
          ? clave[1] === nueva.fecha
          : clave[1] === nueva.tecnico_id && clave[2] === lunesDe(nueva.fecha);
        if (pertenece) {
          consultas.setQueryData(clave, [...datos.filter((v) => v.visita_id !== nueva.visita_id), nueva]);
        }
      });
      // Revalida la bandeja tras unos segundos cuando MS3 haya procesado el evento SQS.
      setTimeout(() => consultas.invalidateQueries({ queryKey: ['bandeja-ordenes'] }), 3000);
      mostrar({
        tono: 'bien',
        texto: `Visita programada con ${p.tecnico_nombre} a las ${p.hora} para ${p.orden.cliente_nombre}.`,
        enlace: { a: `/ordenes/${p.orden.orden_id}`, texto: 'Abrir la orden' },
      });
    },
    onError: (e) => mostrar({ tono: 'error', texto: `No se programó la visita. ${texto(e, 'Ocurrió un error inesperado.')}` }),
    onSettled: () => {
      ['visitas-dia', 'visitas-semana', 'alertas', 'tecnicos-disponibles', 'jornadas', 'dashboard', 'mapa', 'ordenes']
        .forEach((k) => consultas.invalidateQueries({ queryKey: [k] }));
    },
  });

  return { mover, programar, aviso, mostrar, cerrar, enVuelo, ocupado: mover.isPending || programar.isPending };
}

function puedeDih(permitido: boolean, accion: () => void): (() => void) | undefined {
  return permitido ? accion : undefined;
}
