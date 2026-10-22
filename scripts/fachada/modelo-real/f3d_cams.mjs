// Fotografa o site (modelo atual) das 13 câmeras do Twinmotion: node f3d_cams.mjs <cameras.json> <saida> <fov>
import { spawn } from 'node:child_process';
import { mkdirSync, writeFileSync, rmSync, readFileSync } from 'node:fs';
const [CAMS, OUT, FOV = '40'] = process.argv.slice(2);
mkdirSync(OUT, { recursive: true });
const cams = JSON.parse(readFileSync(CAMS, 'utf8'));
const PORTA = 9400 + Math.floor(Math.random() * 400);
const PERFIL = `${OUT}/perfil-cams`; rmSync(PERFIL, { recursive: true, force: true });
const chrome = spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', [
  '--headless=new', `--remote-debugging-port=${PORTA}`, `--user-data-dir=${PERFIL}`,
  '--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist', '--window-size=900,1072',
  '--hide-scrollbars', '--no-first-run', 'about:blank'], { stdio: 'ignore' });
const dorme = (ms) => new Promise((r) => setTimeout(r, ms));
let alvo;
for (let i = 0; i < 50 && !alvo; i++) { await dorme(200); try { alvo = (await (await fetch(`http://127.0.0.1:${PORTA}/json/list`)).json()).find((t) => t.type === 'page'); } catch {} }
const ws = new WebSocket(alvo.webSocketDebuggerUrl); await new Promise((r) => ws.addEventListener('open', r));
let id = 0; const pend = new Map();
ws.addEventListener('message', (ev) => { const m = JSON.parse(ev.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); } });
const cdp = (method, params = {}) => new Promise((r) => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const avalia = async (expr) => (await cdp('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true })).result?.result?.value;
await cdp('Runtime.enable'); await cdp('Page.enable');
await cdp('Emulation.setDeviceMetricsOverride', { width: 900, height: 1072, deviceScaleFactor: 1, mobile: false });
await cdp('Page.addScriptToEvaluateOnNewDocument', { source: "try{sessionStorage.setItem('cinnamon-intro','1')}catch(e){}" });
await cdp('Page.navigate', { url: 'http://localhost:4173/?f3d=info,lente0' });
await dorme(4000);
for (let i = 0; i < 12; i++) { const top = await avalia(`(()=>{const s=document.querySelector('[data-fachada]');s.scrollIntoView();return Math.round(s.getBoundingClientRect().top)})()`); await dorme(700); if (Math.abs(top) < 2 && i > 2) break; }
for (let i = 0; i < 120; i++) { await dorme(500); if (await avalia(`!!(window.__f3dinfo && __f3dinfo().tempos.length >= 5)`)) break; }
await avalia(`(()=>{const st=document.createElement('style');st.textContent='.site-header,.rail,[class*="rail"],.fachada__top,.fachada__actions,.fachada__picker,.fachada__hint,.fachada__drag,.fachada__panel,.fachada__scrim,.fachada__loading,.fachada__poster{display:none!important}';document.head.appendChild(st)})()`);
await avalia(`__f3dfov(${FOV})`);
for (const c of cams) {
  await avalia(`__f3dcam(${c.yaw},${c.pitch},${c.dist},[${c.centro.join(',')}])`);
  await dorme(3200);
  await avalia(`(()=>{const s=document.querySelector('[data-fachada]');window.scrollBy(0,s.getBoundingClientRect().top)})()`);
  await dorme(900);
  const shot = await cdp('Page.captureScreenshot', { format: 'jpeg', quality: 85 });
  writeFileSync(`${OUT}/${c.nome}.jpg`, Buffer.from(shot.result.data, 'base64'));
  console.log('ok', c.nome);
}
ws.close(); chrome.kill(); await new Promise((r) => chrome.on('exit', r)); process.exit(0);
