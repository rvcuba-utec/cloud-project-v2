// Recorrido completo en un navegador real contra lo desplegado.
// Uso: node recorrido.mjs <url-web>   (lee las cuentas de .demo-credentials y no las imprime)
import { chromium } from 'playwright';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';

const WEB = process.argv[2];
const STAGE = process.env.STAGE ?? 'dev';
const RESULTADOS = new URL('./resultados/', import.meta.url).pathname;
mkdirSync(RESULTADOS, { recursive: true });
const cuentas = readFileSync(new URL('../../.demo-credentials', import.meta.url), 'utf8')
  .split('\n').filter((l) => l && !l.startsWith('#')).map((l) => l.split(/\s+/));
const cuenta = (tenant, rol) => {
  const f = cuentas.find((c) => c[0] === STAGE && c[1] === tenant && c[4] === rol);
  return { tenant, email: f[2], password: f[3] };
};

const problemas = [];
function vigilar(pagina, nombre) {
  pagina.on('pageerror', (e) => problemas.push(`${nombre}: excepción ${e.message}`));
  pagina.on('console', (m) => {
    if (m.type() === 'error' && !/status of 40[49]/.test(m.text())) problemas.push(`${nombre}: consola ${m.text().slice(0, 300)}`);
  });
  pagina.on('dialog', (d) => d.accept());
}
async function entrar(contexto, nombre, datos) {
  const p = await contexto.newPage();
  vigilar(p, nombre);
  await p.goto(`${WEB}/login`);
  await p.getByLabel('Código de empresa').fill(datos.tenant);
  await p.getByLabel('Correo').fill(datos.email);
  await p.getByLabel('Contraseña').fill(datos.password);
  await p.locator('button[type=submit]').click();
  await p.waitForURL((u) => !u.pathname.includes('/login'), { timeout: 30000 });
  return p;
}
async function sinDesborde(p, nombre) {
  const sobra = await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  if (sobra > 0) problemas.push(`${nombre}: ${sobra}px de desborde horizontal`);
}
const paso = (t) => console.log(`- ${t}`);
const foto = (p, n) => p.screenshot({ path: `${RESULTADOS}${n}.png`, fullPage: true });

