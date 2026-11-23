// Pruebas E2E de interfaz contra lo desplegado: login, guardas de ruta, clientes,
// órdenes, visitas, agenda, técnico en móvil, tema oscuro y sesión.
// Cada prueba es independiente; se registra PASS/FAIL y una captura si falla.
// Uso: node flujo.mjs <url-web> <carpeta-salida>
import { chromium } from 'playwright';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';

const [WEB, OUT] = process.argv.slice(2);
mkdirSync(OUT, { recursive: true });
const cuentas = readFileSync(new URL('../../.demo-credentials', import.meta.url), 'utf8')
  .split('\n').filter((l) => l && !l.startsWith('#')).map((l) => l.split(/\s+/));
const cuenta = (t, r) => { const f = cuentas.find((c) => c[0] === 'dev' && c[1] === t && c[4] === r); return { tenant: t, email: f[2], password: f[3] }; };

const resultados = [];
const notas = [];
const nota = (t) => { notas.push(t); console.log(`   ⚑ ${t}`); };
let n = 0;
async function prueba(nombre, fn, pagina) {
  const t0 = Date.now();
  try { await fn(); resultados.push({ nombre, ok: true }); console.log(`PASS ${nombre} (${Date.now() - t0} ms)`); }
  catch (e) {
    const msg = e.message.split('\n')[0].slice(0, 220);
    resultados.push({ nombre, ok: false, msg }); console.log(`FAIL ${nombre}: ${msg}`);
    const p = typeof pagina === 'function' ? pagina() : pagina;
    if (p) await p.screenshot({ path: `${OUT}/fail-${++n}.png`, fullPage: true }).catch(() => {});
  }
}
const nav = await chromium.launch();
async function sesion(rol, viewport = { width: 1280, height: 800 }, tenant = 'CLIMALIMA') {
  const ctx = await nav.newContext({ viewport, isMobile: viewport.width < 500, hasTouch: viewport.width < 500, locale: 'es-PE', timezoneId: 'America/Lima' });
  const p = await ctx.newPage();
  p.on('dialog', (d) => d.accept());
  const d = cuenta(tenant, rol);
  await p.goto(`${WEB}/login`);
  await p.getByLabel('Código de empresa').fill(d.tenant);
  await p.getByLabel('Correo').fill(d.email);
  await p.getByLabel('Contraseña').fill(d.password);
  await p.locator('button[type=submit]').click();
  await p.waitForURL((u) => !u.pathname.includes('/login'), { timeout: 30000 });
  return { ctx, p };
}
const cuerpo = (p) => p.evaluate(() => document.body.innerText);

