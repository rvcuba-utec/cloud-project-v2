import { borrarToken, obtenerToken } from '../auth/sesion';

export type Servicio = 'usuarios' | 'clientes' | 'tecnicos' | 'analitica' | 'ordenes' | 'agenda' | 'partes';

const env = import.meta.env;
const BASES: Record<Servicio, string | undefined> = {
  usuarios: env.VITE_API_USUARIOS,
  clientes: env.VITE_API_CLIENTES,
  tecnicos: env.VITE_API_TECNICOS,
  analitica: env.VITE_API_ANALITICA,
  ordenes: env.VITE_API_ORDENES,
  agenda: env.VITE_API_AGENDA,
  partes: env.VITE_API_PARTES,
};

export class ApiError extends Error {
  readonly status: number;
  readonly codigo: string;
  readonly detalle: Record<string, unknown>;

  constructor(status: number, codigo: string, mensaje: string, detalle: Record<string, unknown> = {}) {
    super(mensaje);
    this.status = status;
    this.codigo = codigo;
    this.detalle = detalle;
  }
}

export interface Opciones {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;
  idempotencyKey?: string;
}

let alExpirarSesion: () => void = () => {};
export const configurarSesionExpirada = (accion: () => void) => {
  alExpirarSesion = accion;
};

export async function api<T>(servicio: Servicio, ruta: string, opciones: Opciones = {}): Promise<T> {
  const base = BASES[servicio];
  if (!base) throw new ApiError(0, 'SIN_CONFIGURAR', `Falta la URL del servicio ${servicio}`);

  const token = obtenerToken();
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (opciones.idempotencyKey) headers['Idempotency-Key'] = opciones.idempotencyKey;

  let respuesta: Response;
  try {
    respuesta = await fetch(`${base}${ruta}`, {
      method: opciones.method ?? 'GET',
      headers,
      body: opciones.body === undefined ? undefined : JSON.stringify(opciones.body),
    });
  } catch {
    throw new ApiError(0, 'SIN_CONEXION', 'No se pudo conectar con el servidor');
  }

  const texto = await respuesta.text();
  let datos: { error?: { codigo?: string; mensaje?: string; detalle?: Record<string, unknown> } } | undefined;
  try {
    datos = texto ? JSON.parse(texto) : undefined;
  } catch {
    datos = undefined;
  }

  // Un 401 durante el login significa credenciales incorrectas, no sesión vencida.
  if (respuesta.status === 401 && token) {
    borrarToken();
    alExpirarSesion();
  }
  if (!respuesta.ok) {
    const error = datos?.error;
    throw new ApiError(
      respuesta.status,
      error?.codigo ?? 'ERROR',
      error?.mensaje ?? 'Ocurrió un error inesperado',
      error?.detalle,
    );
  }
  return datos as T;
}
