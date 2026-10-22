// QA da secao #fachada em Chrome headless (GPU real) via CDP.
// node f3d_qa.mjs <variante: atual|real> <pasta de saida>
// "real": troca img/fachada.glb por img/fachada-real.glb na rede (CDP Fetch); "site": usa o data-glb do index.
import { spawn } from 'node:child_process';
import { mkdirSync, writeFileSync, rmSync } from 'node:fs';

const [variante, OUT] = process.argv.slice(2);
mkdirSync(OUT, { recursive: true });
const PORTA = 9333 + (variante === 'real' ? 1 : 0);
const PERFIL = `${OUT}/perfil-${variante}`;
rmSync(PERFIL, { recursive: true, force: true });
const chrome = spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', [
  '--headless=new', `--remote-debugging-port=${PORTA}`, `--user-data-dir=${PERFIL}`,
  '--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist', '--window-size=1280,860',
  '--hide-scrollbars', '--no-first-run', 'about:blank'], { stdio: 'ignore' });
const dorme = (ms) => new Promise((r) => setTimeout(r, ms));

let alvo;
for (let i = 0; i < 50 && !alvo; i++) {
  await dorme(200);
  try { alvo = (await (await fetch(`http://127.0.0.1:${PORTA}/json/list`)).json()).find((t) => t.type === 'page'); } catch {}
}
const ws = new WebSocket(alvo.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener('open', r));
let id = 0; const pend = new Map(); const ouvintes = [];
ws.addEventListener('message', (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); }
  else ouvintes.forEach((f) => f(m));
});
const cdp = (method, params = {}) => new Promise((r) => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const avalia = async (expr) => {
  const r = await cdp('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
  if (r.result?.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails).slice(0, 400));
  return r.result?.result?.value;
};

const erros = [];
ouvintes.push((m) => {
  if (m.method === 'Runtime.exceptionThrown') erros.push(m.params.exceptionDetails.text + ' ' + (m.params.exceptionDetails.exception?.description || ''));
  if (m.method === 'Runtime.consoleAPICalled' && ['error', 'warning'].includes(m.params.type)) erros.push(m.params.type + ': ' + m.params.args.map((a) => a.value ?? a.description).join(' '));
  if (m.method === 'Fetch.requestPaused') {
    const u = m.params.request.url;
    const novo = u.replace(/img\/fachada\.glb[^#]*/, 'img/fachada-real.glb?v=qa');
    cdp('Fetch.continueRequest', { requestId: m.params.requestId, ...(novo !== u ? { url: novo } : {}) });
  }
});
await cdp('Runtime.enable');
await cdp('Page.enable');
if (variante === 'real') await cdp('Fetch.enable', { patterns: [{ urlPattern: '*fachada.glb*' }] });
await cdp('Page.addScriptToEvaluateOnNewDocument', { source: "try{sessionStorage.setItem('cinnamon-intro','1')}catch(e){}" });
await cdp('Page.navigate', { url: 'http://localhost:4173/?f3d=info' });
await dorme(4000);

// rola ate a secao parar de se mexer (a pagina estica depois do load por causa dos pins)
for (let i = 0; i < 12; i++) {
  const top = await avalia(`(()=>{const s=document.querySelector('#fachada');s.scrollIntoView();return Math.round(s.getBoundingClientRect().top)})()`);
  await dorme(700);
  if (Math.abs(top) < 3 && i > 2) break;
}
const t0 = Date.now();
let pronto = false;
for (let i = 0; i < 120 && !pronto; i++) {
  await dorme(500);
  pronto = await avalia(`!!(window.__f3dinfo && window.__f3dinfo().tempos && window.__f3dinfo().tempos.length >= 5)`);
}
const carga_s = (Date.now() - t0) / 1000;
await dorme(2500);
const info = await avalia(`(()=>{const i=__f3dinfo();return {programas:i.programas,chamadas:i.chamadas,triangulos:i.triangulos,tempos:i.tempos,mats:i.mats}})()`);

// fps girando a camera (mesma rotina nas duas variantes)
const fps = await avalia(`new Promise(ok=>{let n=0,t0=performance.now(),y=-2.46;function f(){y+=0.01;__f3dcam(y,0.05,170);n++;if(performance.now()-t0<4000)requestAnimationFrame(f);else ok(+(n/((performance.now()-t0)/1000)).toFixed(1))}requestAnimationFrame(f)})`);

const vistas = [
  ['quina-no', -2.46, -0.05, 150], ['quina-no-perto', -2.46, 0.02, 80], ['sudeste', 0.68, 0.08, 160],
  ['canto-interno', 0.0, 0.15, 140], ['alto', -2.0, 0.9, 190],
];
for (const [nome, y, p, d] of vistas) {
  await avalia(`__f3dcam(${y},${p},${d})`);
  await dorme(2200);
  const r = await avalia(`(()=>{const c=document.querySelector('[data-fachada-canvas]');const b=c.getBoundingClientRect();window.scrollBy(0,b.top);const b2=c.getBoundingClientRect();return {y:b2.top+window.scrollY,h:b2.height,w:b2.width,x:b2.left}})()`);
  await dorme(1500);
  const shot = await cdp('Page.captureScreenshot', { format: 'jpeg', quality: 82, clip: { x: r.x, y: r.y, width: r.w, height: Math.min(r.h, 860), scale: 1 } });
  writeFileSync(`${OUT}/${variante}-${nome}.jpg`, Buffer.from(shot.result.data, 'base64'));
}
writeFileSync(`${OUT}/${variante}.json`, JSON.stringify({ carga_s, fps, info, erros }, null, 1));
console.log(variante, 'carga', carga_s, 's | fps', fps, '| tri', info.triangulos, '| chamadas', info.chamadas, '| erros', erros.length);
ws.close(); chrome.kill();
process.exit(0);