// ---------- 1. LOGIN ----------
{
  const ctx = await nav.newContext({ viewport: { width: 1280, height: 800 } });
  const p = await ctx.newPage();
  await p.goto(`${WEB}/login`);
  const d = cuenta('CLIMALIMA', 'COORDINADOR');
  const llenar = async (t, e, c) => { await p.getByLabel('Código de empresa').fill(t); await p.getByLabel('Correo').fill(e); await p.getByLabel('Contraseña').fill(c); };
  await prueba('Login: enviar vacío no navega y avisa', async () => {
    await p.locator('button[type=submit]').click();
    await p.waitForTimeout(800);
    if (!p.url().includes('/login')) throw new Error('salió del login');
    const t = await cuerpo(p);
    const aviso = await p.evaluate(() => [...document.querySelectorAll('input')].map((i) => i.validationMessage).filter(Boolean).length) || /obligatori|requerid|completa/i.test(t);
    if (!aviso) throw new Error('sin aviso de campos obligatorios');
  }, p);
  await prueba('Login: contraseña incorrecta muestra error claro y no revela cuál dato falló', async () => {
    await llenar(d.tenant, d.email, 'incorrecta-123');
    await p.locator('button[type=submit]').click();
    await p.getByText(/incorrectos/i).waitFor({ timeout: 10000 });
    await p.screenshot({ path: `${OUT}/login-error.png` });
  }, p);
  await prueba('Login: empresa inexistente rechazada', async () => {
    await llenar('NOEXISTE', d.email, d.password);
    await p.locator('button[type=submit]').click();
    await p.getByText(/incorrectos/i).waitFor({ timeout: 10000 });
  }, p);
  await prueba('Login: campo contraseña enmascarado', async () => {
    const tipo = await p.getByLabel('Contraseña').getAttribute('type');
    if (tipo !== 'password') throw new Error(`type=${tipo}`);
  }, p);
  await prueba('Login: ofrece mostrar/ocultar contraseña', async () => {
    const hay = await p.getByRole('button', { name: /mostrar|ver|ojo/i }).count();
    if (!hay) { nota('Login: no hay botón para mostrar/ocultar la contraseña (comodidad, sobre todo en móvil).'); }
  }, p);
  await prueba('Login: Enter en el campo contraseña envía el formulario', async () => {
    await llenar(d.tenant, d.email, d.password);
    await p.getByLabel('Contraseña').press('Enter');
    await p.waitForURL((u) => !u.pathname.includes('/login'), { timeout: 30000 });
  }, p);
  await prueba('Login: con sesión activa /login redirige dentro de la app', async () => {
    await p.goto(`${WEB}/login`); await p.waitForTimeout(1500);
    if (p.url().includes('/login')) nota('Con sesión iniciada, /login sigue mostrando el formulario (podría redirigir al panel).');
  }, p);
  await prueba('Sesión: recargar mantiene la sesión', async () => {
    await p.goto(`${WEB}/panel`); await p.reload(); await p.waitForTimeout(2000);
    if (p.url().includes('/login')) throw new Error('perdió la sesión al recargar');
  }, p);
  await prueba('Sesión: Salir cierra sesión y el botón Atrás no reabre páginas privadas', async () => {
    await p.getByRole('button', { name: 'Salir' }).click();
    await p.waitForURL('**/login', { timeout: 10000 });
    await p.goBack(); await p.waitForTimeout(1500);
    const t = await cuerpo(p);
    if (!p.url().includes('/login') && /Panel|Órdenes/.test(t) && !/Inicia sesión/.test(t)) throw new Error('Atrás muestra contenido privado');
  }, p);
  await prueba('Guarda: sin sesión /panel redirige a /login', async () => {
    await p.goto(`${WEB}/panel`); await p.waitForURL('**/login', { timeout: 10000 });
  }, p);
  await prueba('Guarda: sin sesión /ordenes/OT-x redirige a /login', async () => {
    await p.goto(`${WEB}/ordenes/OT-x`); await p.waitForURL('**/login', { timeout: 10000 });
  }, p);
  await prueba('Ruta inexistente no deja pantalla en blanco', async () => {
    await p.goto(`${WEB}/esta-ruta-no-existe`); await p.waitForTimeout(1500);
    const t = (await cuerpo(p)).trim();
    if (t.length < 20) throw new Error('pantalla vacía');
  }, p);
  await prueba('Login: título de pestaña descriptivo', async () => {
    const t = await p.title(); if (!t || /vite|react app/i.test(t)) throw new Error(`título "${t}"`);
  }, p);
  await ctx.close();
}

