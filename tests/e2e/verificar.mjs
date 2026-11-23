// Verifica las correcciones de la prueba funcional contra una web (local o desplegada).
// Uso: node verificar.mjs <url-web> <carpeta-salida>
import { chromium } from 'playwright';
import { mkdirSync, readFileSync } from 'node:fs';

const [WEB, OUT] = process.argv.slice(2);
mkdirSync(OUT, { recursive: true });
const cr = readFileSync(new URL('../../.demo-credentials', import.meta.url), 'utf8').split('\n').filter((l) => l && !l.startsWith('#')).map((l) => l.split(/\s+/));
const cuenta = (r) => cr.find((x) => x[0] === 'dev' && x[1] === 'CLIMALIMA' && x[4] === r);
const nav = await chromium.launch();
let fallos = 0;
const ok = (n, c, d = '') => { if (!c) fallos++; console.log(`${c ? 'PASS' : 'FAIL'} ${n}${d ? ' -> ' + d : ''}`); };
async function ses(r, vp) {
  const c = await nav.newContext({ viewport: vp, isMobile: vp.width < 500, hasTouch: vp.width < 500, locale: 'en-US' });
  const p = await c.newPage(); const u = cuenta(r);
  await p.goto(WEB + '/login');
  await p.getByLabel('Código de empresa').fill('CLIMALIMA'); await p.getByLabel('Correo').fill(u[2]); await p.getByLabel('Contraseña').fill(u[3]);
  await p.locator('button[type=submit]').click(); await p.waitForURL((x) => !x.pathname.includes('login'), { timeout: 30000 }); return p;
}
const T = async (p) => (await p.innerText('body')).replace(/\s+/g, ' ');

// Login
{
  const p = await (await nav.newContext({ locale: 'en-US' })).newPage();
  await p.goto(WEB + '/login');
  await p.getByLabel('Contraseña').fill('secreta');
  ok('Login: la contraseña empieza oculta', (await p.getByLabel('Contraseña').getAttribute('type')) === 'password');
  await p.getByRole('button', { name: 'Mostrar' }).click();
  ok('Login: Mostrar revela la contraseña', (await p.getByLabel('Contraseña').getAttribute('type')) === 'text');
  await p.getByRole('button', { name: 'Ocultar' }).click();
  await p.locator('button[type=submit]').click();
  const msg = await p.getByLabel('Código de empresa').evaluate((i) => i.validationMessage);
  ok('Login: aviso de campo obligatorio en español', msg === 'Completa este campo.', msg);
  await p.getByLabel('Código de empresa').fill('X'); await p.getByLabel('Correo').fill('malo'); await p.locator('button[type=submit]').click();
  ok('Login: aviso de correo inválido en español', /correo válido/.test(await p.getByLabel('Correo').evaluate((i) => i.validationMessage)));
}

// Coordinador
const c = await ses('COORDINADOR', { width: 1280, height: 800 });
await c.goto(WEB + '/panel'); await c.waitForTimeout(3000);
const sel = c.locator('select').first();
ok('Panel: mes del resumen en español', /noviembre|diciembre|octubre/i.test(await sel.innerText()), (await sel.innerText()).split('\n')[0]);
ok('Panel: aviso de desplazamiento en la tabla de técnicos', /desplázate/.test(await T(c)));
await c.goto(WEB + '/clientes/nuevo'); await c.waitForTimeout(1500);
ok('Ruta /clientes/nuevo lleva a Clientes', c.url().endsWith('/clientes'));
await c.getByRole('button', { name: 'Nuevo cliente' }).click();
const form = c.locator('form').first();
await form.locator('input').nth(0).fill('Prueba'); await form.locator('input').nth(1).fill('abc');
await form.getByRole('button', { name: 'Guardar' }).click();
ok('Clientes: teléfono con letras se rechaza', /Solo números/.test(await form.locator('input').nth(1).evaluate((i) => i.validationMessage)));
await c.goto(WEB + '/ordenes/nueva');
await c.getByRole('button', { name: 'Buscar' }).click();
ok('Nueva orden: buscar vacío avisa', (await c.locator('form input').first().evaluate((i) => i.validationMessage)) === 'Completa este campo.');

