// Poster da secao #fachada: captura do proprio visualizador, sem a interface.
// Requer o site em http://localhost:4173 (preview "cinnamon").
// node scripts/fachada/modelo-real/poster.mjs <saida.png> [yaw pitch dist]
// Depois: cwebp/sips para img/fachada-poster-1920.webp e -960.webp.
import { spawn } from 'node:child_process';
import { writeFileSync, rmSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';

const [SAIDA, yaw = '-2.46', pitch = '-0.176', dist = '190'] = process.argv.slice(2);
const PERFIL = mkdtempSync(`${tmpdir()}/f3d-poster-`);
const PORTA = 9361 + Math.floor(Math.random() * 500);
const chrome = spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', [
  '--headless=new', `--remote-debugging-port=${PORTA}`, `--user-data-dir=${PERFIL}`,
  '--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist', '--window-size=1920,1072',
  '--hide-scrollbars', '--no-first-run', 'about:blank'], { stdio: 'ignore' });
const dorme = (ms) => new Promise((r) => setTimeout(r, ms));
let alvo;
for (let i = 0; i < 50 && !alvo; i++) {
  await dorme(200);
  try { alvo = (await (await fetch(`http://127.0.0.1:${PORTA}/json/list`)).json()).find((t) => t.type === 'page'); } catch {}
}
const ws = new WebSocket(alvo.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener('open', r));
let id = 0; const pend = new Map();
ws.addEventListener('message', (ev) => { const m = JSON.parse(ev.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); } });
const cdp = (method, params = {}) => new Promise((r) => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const avalia = async (expr) => (await cdp('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true })).result?.result?.value;
await cdp('Runtime.enable'); await cdp('Page.enable');
// palco = min(84svh, 900px): viewport de 1072 px de altura da exatamente 1920 x 900
await cdp('Emulation.setDeviceMetricsOverride', { width: 1920, height: 1072, deviceScaleFactor: 1, mobile: false });
await cdp('Page.addScriptToEvaluateOnNewDocument', { source: "try{sessionStorage.setItem('cinnamon-intro','1')}catch(e){}" });
await cdp('Page.navigate', { url: 'http://localhost:4173/?f3d=info' });
await dorme(4000);
for (let i = 0; i < 12; i++) {
  const top = await avalia(`(()=>{const s=document.querySelector('[data-fachada]');s.scrollIntoView();return Math.round(s.getBoundingClientRect().top)})()`);
  await dorme(700);
  if (Math.abs(top) < 2 && i > 2) break;
}
for (let i = 0; i < 120; i++) {
  await dorme(500);
  if (await avalia(`!!(window.__f3dinfo && __f3dinfo().tempos.length >= 5)`)) break;
}
// so o canvas: sem cabecalho, trilho, botoes, seletores, dicas e degrade
await avalia(`(()=>{const st=document.createElement('style');st.textContent=
  '.site-header,.rail,[class*="rail"],.fachada__top,.fachada__actions,.fachada__picker,.fachada__hint,.fachada__drag,'+
  '.fachada__panel,.fachada__scrim,.fachada__loading,.fachada__poster,.fachada__gizmo,[data-fachada-gizmo]{display:none!important}';document.head.appendChild(st)})()`);
await avalia(`__f3dcam(${yaw},${pitch},${dist})`);
await dorme(4500);                       // parado: densidade cheia + brilho
await avalia(`(()=>{const s=document.querySelector('[data-fachada]');window.scrollBy(0,s.getBoundingClientRect().top)})()`);
await dorme(1500);
const h = await avalia(`Math.round(document.querySelector('[data-fachada]').getBoundingClientRect().height)`);
const shot = await cdp('Page.captureScreenshot', { format: 'png' });   // sem clip (com clip o canvas ja saiu vazio); recorte depois: topo, 1920 x altura do palco
writeFileSync(SAIDA, Buffer.from(shot.result.data, 'base64'));
console.log('ok', SAIDA, 'altura do palco', h);
ws.close(); chrome.kill();
await new Promise((r) => chrome.on('exit', r));
try { rmSync(PERFIL, { recursive: true, force: true }); } catch {}
process.exit(0);