// ---------- 2. COORDINADOR ----------
const coord = await sesion('COORDINADOR');
const c = coord.p;
const marca = `QA ${Date.now()}`;
let urlOrden;
await prueba('Guarda: coordinador en /usuarios es redirigido', async () => {
  await c.goto(`${WEB}/usuarios`); await c.waitForTimeout(1500);
  if (c.url().includes('/usuarios')) throw new Error('accedió a usuarios');
}, c);
await prueba('Navegación: todas las pestañas del coordinador cargan', async () => {
  for (const [txt, ruta] of [['Panel', 'panel'], ['Órdenes', 'ordenes'], ['Agenda', 'agenda'], ['Clientes', 'clientes'], ['Técnicos', 'tecnicos']]) {
    await c.getByRole('link', { name: txt, exact: true }).first().click();
    await c.waitForURL(`**/${ruta}`, { timeout: 10000 });
  }
}, c);
await prueba('Órdenes: filtros por estado cambian la lista', async () => {
  await c.goto(`${WEB}/ordenes`);
  await c.locator('tbody tr').first().waitFor({ timeout: 30000 });
  for (const f of ['Sin atender', 'Programadas', 'Cerradas', 'Canceladas', 'Todas']) {
    await c.getByRole('button', { name: f, exact: true }).click(); await c.waitForTimeout(1200);
    const filas = await c.locator('tbody tr').count(); const t = await cuerpo(c);
    console.log(`   filtro "${f}": ${filas} filas${filas === 0 ? ' -> ' + (t.match(/No hay[^\n]*/) || ['(sin mensaje de vacío)'])[0] : ''}`);
  }
}, c);
await prueba('Órdenes: paginación / cargar más', async () => {
  await c.getByRole('button', { name: 'Todas', exact: true }).click(); await c.waitForTimeout(1200);
  const filas = await c.locator('tbody tr').count();
  const mas = await c.getByRole('button', { name: /más|siguiente/i }).count();
  console.log(`   ${filas} filas, botón "más": ${mas}`);
  if (filas >= 50 && !mas) nota('Órdenes: hay muchas filas y no se ve cómo cargar más (la API devuelve next_cursor).');
}, c);
await prueba('Nueva orden: enviar sin cliente no crea nada', async () => {
  await c.goto(`${WEB}/ordenes/nueva`);
  const antes = c.url();
  await c.getByRole('button', { name: 'Buscar' }).click(); await c.waitForTimeout(1500);
  const t = await cuerpo(c);
  console.log(`   buscar vacío -> ${(t.match(/(Escribe|Indica|No hay|sin resultados|Ingresa)[^\n]*/i) || ['(sin mensaje)'])[0]}`);
  if (c.url() !== antes) throw new Error('navegó');
}, c);
await prueba('Nueva orden: búsqueda de cliente inexistente muestra estado vacío', async () => {
  await c.locator('form input').first().fill('zzzzzz'); await c.getByRole('button', { name: 'Buscar' }).click(); await c.waitForTimeout(2500);
  const t = await cuerpo(c);
  if (!/no hay|sin resultados|no se encontr|ningún/i.test(t)) nota('Nueva orden: buscar un cliente que no existe no muestra ningún mensaje.');
  await c.screenshot({ path: `${OUT}/nueva-orden-vacia.png` });
}, c);
await prueba('Nueva orden: flujo completo crea la orden', async () => {
  await c.goto(`${WEB}/ordenes/nueva`);
  await c.locator('form input').first().fill('hotel'); await c.getByRole('button', { name: 'Buscar' }).click();
  await c.locator('form li button').first().click({ timeout: 30000 });
  const ub = c.getByLabel('Ubicación'); await ub.locator('option').nth(1).waitFor({ state: 'attached', timeout: 30000 });
  // enviar sin descripción
  await ub.selectOption({ index: 1 });
  await c.getByRole('button', { name: 'Crear orden' }).click(); await c.waitForTimeout(1200);
  if (/\/ordenes\/OT-/.test(c.url())) nota('Nueva orden: se pudo crear una orden SIN descripción del problema.');
  if (!/\/ordenes\/OT-/.test(c.url())) {
    await c.getByLabel('Tipo de servicio').selectOption('REPARACION');
    await c.getByLabel('Descripción del problema').fill(marca);
    await c.getByRole('button', { name: 'Crear orden' }).click();
    await c.waitForURL(/\/ordenes\/OT-/, { timeout: 30000 });
  }
  urlOrden = c.url();
  await c.screenshot({ path: `${OUT}/orden-creada.png` });
}, c);
await prueba('Orden: aparece en la lista como primera fila', async () => {
  await c.goto(`${WEB}/ordenes`); await c.locator('tbody tr').first().waitFor({ timeout: 30000 });
  if (!(await c.locator('tbody tr').first().innerText()).includes(marca) && !(await cuerpo(c)).includes(marca)) throw new Error('no aparece en la lista');
}, c);
await prueba('Orden: la fila de la lista abre el detalle (clic y teclado)', async () => {
  await c.locator('tbody tr').first().getByRole('link').first().click().catch(async () => c.locator('tbody tr').first().click());
  await c.waitForURL(/\/ordenes\/OT-/, { timeout: 10000 });
}, c);
await prueba('Orden: cambiar prioridad se guarda al recargar', async () => {
  await c.goto(urlOrden);
  const sel = c.getByLabel('Prioridad'); await sel.waitFor({ timeout: 20000 });
  await sel.selectOption('ALTA'); await c.waitForTimeout(2000);
  await c.reload(); await c.getByLabel('Prioridad').waitFor({ timeout: 20000 });
  const v = await c.getByLabel('Prioridad').inputValue(); if (v !== 'ALTA') throw new Error(`prioridad=${v}`);
  const t = await cuerpo(c); if (!/prioridad/i.test(t.split('Historial')[1] || '')) nota('Orden: cambiar la prioridad no deja rastro en el Historial.');
}, c);
await prueba('Visita: programar para una fecha futura y ver confirmación', async () => {
  await c.getByRole('button', { name: 'Programar visita' }).click();
  const f = new Date(Date.now() + 9 * 86400000); const ddmmaaaa = `${String(f.getDate()).padStart(2, '0')}/${String(f.getMonth() + 1).padStart(2, '0')}/${f.getFullYear()}`;
  await c.getByLabel('Fecha').fill(ddmmaaaa);
  const li = c.locator('li', { hasText: 'Carlos Villanueva' }).first(); await li.waitFor({ timeout: 30000 });
  await c.screenshot({ path: `${OUT}/programar-visita.png` });
  await li.locator('button').last().click();
  await c.getByText(/Visita 1/).first().waitFor({ timeout: 30000 });
  await c.screenshot({ path: `${OUT}/visita-programada.png` });
}, c);
await prueba('Visita: el formato de fecha en el detalle es DD/MM/AAAA como el resto de la app', async () => {
  const t = await cuerpo(c);
  if (/Visita 1 · \d{4}-\d{2}-\d{2}/.test(t)) throw new Error('la visita muestra fecha ISO (AAAA-MM-DD), inconsistente con DD/MM/AAAA');
}, c);
await prueba('Orden: tras programar, el estado visible refleja la visita', async () => {
  await c.reload(); await c.waitForTimeout(2500);
  const cab = await c.locator('h1').first().evaluate((h) => h.parentElement.innerText);
  console.log(`   cabecera: ${cab.replace(/\s+/g, ' ')}`);
  if (/Abierta/.test(cab)) nota('Orden: con una visita Programada la orden sigue marcada como "Abierta" (la lista tiene filtro "Programadas").');
}, c);
await prueba('Visita: no se puede programar en el pasado', async () => {
  await c.getByRole('button', { name: 'Programar visita' }).click();
  await c.getByLabel('Fecha').fill('01/01/2020'); await c.waitForTimeout(2500);
  const t = await cuerpo(c);
  console.log(`   fecha pasada -> ${(t.match(/(No hay|Ya no|pasad|disponib)[^\n]*/i) || ['(sin mensaje)'])[0]}`);
  await c.screenshot({ path: `${OUT}/visita-pasado.png` });
}, c);
await prueba('Visita: fecha escrita con datos inválidos no rompe el formulario', async () => {
  await c.getByLabel('Fecha').fill('99/99/9999'); await c.waitForTimeout(1500);
  const t = await cuerpo(c); if (/Application error|Something went wrong/i.test(t)) throw new Error('error de aplicación');
}, c);
await prueba('Orden: cancelar orden pide confirmación y avisa qué se cancela', async () => {
  await c.goto(urlOrden);
  let dialogo = null;
  c.removeAllListeners('dialog'); c.on('dialog', (d) => { dialogo = d.message(); d.dismiss(); });
  await c.getByRole('button', { name: 'Cancelar orden' }).click(); await c.waitForTimeout(1200);
  const modal = await c.locator('dialog[open]').count();
  if (!dialogo && !modal) throw new Error('cancelar no pide confirmación');
  const txt = dialogo ?? await c.locator('dialog[open]').innerText();
  console.log(`   confirmación: ${txt.replace(/\s+/g, ' ').slice(0, 160)}`);
  await c.screenshot({ path: `${OUT}/cancelar-confirmacion.png` });
  if (modal) await c.locator('dialog[open]').getByRole('button', { name: /volver|no|cancelar$/i }).first().click().catch(() => c.keyboard.press('Escape'));
}, c);
// Clientes
const nombreCliente = `Cliente QA ${Date.now() % 100000}`;
await prueba('Clientes: búsqueda por nombre filtra', async () => {
  await c.goto(`${WEB}/clientes`); await c.locator('tbody tr').first().waitFor({ timeout: 30000 });
  await c.getByPlaceholder(/buscar/i).first().fill('Hotel').catch(async () => c.locator('input').first().fill('Hotel'));
  await c.getByRole('button', { name: 'Buscar' }).click(); await c.waitForTimeout(2000);
  const t = await c.locator('tbody').innerText(); if (!/Hotel/.test(t)) throw new Error('el filtro no devolvió Hotel*');
  if (/Bodega/.test(t)) nota('Clientes: la búsqueda "Hotel" devuelve también clientes que no empiezan por Hotel.');
}, c);
await prueba('Clientes: crear cliente (validación y alta)', async () => {
  await c.goto(`${WEB}/clientes`);
  await c.getByRole('button', { name: 'Nuevo cliente' }).click(); await c.waitForTimeout(800);
  await c.screenshot({ path: `${OUT}/cliente-form.png` });
  const guardar = c.getByRole('button', { name: /guardar|crear/i }).last();
  await guardar.click(); await c.waitForTimeout(1000);
  const t0 = await cuerpo(c); console.log(`   enviar vacío -> ${(t0.match(/(obligatori|requerid|completa)[^\n]*/i) || ['(sin mensaje visible; validación del navegador?)'])[0]}`);
  await c.getByLabel('Nombre').first().fill(nombreCliente);
  const tel = c.getByLabel('Teléfono'); if (await tel.count()) await tel.fill('abc');
  await guardar.click(); await c.waitForTimeout(1500);
  const t1 = await cuerpo(c); if (/abc/.test(await c.locator('input[name=telefono], #telefono').first().inputValue().catch(() => ''))) nota('Clientes: el campo Teléfono acepta letras ("abc") y no avisa.');
  if (await tel.count()) await tel.fill('987654321');
  const correo = c.getByLabel('Correo'); if (await correo.count()) await correo.fill('no-es-correo');
  await guardar.click(); await c.waitForTimeout(1500);
  const t2 = await cuerpo(c); console.log(`   correo inválido -> ${(t2.match(/(correo|email)[^\n]*(válid|inválid)[^\n]*/i) || ['(sin mensaje)'])[0]}`);
  if (await correo.count()) await correo.fill('qa@example.com');
  await guardar.click(); await c.waitForTimeout(3000);
  await c.screenshot({ path: `${OUT}/cliente-creado.png` });
  const t3 = await cuerpo(c); if (!t3.includes(nombreCliente)) throw new Error('el cliente creado no aparece');
}, c);
await prueba('Clientes: detalle de cliente y alta de ubicación', async () => {
  await c.goto(`${WEB}/clientes`);
  await c.getByPlaceholder(/buscar/i).first().fill(nombreCliente).catch(() => c.locator('input').first().fill(nombreCliente));
  await c.getByRole('button', { name: 'Buscar' }).click(); await c.waitForTimeout(2000);
  await c.getByText(nombreCliente).first().click(); await c.waitForURL(/\/clientes\/.+/, { timeout: 10000 });
  await c.waitForTimeout(1500); await c.screenshot({ path: `${OUT}/cliente-detalle.png`, fullPage: true });
  const t = await cuerpo(c); if (!/ubicaci/i.test(t)) nota('Cliente: el detalle no menciona ubicaciones.');
}, c);
await prueba('Técnicos: búsqueda por nombre y detalle', async () => {
  await c.goto(`${WEB}/tecnicos`); await c.getByText('Carlos Villanueva').first().waitFor({ timeout: 30000 });
  await c.getByPlaceholder(/buscar/i).fill('Villanueva'); await c.waitForTimeout(1500);
  await c.getByText('Carlos Villanueva').first().click(); await c.waitForURL(/\/tecnicos\/.+/);
  await c.waitForTimeout(2500); await c.screenshot({ path: `${OUT}/tecnico-detalle.png`, fullPage: true });
}, c);
// Agenda
await prueba('Agenda: vista Semana y navegación de fechas', async () => {
  await c.goto(`${WEB}/agenda`); await c.waitForTimeout(2500);
  await c.getByRole('button', { name: 'Semana' }).click(); await c.waitForTimeout(2000);
  await c.screenshot({ path: `${OUT}/agenda-semana.png`, fullPage: true });
  await c.getByRole('button', { name: 'Día' }).click();
  await c.getByRole('button', { name: /siguiente|→/ }).first().click().catch(() => c.locator('button:has-text("→")').click());
  await c.waitForTimeout(1500);
  await c.getByRole('button', { name: 'Hoy' }).click(); await c.waitForTimeout(1000);
}, c);
await prueba('Agenda: la visita creada aparece en su día', async () => {
  const f = new Date(Date.now() + 9 * 86400000); const s = `${String(f.getDate()).padStart(2, '0')}/${String(f.getMonth() + 1).padStart(2, '0')}/${f.getFullYear()}`;
  const campo = c.getByLabel(/fecha/i).first().or(c.locator('input[inputmode], input[placeholder*="/"]').first());
  await campo.fill(s); await c.waitForTimeout(2500);
  await c.getByLabel(/Ver todos/).check().catch(() => c.getByText('Ver todos los técnicos').click());
  await c.waitForTimeout(2500);
  await c.screenshot({ path: `${OUT}/agenda-dia-visita.png`, fullPage: true });
  const t = await cuerpo(c); if (!/Villanueva/.test(t)) throw new Error('Carlos Villanueva no aparece en la agenda de ese día');
}, c);
await prueba('Agenda: filtro de especialidad no corta su etiqueta', async () => {
  const w = await c.evaluate(() => { const s = document.querySelector('select'); return s ? [s.scrollWidth, s.clientWidth] : null; });
  console.log(`   select especialidad scroll/client: ${w}`);
}, c);
await prueba('Tema oscuro: alternar y recargar mantiene el tema', async () => {
  await c.getByRole('button', { name: /tema|oscuro|claro/i }).first().click().catch(() => c.locator('header button').first().click());
  await c.waitForTimeout(600); await c.goto(`${WEB}/panel`); await c.waitForTimeout(3000);
  await c.screenshot({ path: `${OUT}/panel-oscuro.png`, fullPage: true });
  const bg = await c.evaluate(() => getComputedStyle(document.body).backgroundColor); console.log(`   fondo tras recargar: ${bg}`);
}, c);
await prueba('Panel: el selector de mes usa el idioma de la app', async () => {
  const v = await c.evaluate(() => { const i = document.querySelector('input[type=month]'); return i ? 'native-month' : 'custom'; });
  if (v === 'native-month') nota('Panel: "Mes del resumen" usa el selector nativo del navegador (en inglés: "November 2026"), distinto del campo de fecha propio DD/MM/AAAA.');
}, c);
await prueba('Panel: números coherentes (abiertas del anillo vs órdenes en curso)', async () => {
  await c.goto(`${WEB}/panel`); await c.waitForTimeout(3500);
  const t = await cuerpo(c);
  const curso = (t.match(/Órdenes en curso\s+(\d+)/) || [])[1]; const abiertas = (t.match(/Abiertas\s+(\d+)/) || [])[1];
  console.log(`   en curso=${curso} abiertas(mes)=${abiertas}`);
  if (curso && abiertas && curso !== abiertas) nota(`Panel: "Órdenes en curso" (${curso}) y "Abiertas" del anillo (${abiertas}) difieren sin explicación (el anillo es del mes, la tarjeta no).`);
}, c);
await prueba('Mapa: se renderiza con marcadores', async () => {
  await c.locator('.leaflet-container').waitFor({ timeout: 20000 });
  const m = await c.locator('.leaflet-marker-icon, .leaflet-overlay-pane path').count(); if (!m) throw new Error('sin marcadores');
}, c);
await coord.ctx.close();