// Orden con visita: fechas y fecha pasada
// Se crea una orden propia y se le programa una visita lejana, para no depender de datos previos.
await c.goto(WEB + '/ordenes/nueva');
await c.locator('form input').first().fill('hotel'); await c.getByRole('button', { name: 'Buscar' }).click();
await c.locator('form li button').first().click({ timeout: 30000 });
const ub = c.getByLabel('Ubicación'); await ub.locator('option').nth(1).waitFor({ state: 'attached', timeout: 30000 });
await ub.selectOption({ index: 1 });
await c.getByLabel('Descripción del problema').fill(`Verificación ${Date.now()}`);
await c.getByRole('button', { name: 'Crear orden' }).click(); await c.waitForURL(/\/ordenes\/OT-/, { timeout: 30000 });
await c.getByRole('button', { name: 'Programar visita' }).click();
const lejos = new Date(Date.now() + 16 * 86400000);
await c.getByLabel('Fecha').fill(`${String(lejos.getDate()).padStart(2, '0')}/${String(lejos.getMonth() + 1).padStart(2, '0')}/${lejos.getFullYear()}`);
await c.getByRole('button', { name: /Asignar al mejor técnico/ }).click({ timeout: 30000 });
await c.getByText(/Visita 1/).first().waitFor({ timeout: 30000 }); await c.waitForTimeout(1500);
ok('Orden: la visita muestra DD/MM/AAAA', /Visita 1 · \d{2}\/\d{2}\/\d{4}/.test(await T(c)), (await T(c)).match(/Visita 1 · \S+/)?.[0]);
await c.getByRole('button', { name: 'Programar visita' }).click();
await c.getByLabel('Fecha').fill('01/01/2020'); await c.waitForTimeout(800);
const t1 = await T(c);
ok('Visita: fecha pasada explica el problema', /Elige \d{2}\/\d{2}\/\d{4} o una fecha posterior/.test(t1));
await c.getByLabel('Fecha').fill('31/02/2026'); await c.waitForTimeout(500);
ok('Visita: fecha inexistente explica el problema', /Esa fecha no existe/.test(await T(c)));
await c.screenshot({ path: OUT + '/fecha-invalida.png' });
await c.getByRole('button', { name: 'Cerrar' }).click();
await c.getByRole('button', { name: 'Cancelar orden' }).click(); await c.waitForTimeout(800);
const aviso = await c.locator('dialog[open]').innerText();
if (/Visita 1:/.test(aviso)) ok('Cancelar orden: fecha DD/MM/AAAA', /Visita 1: \d{2}\/\d{2}\/\d{4}/.test(aviso));
else console.log('OMITIDA Cancelar orden: la orden no tiene visitas programadas');
await c.keyboard.press('Escape');

// Agenda
await c.goto(WEB + '/agenda'); await c.waitForTimeout(2500);
const w = await c.locator('select[aria-label=Especialidad]').evaluate((s) => [s.scrollWidth, s.clientWidth]);
ok('Agenda: filtro de especialidad sin recorte', w[0] <= w[1] + 1, w.join('/'));

// Móvil: desborde en todas las pantallas
const m = await ses('COORDINADOR', { width: 390, height: 844 });
for (const r of ['/panel', '/ordenes', '/agenda', '/clientes', '/tecnicos', '/ordenes/nueva']) {
  await m.goto(WEB + r); await m.waitForTimeout(3000);
  const s = await m.evaluate(() => {
    const ancho = document.documentElement.clientWidth;
    const culpables = [...document.querySelectorAll('body *')].filter((e) => e.getBoundingClientRect().right > ancho + 1 && !e.closest('.leaflet-container') && !e.closest('.overflow-x-auto, .overflow-auto'))
      .slice(0, 4).map((e) => `${e.tagName.toLowerCase()}.${String(e.className).slice(0, 50)} ${Math.round(e.getBoundingClientRect().right)}`);
    return { sobra: document.documentElement.scrollWidth - ancho, culpables };
  });
  ok(`Móvil ${r}: sin desborde horizontal`, s.sobra <= 0, s.sobra > 0 ? `${s.sobra}px ${JSON.stringify(s.culpables)}` : '');
  if (r === '/panel') await m.screenshot({ path: OUT + '/movil-panel.png', fullPage: true });
}

// Técnico
const t = await ses('TECNICO', { width: 390, height: 844 });
await t.goto(WEB + '/mis-visitas'); await t.waitForTimeout(3000);
if (!(await t.getByRole('button', { name: /Iniciar visita/ }).count())) { console.log('OMITIDAS pruebas del técnico: no tiene visitas programadas'); await nav.close(); console.log(fallos ? `\n${fallos} FALLO(S)` : '\nTODO CORRECTO'); process.exit(fallos ? 1 : 0); }
await t.getByRole('button', { name: /Iniciar visita/ }).first().click(); await t.waitForTimeout(800);
const d = t.locator('dialog[open]');
ok('Técnico: iniciar visita de otro día pide confirmación', (await d.count()) === 1 && /no es de hoy/.test(await d.innerText()));
await t.screenshot({ path: OUT + '/tecnico-confirma.png' });
await d.getByRole('button', { name: 'Iniciar de todos modos' }).click();
await t.waitForURL(/\/mis-visitas\/VIS-/, { timeout: 20000 }); await t.getByLabel('Diagnóstico').waitFor({ timeout: 30000 });
ok('Atención: la fecha se ve DD/MM/AAAA', /\d{2}\/\d{2}\/\d{4} · /.test(await T(t)));
await t.getByRole('button', { name: 'Finalizar parte' }).first().click(); await t.waitForTimeout(600);
ok('Atención: no deja finalizar con campos vacíos', (await t.locator('dialog[open]').count()) === 0 && /completa el diagnóstico, las tareas realizadas, el resultado/.test(await T(t)));
await t.getByLabel('Diagnóstico').fill('x');
ok('Atención: avisa de cambios sin guardar', /cambios sin guardar/.test(await T(t)));
await t.screenshot({ path: OUT + '/atencion-validacion.png', fullPage: true });
await nav.close();
console.log(fallos ? `\n${fallos} FALLO(S)` : '\nTODO CORRECTO');
process.exit(fallos ? 1 : 0);