const navegador = await chromium.launch();
let salida = 0;
try {
  const escritorio = await navegador.newContext({ viewport: { width: 1280, height: 800 } });
  const coord = await entrar(escritorio, 'coordinador', cuenta('CLIMALIMA', 'COORDINADOR'));
  await coord.waitForURL('**/panel');
  await coord.getByRole('heading', { name: 'Rendimiento de técnicos' }).waitFor();
  await coord.getByText('Órdenes abiertas').waitFor();
  await foto(coord, '1-panel');
  paso('Coordinador entra y ve el panel');

  await coord.goto(`${WEB}/ordenes/nueva`);
  const descripcion = `Recorrido navegador ${Date.now()}`;
  await coord.locator('form input').first().fill('hotel');
  await coord.getByRole('button', { name: 'Buscar' }).click();
  await coord.locator('form li button').first().click({ timeout: 30000 });
  const ubicacion = coord.getByLabel('Ubicación');
  await ubicacion.locator('option').nth(1).waitFor({ state: 'attached', timeout: 30000 });
  await ubicacion.selectOption({ index: 1 });
  await coord.getByLabel('Tipo de servicio').selectOption('REPARACION');
  await coord.getByLabel('Descripción del problema').fill(descripcion);
  await coord.getByRole('button', { name: 'Crear orden' }).click();
  await coord.waitForURL(/\/ordenes\/OT-/, { timeout: 30000 });
  const urlOrden = coord.url();
  paso('Crea la orden');

  await coord.getByRole('button', { name: 'Programar visita' }).click();
  const fecha = new Date(Date.now() + 26 * 86400000 - 5 * 3600000).toISOString().slice(0, 10);
  await coord.getByLabel('Fecha').fill(fecha);
  const fila = coord.locator('li', { hasText: 'Carlos Quispe' }).first();
  await fila.waitFor({ timeout: 30000 });
  await fila.locator('button').last().click();
  await coord.getByText(/Visita 1/).first().waitFor({ timeout: 30000 });
  await coord.getByText('Programada', { exact: true }).first().waitFor({ timeout: 30000 });
  await foto(coord, '2-orden-programada');
  paso('Programa la visita con el técnico sugerido o elegido');

  const telefono = await navegador.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const tec = await entrar(telefono, 'tecnico', cuenta('CLIMALIMA', 'TECNICO'));
  await tec.waitForURL('**/mis-visitas');
  const visita = tec.locator('li', { hasText: descripcion });
  while (!(await visita.count())) {
    const siguiente = tec.getByRole('button', { name: 'Siguiente' });
    await tec.waitForTimeout(1500);
    if (await visita.count()) break;
    if (await siguiente.isDisabled()) throw new Error('El técnico no ve la visita');
    await siguiente.click();
  }
  await sinDesborde(tec, 'mis-visitas');
  await visita.getByRole('button', { name: 'Iniciar visita' }).click();
  await tec.waitForURL(/\/mis-visitas\/VIS-/);
  await tec.getByLabel('Diagnóstico').waitFor({ timeout: 30000 });
  paso('Técnico, en teléfono, inicia la visita');

  // Rechazo en el navegador: más de 5 MB.
  await tec.locator('input[type=file]').setInputFiles({ name: 'grande.jpg', mimeType: 'image/jpeg', buffer: Buffer.alloc(5 * 1024 * 1024 + 1) });
  await tec.getByText('La foto supera los 5 MB.').waitFor();
  // Foto real: JPEG mínimo válido de 1×1.
  const jpeg = Buffer.from('/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wAALCAABAAEBAREA/8QAFAABAAAAAAAAAAAAAAAAAAAAA//EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AN//Z', 'base64');
  await tec.locator('input[type=file]').setInputFiles({ name: 'evidencia.jpg', mimeType: 'image/jpeg', buffer: jpeg });
  const img = tec.locator('img[alt="evidencia.jpg"]');
  await img.waitFor({ timeout: 40000 });
  await tec.waitForFunction(() => { const i = document.querySelector('img[alt="evidencia.jpg"]'); return i && i.complete && i.naturalWidth > 0; }, null, { timeout: 15000 });
  paso('Sube una foto real a S3 (CORS del bucket) y la ve con una URL temporal; más de 5 MB se rechaza');

  await tec.getByLabel('Diagnóstico').fill('Filtro obstruido');
  await tec.getByLabel(/Tareas realizadas/).fill('Limpieza de filtro\nPrueba de funcionamiento');
  await tec.getByLabel('Resultado').selectOption('RESUELTO');
  await sinDesborde(tec, 'atencion');
  await foto(tec, '3-atencion-telefono');
  await tec.getByRole('button', { name: 'Finalizar parte' }).click();
  await tec.getByText('Finalizada', { exact: true }).waitFor({ timeout: 40000 });
  await foto(tec, '4-parte-finalizado');
  paso('Finaliza el parte y la visita pasa a Finalizada por eventos');

  await coord.goto(urlOrden);
  await coord.getByRole('button', { name: 'Cerrar orden' }).waitFor({ timeout: 40000 });
  await coord.getByRole('link', { name: 'Visita 1' }).waitFor();
  await coord.getByRole('button', { name: 'Cerrar orden' }).click();
  await coord.getByText('Cerrada', { exact: true }).first().waitFor({ timeout: 30000 });
  await foto(coord, '5-orden-cerrada');
  paso('Coordinador ve el parte y cierra la orden');

  const adminCtx = await navegador.newContext({ viewport: { width: 1280, height: 800 } });
  const admin = await entrar(adminCtx, 'admin', cuenta('CLIMALIMA', 'ADMIN'));
  await admin.goto(`${WEB}/usuarios`);
  await admin.getByRole('heading', { name: 'Usuarios y roles' }).waitFor();
  await admin.locator('tbody tr').first().waitFor({ timeout: 30000 });
  paso('Administrador ve usuarios y roles');
  await coord.goto(`${WEB}/usuarios`);
  await coord.waitForURL((u) => !u.pathname.endsWith('/usuarios'), { timeout: 10000 });
  paso('El coordinador no puede entrar a usuarios');

  // Otras pantallas, también a ancho de teléfono.
  const coordMovil = await entrar(await navegador.newContext({ viewport: { width: 390, height: 844 }, isMobile: true }), 'coordinador-movil', cuenta('CLIMALIMA', 'COORDINADOR'));
  for (const ruta of ['panel', 'ordenes', 'agenda', 'clientes', 'tecnicos']) {
    await coordMovil.goto(`${WEB}/${ruta}`);
    await coordMovil.waitForTimeout(2500);
    await sinDesborde(coordMovil, ruta);
    await foto(coordMovil, `movil-${ruta}`);
  }
  paso('Pantallas revisadas a 390 px');
} catch (e) {
  salida = 1;
  console.error(`FALLÓ: ${e.message.split('\n').slice(0, 4).join(' | ')}`);
  for (const c of navegador.contexts()) for (const [i, p] of c.pages().entries()) {
    await p.screenshot({ path: `${RESULTADOS}fallo-${Math.random().toString(36).slice(2, 6)}-${i}.png` }).catch(() => {});
  }
}
if (problemas.length) { salida = 1; console.error(`Problemas:\n  ${problemas.join('\n  ')}`); }
writeFileSync(`${RESULTADOS}ultima.txt`, salida ? 'fallo\n' : 'correcto\n');
await navegador.close();
console.log(salida ? 'Recorrido con fallos' : 'Recorrido correcto');
process.exit(salida);
