// Escolhe studios pelos selects e fotografa: confere se acende e se a camera mira certo.
// node f3d_sel.mjs <atual|real> <pasta> "pav,stu;pav,stu;..."
import { spawn } from 'node:child_process';
import { mkdirSync, writeFileSync, rmSync } from 'node:fs';

const [variante, OUT, lista] = process.argv.slice(2);
mkdirSync(OUT, { recursive: true });
const PORTA = 9343 + (variante === 'real' ? 1 : 0);
const PERFIL = `${OUT}/perfil-sel-${variante}`;
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
  if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); } else ouvintes.forEach((f) => f(m));
});
const cdp = (method, params = {}) => new Promise((r) => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const avalia = async (expr) => (await cdp('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true })).result?.result?.value;
ouvintes.push((m) => {
  if (m.method === 'Fetch.requestPaused') {
    const u = m.params.request.url, novo = u.replace(/img\/fachada\.glb[^#]*/, 'img/fachada-real.glb?v=qa');
    cdp('Fetch.continueRequest', { requestId: m.params.requestId, ...(novo !== u ? { url: novo } : {}) });
  }
});
await cdp('Runtime.enable'); await cdp('Page.enable');
if (variante === 'real') await cdp('Fetch.enable', { patterns: [{ urlPattern: '*fachada.glb*' }] });
await cdp('Page.addScriptToEvaluateOnNewDocument', { source: "try{sessionStorage.setItem('cinnamon-intro','1')}catch(e){}" });
await cdp('Page.navigate', { url: 'http://localhost:4173/?f3d=info' });
await dorme(4000);
for (let i = 0; i < 12; i++) {
  const top = await avalia(`(()=>{const s=document.querySelector('#fachada');s.scrollIntoView();return Math.round(s.getBoundingClientRect().top)})()`);
  await dorme(700);
  if (Math.abs(top) < 3 && i > 2) break;
}
for (let i = 0; i < 120; i++) {
  await dorme(500);
  if (await avalia(`!!(window.__f3dinfo && __f3dinfo().tempos.length >= 5)`)) break;
}
await dorme(2000);
const res = [];
for (const par of lista.split(';')) {
  const [pav, stu] = par.split(',').map(Number);
  await avalia(`(()=>{const p=document.querySelector('[data-fachada-sel-pav]'),s=document.querySelector('[data-fachada-sel-stu]');
    p.value=String(${pav});p.dispatchEvent(new Event('change'));s.value=String(${stu});s.dispatchEvent(new Event('change'));})()`);
  await dorme(3500);
  const vis = await avalia(`JSON.stringify(__f3dvis(${pav},${stu}))`);
  const painel = await avalia(`(document.querySelector('[data-fachada-painel]')||document.querySelector('.fachada__painel')||{}).innerText||''`);
  const r = await avalia(`(()=>{const c=document.querySelector('[data-fachada-canvas]');const b=c.getBoundingClientRect();window.scrollBy(0,b.top);const b2=c.getBoundingClientRect();return {y:b2.top+window.scrollY,h:b2.height,w:b2.width,x:b2.left}})()`);
  await dorme(1200);
  const shot = await cdp('Page.captureScreenshot', { format: 'jpeg', quality: 82, clip: { x: r.x, y: r.y, width: r.w, height: Math.min(r.h, 860), scale: 1 } });
  writeFileSync(`${OUT}/sel-${variante}-P${pav}-S${stu}.jpg`, Buffer.from(shot.result.data, 'base64'));
  res.push({ pav, stu, vis: JSON.parse(vis || 'null'), painel: painel.slice(0, 200) });
}
writeFileSync(`${OUT}/sel-${variante}.json`, JSON.stringify(res, null, 1));
for (const r of res) console.log(variante, r.pav, r.stu, r.vis && r.vis.fachada, r.vis && r.vis.centro, r.vis && r.vis.cam.escolhida, r.vis && r.vis.cam.luz, '|', r.painel.replace(/\s+/g, ' ').slice(0, 90));
ws.close(); chrome.kill(); process.exit(0);
