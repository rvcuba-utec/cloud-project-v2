// sessionStorage y no localStorage: cada pestaña conserva su propia sesión,
// y la demo usa coordinador y técnico en pestañas distintas.
const CLAVE = 'trazora_token';

export const obtenerToken = () => sessionStorage.getItem(CLAVE);
export const guardarToken = (token: string) => sessionStorage.setItem(CLAVE, token);
export const borrarToken = () => sessionStorage.removeItem(CLAVE);