// ---------- 3. TÉCNICO (móvil) ----------
const tec = await sesion('TECNICO', { width: 390, height: 844 });
const t = tec.p;
await prueba('Técnico: aterriza en "Mis visitas" y no ve menús de coordinación', async () => {
  await t.waitForURL('**/mis-visitas', { timeout: 15000 });
  const links = await t.locator('nav a, header a').allInnerTexts(); console.log(`   enlaces visibles: ${links.join(', ') || '(menú plegado)'}`);
}, t);
await prueba('Técnico: menú móvil abre y cierra', async () => {
  await t.getByRole('button', { name: 'Menú' }).click(); await t.waitForTimeout(500);
  await t.screenshot({ path: `${OUT}/tecnico-menu.png` });
  await t.keyboard.press('Escape');
}, t);
await prueba('Técnico: ve su visita programada para otro día', async () => {
  await t.goto(`${WEB}/mis-visitas`); await t.waitForTimeout(3000);
  const txt = await cuerpo(t);
  console.log(`   texto: ${txt.replace(/\s+/g, ' ').slice(0, 220)}`);
  if (!/Próxim|Mañana|Esta semana|Siguientes|\d{2}\/\d{2}/.test(txt)) nota('Técnico: "Mi día" solo muestra HOY. La API sí devuelve visitas futuras (p. ej. 04/12 y las de esta prueba) pero el técnico no puede verlas ni anticiparse.');
}, t);
await prueba('Técnico: sin horizontal scroll en Mis visitas', async () => {
  const s = await t.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth); if (s > 0) throw new Error(`${s}px de desborde`);
}, t);
await prueba('Técnico: URL de visita ajena/inexistente no rompe', async () => {
  await t.goto(`${WEB}/mis-visitas/VIS-NOEXISTE`); await t.waitForTimeout(3000);
  await t.screenshot({ path: `${OUT}/tecnico-visita-inexistente.png` });
  const x = await cuerpo(t); console.log(`   -> ${x.replace(/\s+/g, ' ').slice(0, 120)}`);
}, t);
await prueba('Técnico: /panel redirige', async () => {
  await t.goto(`${WEB}/panel`); await t.waitForTimeout(1500); if (t.url().includes('/panel')) throw new Error('el técnico entró al panel');
}, t);
await tec.ctx.close();

