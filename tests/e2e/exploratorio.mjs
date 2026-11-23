// Prueba exploratoria: recorre todas las pantallas por rol y viewport, y registra
// errores de consola, respuestas 4xx/5xx, desborde horizontal, tiempos y capturas.
// Uso: node exploratorio.mjs <url-web> <url-api> <carpeta-salida>
import { chromium } from 'playwright';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';

const [WEB, API, OUT] = process.argv.slice(2);
mkdirSync(OUT, { recursive: true });
const cuentas = readFileSync(new URL('../../.demo-credentials', import.meta.url), 'utf8')
  .split('\n').filter((l) => l && !l.startsWith('#')).map((l) => l.split(/\s+/));
const cuenta = (tenant, rol) => {
  const f = cuentas.find((c) => c[0] === 'dev' && c[1] === tenant && c[4] === rol);
  return { tenant, email: f[2], password: f[3] };
};

const hallazgos = [];
const nota = (sev, donde, txt) => { hallazgos.push({ sev, donde, txt }); console.log(`[${sev}] ${donde}: ${txt}`); };

function vigilar(p, ctx) {
  p.on('pageerror', (e) => nota('ERROR', ctx(), `excepción JS: ${e.message}`));
  p.on('console', (m) => { if (m.type() === 'error') nota('CONSOLA', ctx(), m.text().slice(0, 200)); });
  p.on('response', (r) => {
    if (r.status() >= 400 && r.url().includes('execute-api')) nota('HTTP', ctx(), `${r.status()} ${r.request().method()} ${r.url().replace(API, '')}`);
  });
  p.on('requestfailed', (r) => nota('RED', ctx(), `${r.failure()?.errorText} ${r.url().slice(0, 120)}`));
  p.on('dialog', (d) => d.accept());
}

async function login(browser, datos, viewport, etiqueta) {
  const c = await browser.newContext({ viewport });
  const p = await c.newPage();
  let donde = `${etiqueta}/login`;
  vigilar(p, () => donde);
  const t0 = Date.now();
  await p.goto(`${WEB}/login`);
  await p.getByLabel('Código de empresa').fill(datos.tenant);
  await p.getByLabel('Correo').fill(datos.email);
  await p.getByLabel('Contraseña').fill(datos.password);
  await p.locator('button[type=submit]').click();
  await p.waitForURL((u) => !u.pathname.includes('/login'), { timeout: 30000 });
  console.log(`  login ${etiqueta}: ${Date.now() - t0} ms`);
  return { p, ctx: c, setDonde: (d) => { donde = d; } };
}

async function visitar(s, etiqueta, ruta, nombre) {
  s.setDonde(`${etiqueta}${ruta}`);
  const t0 = Date.now();
  await s.p.goto(`${WEB}${ruta}`, { waitUntil: 'networkidle', timeout: 45000 }).catch((e) => nota('ERROR', `${etiqueta}${ruta}`, `no cargó: ${e.message.slice(0, 100)}`));
  await s.p.waitForTimeout(800);
  const ms = Date.now() - t0;
  if (ms > 5000) nota('LENTO', `${etiqueta}${ruta}`, `${ms} ms hasta estar estable`);
  const sobra = await s.p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  if (sobra > 0) nota('LAYOUT', `${etiqueta}${ruta}`, `${sobra}px de desborde horizontal`);
  const texto = await s.p.evaluate(() => document.body.innerText);
  if (/undefined|NaN|\[object|null\b/.test(texto)) nota('DATO', `${etiqueta}${ruta}`, `texto sospechoso: ${(texto.match(/.{0,30}(undefined|NaN|\[object|null\b).{0,30}/) || [''])[0].replace(/\s+/g, ' ')}`);
  const imgsRotas = await s.p.evaluate(() => [...document.images].filter((i) => i.complete && i.naturalWidth === 0).length);
  if (imgsRotas) nota('LAYOUT', `${etiqueta}${ruta}`, `${imgsRotas} imagen(es) rotas`);
  const sinNombre = await s.p.evaluate(() => [...document.querySelectorAll('button, a, input, select')].filter((e) => !(e.innerText || e.getAttribute('aria-label') || e.getAttribute('title') || e.labels?.length || e.placeholder || e.value)).length);
  if (sinNombre) nota('A11Y', `${etiqueta}${ruta}`, `${sinNombre} control(es) sin nombre accesible`);
  await s.p.screenshot({ path: `${OUT}/${etiqueta}${ruta.replace(/\//g, '_') || '_inicio'}.png`, fullPage: true });
  console.log(`  ${etiqueta}${ruta} (${nombre}) ${ms} ms`);
  return texto;
}

const navegador = await chromium.launch();
const ESC = { width: 1280, height: 800 };
const MOV = { width: 390, height: 844 };
try {
  for (const [rolEt, tenant, rol, rutas, vp] of [
    ['coord', 'CLIMALIMA', 'COORDINADOR', ['/', '/panel', '/ordenes', '/ordenes/nueva', '/clientes', '/tecnicos', '/agenda', '/usuarios'], ESC],
    ['admin', 'CLIMALIMA', 'ADMIN', ['/', '/panel', '/usuarios', '/ordenes', '/clientes', '/tecnicos', '/agenda'], ESC],
    ['tecnico', 'CLIMALIMA', 'TECNICO', ['/', '/mis-visitas', '/panel', '/ordenes', '/usuarios'], MOV],
    ['coord-movil', 'CLIMALIMA', 'COORDINADOR', ['/panel', '/ordenes', '/agenda', '/clientes', '/tecnicos'], MOV],
  ]) {
    console.log(`== ${rolEt}`);
    const s = await login(navegador, cuenta(tenant, rol), vp, rolEt);
    for (const r of rutas) await visitar(s, rolEt, r, rol);
    await s.ctx.close();
  }
} finally {
  await navegador.close();
  writeFileSync(`${OUT}/hallazgos.json`, JSON.stringify(hallazgos, null, 1));
}