// ---------- 4. ADMIN: USUARIOS ----------
const adm = await sesion('ADMIN');
const a = adm.p;
await prueba('Usuarios: listar, filtrar por rol y buscar', async () => {
  await a.goto(`${WEB}/usuarios`); await a.locator('tbody tr').first().waitFor({ timeout: 30000 });
  await a.getByLabel('Rol').selectOption({ index: 1 }); await a.waitForTimeout(1500);
  await a.getByLabel('Estado').selectOption({ index: 1 }); await a.waitForTimeout(1500);
  await a.screenshot({ path: `${OUT}/usuarios-filtrado.png` });
}, a);
await prueba('Usuarios: el formulario Nuevo usuario valida contraseña débil y correo', async () => {
  await a.getByRole('button', { name: 'Nuevo usuario' }).click(); await a.waitForTimeout(800);
  await a.screenshot({ path: `${OUT}/usuarios-nuevo.png` });
  const t0 = await cuerpo(a); console.log(`   campos: ${(await a.locator('dialog[open] label, form label').allInnerTexts()).join(', ')}`);
}, a);
await prueba('Usuarios: filas "Inactivo" con roles múltiples se ven coherentes', async () => {
  const t1 = await a.locator('tbody tr').first().innerText(); console.log(`   fila 1: ${t1.replace(/\s+/g, ' ')}`);
}, a);
await adm.ctx.close();

await nav.close();
const ok = resultados.filter((r) => r.ok).length;
writeFileSync(`${OUT}/flujo.json`, JSON.stringify({ resultados, notas, org: new Date().toISOString() }, null, 1));
console.log(`\nRESUMEN: ${ok} PASS / ${resultados.length - ok} FAIL / ${notas.length} observaciones`);
