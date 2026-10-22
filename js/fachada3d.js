/* ============================================================
   CINNAMON STUDIO — fachada3d.js
   A torre em 3D (#fachada): gire, aproxime e toque num studio —
   ele acende e o painel mostra onde fica e as metragens oficiais.
   A ideia vem das "tabelas em 3D" dos lançamentos; aqui NÃO há preço,
   status (vendido/disponível) nem percentual: memorial de incorporação
   não registrado (ver rodapé). O painel só traz o que é oficial.

   Motor: Three.js, a única biblioteca além de GSAP/Lenis no site
   (exceção registrada no CLAUDE.md). Ela e o modelo (o data-glb do palco:
   img/fachada-real.glb, convertido do FBX do arquiteto por
   scripts/fachada/modelo-real/; a maquete antiga img/fachada.glb sai de
   scripts/fachada/gen_fachada.py) só baixam quando a seção chega a uma
   tela de distância; até lá vale o pôster.

   Regras de gesto, as mesmas do tour 360: em fluxo o dedo na vertical e a
   roda são da PÁGINA; girar é arrastar na horizontal. Na tela cheia o
   palco assume tudo (inclinar, roda, pinça). Dois níveis de qualidade:
   em movimento, densidade baixa e sem pós-processo; parado, densidade
   cheia + brilho (bloom) das luzes. No celular: sem sombras, sem reflexo
   e sem bloom — a GPU integrada não paga.

   Estados no palco (CSS): .is-loading .is-webgl .is-live .is-ready
   .is-touched .is-expanded. Reduced-motion: sem giro automático, sem
   inércia, sem planeio de câmera, luz acende sem transição.
   ============================================================ */
(function () {
  'use strict';

  var stage = document.querySelector('[data-fachada]');
  if (!stage) return;

  function q(sel) { return stage.querySelector(sel); }

  var canvas  = q('[data-fachada-canvas]');
  var poster  = q('[data-fachada-poster]');
  var panel   = q('[data-fachada-panel]');
  var errorEl = q('[data-fachada-error]');
  var fullBtn = q('[data-fachada-full]');
  var selPav  = q('[data-fachada-sel-pav]');
  var selStu  = q('[data-fachada-sel-stu]');
  if (!canvas) return;

  var GLB = stage.getAttribute('data-glb') || 'img/fachada.glb';
  var CDN = 'https://cdn.jsdelivr.net/npm/three@0.160.0/';

  var mqReduce = window.matchMedia('(prefers-reduced-motion: reduce)');
  var mqFine   = window.matchMedia('(hover:hover) and (pointer:fine)');
  var mqFolha = window.matchMedia('(max-width: 768px)');
  /* diagnóstico (QA): ?f3d=sombra0,reflexo0,bloom0,nevoa0 desliga cada efeito */
  var DBG = (/[?&]f3d=([a-z0-9,]+)/.exec(location.search) || [])[1] || '';   /* painel vira folha embaixo (css 15c) */
  var leve = !mqFine.matches || Math.min(screen.width, screen.height) < 768; /* celular/tablet: sem sombra, reflexo e bloom */

  /* câmera — órbita em volta do centro da torre (metros do modelo) */
  var CENTRO = [24.5, 33, 22];      /* centro da maquete (planta 49 x 44 m); alvo acima do meio da torre:
                                       com a câmera no nível da rua o horizonte fica baixo (Render 2) */
  var DIST_START = 190, DIST_MIN = 46, DIST_MAX = 340;
  /* zoom dinâmico (pedido do usuário em 15/10/2026): perto, o alvo da órbita desce até o
     térreo e sobe até a coroa (arrastar na vertical, pinça/roda no ponto, botões ▲▼).
     De longe ele volta ao meio da torre. A câmera nunca entra no prédio: fora do raio
     R_LIVRE em volta do centro, ou acima de Y_LIVRE */
  var ALT_MIN = 3, ALT_MAX = 58, DIST_SEL = 88, R_LIVRE = 38, Y_LIVRE = 64;
  /* abre de baixo para cima, como o Render 1 (câmera a ~9 m do chão): é de baixo que
     aparecem os forros de madeira acesos. O limite de baixo depende da distância —
     a câmera nunca desce a menos de 2,5 m do chão (pitchMin) */
  /* TERRENO (16/10/2026) — dados do PROJETO (DWG do arquiteto, prancha TÉRREO/LOCAÇÃO, set/2026), não do FBX nem dos renders:
     o piso do térreo é 0,00; a calçada ao redor está em −0,02 a −0,05 ("NÃO HAVERÁ DESNÍVEL COM A CALÇADA VIZINHA") nos lados LESTE (Avenida
     Parque), SUL e OESTE (Rua-05): o prédio é RENTE ao chão, sem plataforma. Só o lado NORTE (a orla) desce: cotas de −1,14 no canto
     nordeste e −1,74 no noroeste, com "parede de contenção" e o "gradil de ventilação vertical" dos subsolos — é o muro de pedra com a
     grelha das imagens 14–16. As cotas do DWG (relativas ao piso 0,00 = y 1,05 do site) viram y do site somando 1,05. A queda começa em
     z = zN1 (a calçada leste é rente ao longo de toda a entrada) e vai suave até a linha do muro norte (z = zN0). O gerador manda estes
     números pelo .glb (extras.terreno): fonte única. AJUSTAR: o DWG só dá as cotas dos cantos e não diz onde a queda começa. */
  var TERR = { chaoL: 1.0, zN0: -0.9, zN1: 24, gNO: -0.69, gNL: -0.09, xO: -2.5, xL: 54.4 };
  function hgt(x, z) {                  /* altura (y do site) do terreno em (x, z) */
    var t = clamp((TERR.zN1 - z) / (TERR.zN1 - TERR.zN0), 0, 1); t = t * t * (3 - 2 * t);
    var u = clamp((x - TERR.xO) / (TERR.xL - TERR.xO), 0, 1), gN = TERR.gNO + (TERR.gNL - TERR.gNO) * u;
    return TERR.chaoL + (gN - TERR.chaoL) * t;
  }
  var CHAO_Y = 1.0;                     /* nível rente (calçada) — referência do reflexo e do celular */
  var PITCH_START = -0.16, PITCH_MAX = 1.48, CHAO_MIN = 1.0 + 1.7;   /* 1,48: vista de cima (seletor de ângulos, 16/10/2026) */   /* olho a 1,7 m da calçada; sobre o deque, 1,7 m do deque (chaoMin) */
  /* lente de arquitetura: até LENTE_MAX a câmera fica na horizontal e a lente desloca para
     enquadrar (as verticais da torre ficam retas, como nos renders); passou disso, inclina.
     De perto o campo de visão abre (FOV_PERTO) para caber térreo e coroa */
  var LENTE_MAX = 0.38, FOV_LONGE = 30, FOV_PERTO = 40;
  var YAW_START = -2.46;             /* quina noroeste, como o Render 1: madeira, letreiro, escada e as duas alas */
  /* sol (16/10/2026): um céu só para os Renders 2, 3, 9 e 10. Posto ~23° à direita da vista
     inicial (quina noroeste, Render 2: dourado atrás da torre); quem olha a parede leste de
     frente (Render 3) o tem ~105° à esquerda — creme na borda esquerda, azul à direita; da
     entrada no canto interno (Render 10) ele fica atrás: céu azul de nuvens escuras */
  var SOL_AZ = YAW_START + Math.PI - 0.4, SOL_ALT = 0.42, SOL_ALT_CEU = -0.03;
  var GIRO_AUTO = 0.00010;           /* rad/ms do giro automático */
  var FRICTION = 0.90, ZOOM_STEP = 0.14, WHEEL_STEP = 0.08, KEY_STEP = 0.06;
  var SUAVE = 0.14;                  /* fração por quadro do planeio de câmera */

  /* orçamento: densidade de pixels por nível */
  var MOVENDO = leve ? 1 : 1.25;
  var PARADO  = leve ? Math.min(2, window.devicePixelRatio || 1) : Math.min(2, window.devicePixelRatio || 1);
  var REPOUSO = 220;                 /* ms parado até o quadro fino */

  /* luz das unidades: apagada por padrão; a escolhida acende, o andar brilha */
  /* teto = 1 spot por vão (Renders 1 e 3): pequeno, precisa de mais brilho para ler como ponto.
     Só a escolhida acende de verdade; o resto do andar mal sobe da base (contraste) */
  /* janelas apagadas = vidro escuro (correção do usuário em 15/10: não há cortina amarela, é
     porta de vidro); só a escolhida acende e mostra o ambiente */
  /* Render 3 (16/10/2026): todos os studios com o ambiente aceso em tom quente atrás do vidro;
     a escolhida acende bem mais e o andar dela um pouco mais que o resto */
  var LUZ = { janela: 4.2, teto: 5.0 }, LUZ_ANDAR = { janela: 1.4, teto: 2.6 }, LUZ_BASE = { janela: 0.42, teto: 2.0 };   /* 16/10: cortinas de voil creme acesas como nos Renders 6/7 (antes 0,62, escuras) */

  /* conteúdo oficial do painel — não inventar nada além disto */
  var METRAGENS = [['Área total', '29,92 m²'], ['Studio', '22,44 m²'], ['Sacada', '7,48 m²']];
  /* a planta nao traz o norte: o painel diz em que ala e de que lado fica,
     nunca um ponto cardeal (as chaves internas norte/oeste sao so nomes de face) */
  var FACHADAS = { norte: 'Ala dos studios 17 a 30 · fachada externa',
                   sul_barra: 'Ala dos studios 17 a 30 · face interna do L',
                   leste_haste: 'Ala dos studios 01 a 16 · face interna do L',
                   oeste: 'Ala dos studios 01 a 16 · fachada externa' };

  var THREE, R, scene, cam, model, composer, bloom, ceuEnv = null, ceuCubo = null;
  var hemi = null, hemiS0 = null, hemiG0 = null, SPOTS = null;   /* luz de céu (tingida pela direção) e spots das sacadas */
  var yaw = YAW_START, pitch = PITCH_START, dist = DIST_START;
  var alvoYaw = yaw, alvoPitch = pitch, alvoDist = dist;
  var centro = CENTRO.slice(), alvoCentro = CENTRO.slice();
  /* deslocamento da LENTE (fração da tela) para o studio escolhido cair na área livre ao lado
     do card — a câmera continua mirando o studio (antes ela deslocava o alvo ~20 m e, nos
     cantos, passava a olhar o studio através da outra ala) */
  var desloc = [0, 0], alvoDesloc = [0, 0];
  var vYaw = 0, solto = false, girando = !mqReduce.matches;
  var unidades = {}, unidadesPorAndar = {}, escolhida = null, mods3 = null;
  var transicoes = [];               /* luzes acendendo/apagando */
  var partiu = false, vivo = false, visivel = true, expandido = false;

  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
  /* menor inclinação possível: a câmera fica pelo menos CHAO_MIN acima do chão */
  /* altura mínima do olho: 1,7 m da calçada; perto o bastante para estar sobre o embasamento
     (quinas a ~46 m do centro), 1,7 m acima do deque */
  function chaoMin() { return CHAO_MIN; }   /* olho a 1,7 m do chão (e a ~0,7 m acima do deque NO) */
  function pitchMin() { return Math.max(-0.4, Math.asin(clamp((chaoMin() - alvoCentro[1]) / Math.max(1, alvoDist), -1, 1))); }
  /* inclinação máxima: de perto, olhar de cima poria a câmera dentro da torre */
  function pitchMax() {
    var d = Math.max(1, alvoDist);
    if (d <= R_LIVRE) return PITCH_MAX;
    var pA = Math.acos(R_LIVRE / d), sB = (Y_LIVRE - alvoCentro[1]) / d;
    if (sB <= 1 && Math.asin(clamp(sB, -1, 1)) <= pA) return PITCH_MAX;
    return Math.min(PITCH_MAX, pA);
  }
  /* até onde o alvo sobe e desce nesta distância (de longe, fica no meio da torre) */
  function faixaAltura(d) {
    var t = clamp((DIST_START - d) / (DIST_START - 110), 0, 1);
    return [CENTRO[1] + (ALT_MIN - CENTRO[1]) * t, CENTRO[1] + (ALT_MAX - CENTRO[1]) * t];
  }
  /* metros por pixel na distância do alvo: arrastar leva o prédio junto com o dedo */
  function metroPorPx() { return 2 * alvoDist * Math.tan(cam.fov * Math.PI / 360) / Math.max(1, canvas.clientHeight); }
  /* peso do arrasto vertical que vira subir/descer (perto) em vez de inclinar (longe) */
  function pesoAltura() { var t = clamp((150 - alvoDist) / 40, 0, 1); return t * t * (3 - 2 * t); }
  function syDe(clientY) { var r = canvas.getBoundingClientRect(); return -((clientY - r.top) / Math.max(1, r.height) * 2 - 1); }
  function pad(n) { return (n < 10 ? '0' : '') + n; }

  /* ------------------------------------------------------------
     CENA — hora azul como no hero: céu de entardecer, luz de céu suave,
     calor do térreo e das unidades acesas.
     ------------------------------------------------------------ */
  /* ------------------------------------------------------------
     CHÃO — plano, de tijolinho de calçada em volta do embasamento (correção do
     usuário: nada de lago). Textura feita aqui num canvas: tijolos de 20 x 10 cm
     em fiadas desencontradas, tom de calçada à noite, juntas escuras. A névoa
     funde o chão com o horizonte. A água fica só na piscina do deque.
     ------------------------------------------------------------ */

  /* CHÃO MOLHADO — reflexo planar (Renders 2, 3, 9 e 10): só no DESKTOP e só no quadro fino
     PARADO. Meia resolução, um plano por vez (rua, embarque ou deque, o mais perto do alvo da
     câmera); durante o movimento o reflexo some (uReflOn = 0) e o chão só fica mais escuro, igual
     parado, para não pular. No celular nada disso existe: nenhum passe novo. */
  var REFL = null;                   /* { rt, cam, u, chao[] } */
  function reflexoCria(THREE) {
    var rt = new THREE.WebGLRenderTarget(4, 4, { type: THREE.HalfFloatType, depthBuffer: true });
    REFL = { rt: rt, cam: new THREE.PerspectiveCamera(), y: CHAO_Y,
      u: { uRefl: { value: rt.texture }, uTexMat: { value: new THREE.Matrix4() }, uReflOn: { value: 0 }, uReflY: { value: CHAO_Y } }, chao: [] };
    return REFL;
  }
  /* trecho de fragment shader: mistura o reflexo (Fresnel, estrias verticais, ondulação mínima)
     no gl_FragColor antes do tone mapping. 'base' escurece o chão molhado sempre (não pula ao parar) */
  function reflexoGLSL(vm, base, peso) {
    return '{ vec4 pr = uTexMat * vec4(' + vm + ', 1.0); vec2 uvr = pr.xy / pr.w;\n' +
      '  vec3 vdir = normalize(cameraPosition - ' + vm + '); float cosv = clamp(vdir.y, 0.0, 1.0);\n' +
      '  float fr = min(0.04 + 0.96 * pow(1.0 - cosv, 5.0), 0.20);\n' +   /* teto no reflexo rasante: a 190 m o piso virava um espelho nítido da fachada (cunha escura) */
      
      '  vec2 wv = ' + vm + '.xz * 2.5;\n' +
      '  uvr.x += (sin(wv.y * 1.7 + sin(wv.x * 0.8) * 2.0) + 0.5 * sin(wv.x * 3.1 + wv.y * 0.7)) * 0.0008;\n' +
      '  uvr += normal.xy * 0.045;\n' +   /* relevo das pedras quebra o reflexo (pedra molhada, não espelho) */
      '  vec3 rf = vec3(0.0); float sw = 0.0;\n' +
      '  for (int k = -4; k <= 4; k++) { float fk = float(k); float wk = exp(-fk * fk / 6.0); rf += texture2D(uRefl, uvr + vec2(fk * 0.004, fk * 0.024)).rgb * wk; sw += wk; }\n' +
      '  rf = rf / sw * 0.15 * ' + peso.toFixed(2) + ';\n' +
      '  float molhado = (1.0 - smoothstep(22.0, 80.0, length(' + vm + '.xz - vec2(24.5, 22.0)))) * (1.0 - smoothstep(0.2, 0.5, abs(' + vm + '.y - uReflY)));\n' +
      '  gl_FragColor.rgb = gl_FragColor.rgb * mix(1.0, ' + base.toFixed(2) + ', molhado) + rf * fr * uReflOn * molhado;\n' +
      '}\n';
  }
  /* escolhe o plano pelo alvo da câmera: embarque (entrada) e deque NO têm cota própria */
  function reflexoPlano() {
    var cx = alvoCentro[0], cz = alvoCentro[2], px = cam.position.x, py = cam.position.y, pz = cam.position.z;
    if (Math.sqrt(px * px + pz * pz) < 70 && py < 30 && cx < 20 && cz < 20) return 2.08;
    return hgt(cx, cz);   /* o terreno cai para o norte: o plano segue o alvo (o erro fora dele, < 0,45 m, some na máscara abaixo) */
  }
  function reflexoDesenha() {
    if (!REFL) return;
    var w = Math.max(4, Math.round(R.domElement.width * 0.5)), h = Math.max(4, Math.round(R.domElement.height * 0.5));
    if (REFL.rt.width !== w || REFL.rt.height !== h) REFL.rt.setSize(w, h);
    var YR = REFL.u.uReflY.value = reflexoPlano();
    var c = REFL.cam, n = new THREE.Vector3(0, 1, 0), p0 = new THREE.Vector3(0, YR, 0);
    cam.updateMatrixWorld();
    var cp = new THREE.Vector3().setFromMatrixPosition(cam.matrixWorld);
    if (cp.y <= YR + 0.05) { REFL.u.uReflOn.value = 0; return; }
    var rot = new THREE.Matrix4().extractRotation(cam.matrixWorld);
    var look = new THREE.Vector3(0, 0, -1).applyMatrix4(rot).add(cp);
    c.position.set(cp.x, 2 * YR - cp.y, cp.z);
    c.up.set(0, 1, 0).applyMatrix4(rot); c.up.y = -c.up.y;
    c.lookAt(look.x, 2 * YR - look.y, look.z); c.updateMatrixWorld(); c.matrixWorldInverse.copy(c.matrixWorld).invert();
    c.projectionMatrix.copy(cam.projectionMatrix); c.projectionMatrixInverse.copy(cam.projectionMatrixInverse);
    var tm = REFL.u.uTexMat.value;
    tm.set(0.5, 0, 0, 0.5, 0, 0.5, 0, 0.5, 0, 0, 0.5, 0.5, 0, 0, 0, 1); tm.multiply(c.projectionMatrix); tm.multiply(c.matrixWorldInverse);
    /* plano de corte oblíquo: nada abaixo do chão entra no reflexo */
    var pl = new THREE.Plane().setFromNormalAndCoplanarPoint(n, p0); pl.applyMatrix4(c.matrixWorldInverse);
    var cpl = new THREE.Vector4(pl.normal.x, pl.normal.y, pl.normal.z, pl.constant), e = c.projectionMatrix.elements, q = new THREE.Vector4();
    q.x = (Math.sign(cpl.x) + e[8]) / e[0]; q.y = (Math.sign(cpl.y) + e[9]) / e[5]; q.z = -1.0; q.w = (1.0 + e[10]) / e[14];
    cpl.multiplyScalar(2.0 / cpl.dot(q)); e[2] = cpl.x; e[6] = cpl.y; e[10] = cpl.z + 1.0 - 0.003; e[14] = cpl.w;
    REFL.chao.forEach(function (m) { m.visible = false; });
    var ant = R.getRenderTarget();
    R.setRenderTarget(REFL.rt); R.clear(); R.render(scene, c); R.setRenderTarget(ant);
    REFL.chao.forEach(function (m) { m.visible = true; });
    REFL.u.uReflOn.value = 1;
  }
  /* liga o reflexo num material (uniforms + varying da posição no mundo) */
  function reflexoLiga(mat, base, peso) {
    if (!REFL || mat.userData.refl) return; mat.userData.refl = true;
    encadeia(mat, 'refl', function (sh) {
      sh.uniforms.uRefl = REFL.u.uRefl; sh.uniforms.uTexMat = REFL.u.uTexMat; sh.uniforms.uReflOn = REFL.u.uReflOn; sh.uniforms.uReflY = REFL.u.uReflY;
      sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vMundoR;')
        .replace('#include <project_vertex>', '#include <project_vertex>\nvec4 wpR = vec4(transformed, 1.0);\n#ifdef USE_INSTANCING\nwpR = instanceMatrix * wpR;\n#endif\nvMundoR = (modelMatrix * wpR).xyz;');
      sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nvarying vec3 vMundoR;\nuniform sampler2D uRefl;\nuniform mat4 uTexMat;\nuniform float uReflOn;\nuniform float uReflY;')
        .replace('#include <tonemapping_fragment>', reflexoGLSL('vMundoR', base, peso) + '#include <tonemapping_fragment>');
    });
    mat.needsUpdate = true;
  }

  /* PARALELEPÍPEDO dos Renders 4, 6 e 10: granito cinza-escuro em fiadas desencontradas,
     pedras de ~12 cm levemente abauladas e juntas escuras. Três texturas de 256 px por metro
     (cor, relevo e rugosidade); molhado perto da torre — brilha nas cabeças das pedras e
     reflete o céu — e seco e fosco ao longe (no shader do chão). */
  function texturasCalcada(THREE) {
    var N = 256, NP = 8, S = N / NP, semente = 7;
    var rnd = function () { semente = (semente * 16807) % 2147483647; return semente / 2147483647; };
    var alt = new Float32Array(N * N), tom = new Float32Array(N * N), rug = new Float32Array(N * N);
    for (var i0 = 0; i0 < N * N; i0++) { tom[i0] = 26; rug[i0] = 0.22; }          /* juntas: escuras e com água */
    for (var r = 0; r < NP; r++) {
      var off = rnd() * S;
      for (var k = -1; k <= NP; k++) {
        var cx = k * S + off + S / 2 + (rnd() - 0.5) * 3, cy = r * S + S / 2 + (rnd() - 0.5) * 2;
        var hx = S * (0.40 + rnd() * 0.05), hy = S * (0.38 + rnd() * 0.05);
        var t = 62 + rnd() * 34, rg = 0.42 + rnd() * 0.22;
        for (var y = Math.floor(cy - hy) - 1; y <= cy + hy + 1; y++) {
          for (var x = Math.floor(cx - hx) - 1; x <= cx + hx + 1; x++) {
            var u = (x - cx) / hx, v = (y - cy) / hy, e = Math.pow(u * u * u * u + v * v * v * v, 0.25);
            if (e >= 1) continue;
            var X = ((x % N) + N) % N, Y = ((y % N) + N) % N, j = Y * N + X;
            var a = Math.sqrt(1 - e * e);
            alt[j] = a; tom[j] = t * (0.82 + 0.18 * a) + (rnd() - 0.5) * 9; rug[j] = rg - 0.12 * a;
          }
        }
      }
    }
    function canvasDe(f) {
      var c = document.createElement('canvas'); c.width = c.height = N;
      var g = c.getContext('2d'), img = g.createImageData(N, N);
      for (var j = 0; j < N * N; j++) { var px = f(j); img.data[j * 4] = px[0]; img.data[j * 4 + 1] = px[1]; img.data[j * 4 + 2] = px[2]; img.data[j * 4 + 3] = 255; }
      g.putImageData(img, 0, 0);
      var tx = new THREE.CanvasTexture(c);
      tx.wrapS = tx.wrapT = THREE.RepeatWrapping; tx.anisotropy = R.capabilities.getMaxAnisotropy();
      return tx;
    }
    var cor = canvasDe(function (j) { var t = tom[j]; return [t + 2, t, t - 3]; });
    cor.colorSpace = THREE.SRGBColorSpace;
    var nrm = canvasDe(function (j) {
      var x = j % N, y = (j - x) / N;
      var dx = alt[y * N + (x + 1) % N] - alt[y * N + (x + N - 1) % N];
      var dy = alt[((y + 1) % N) * N + x] - alt[((y + N - 1) % N) * N + x];
      var nx = -dx * 1.6, ny = dy * 1.6, l = Math.sqrt(nx * nx + ny * ny + 1);
      return [(nx / l * 0.5 + 0.5) * 255, (ny / l * 0.5 + 0.5) * 255, (1 / l * 0.5 + 0.5) * 255];
    });
    var rgh = canvasDe(function (j) { var v = rug[j] * 255; return [v, v, v]; });
    return { cor: cor, nrm: nrm, rgh: rgh };
  }

  function montaChao(THREE, ceuEnv) {
    /* terreno vem do .glb (extras.terreno do gerador): fonte única (ver TERR acima) */
    var raizT = model && model.getObjectByName('CINNAMON_FACHADA_PROVISORIO'), TER = raizT && raizT.userData && raizT.userData.terreno;
    if (TER) { Object.keys(TER).forEach(function (k) { if (k in TERR) TERR[k] = TER[k]; }); CHAO_Y = TERR.chaoL; CHAO_MIN = TERR.chaoL + 1.7; }
    var tam = 3600, tx = texturasCalcada(THREE);
    [tx.cor, tx.nrm, tx.rgh].forEach(function (t) { t.repeat.set(tam, tam); });
    /* Render 3: piso escuro e molhado na frente da torre, espelhando o céu e as luzes */
    var mat = new THREE.MeshStandardMaterial({ map: tx.cor, color: 0xa39a8e,   /* tom QUENTE (Renders 6/10: pedra molhada marrom-acinzentada; com a luz de céu azulada o chão lia azul) */ normalMap: tx.nrm, normalScale: new THREE.Vector2(0.9, 0.9),
      roughnessMap: tx.rgh, roughness: 1, metalness: 0, envMap: ceuEnv, envMapIntensity: 0.55 });
    /* ao longe: seco e fosco, e escurece até a cor de baixo do horizonte (o céu abaixo da linha
       tem a mesma cor) — o limite chão × céu fica nítido, sem faixa de névoa. A mistura é feita
       ANTES do tone mapping, como no céu (no celular a névoa padrão do three entra depois) */
    mat.fog = false;
    /* a névoa ao longe pega a cor do céu logo abaixo do horizonte naquela direção (ardósia
       escura, mais clara do lado do sol — ver o céu): a linha chão × céu fica nítida */
    var densidade = DBG.indexOf('nevoa0') < 0 ? 0.0011 : 0.0;
    if (!leve) reflexoCria(THREE);
    mat.onBeforeCompile = function (sh) {
      if (REFL) { sh.uniforms.uRefl = REFL.u.uRefl; sh.uniforms.uTexMat = REFL.u.uTexMat; sh.uniforms.uReflOn = REFL.u.uReflOn; sh.uniforms.uReflY = REFL.u.uReflY; }
      sh.uniforms.uCeu = { value: ceuCubo }; sh.uniforms.uDens = { value: densidade };
      sh.uniforms.uCentro = { value: new THREE.Vector2(CENTRO[0], CENTRO[2]) };
      /* posição no mundo por varying (o plano tem só 4 vértices) */
      sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vMundo;')
        .replace('#include <project_vertex>', '#include <project_vertex>\nvMundo = (modelMatrix * vec4(transformed, 1.0)).xyz;');
      sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nvarying vec3 vMundo;\nuniform samplerCube uCeu;\nuniform float uDens;\nuniform vec2 uCentro;' + (REFL ? '\nuniform sampler2D uRefl;\nuniform mat4 uTexMat;\nuniform float uReflOn;\nuniform float uReflY;' : ''))
        .replace('#include <roughnessmap_fragment>', '#include <roughnessmap_fragment>\n' +
          'roughnessFactor = mix(max(roughnessFactor, 0.28), 0.97, smoothstep(40.0, 75.0, length(vMundo.xz - uCentro)));')
        .replace('#include <tonemapping_fragment>', (REFL ? reflexoGLSL('vMundo', 0.85, 0.5) : '') +
          'float dd = length(vMundo - cameraPosition);\n' +
          'vec3 dv = normalize(vMundo - cameraPosition);\n' +
          'vec3 uNeb = textureCube(uCeu, normalize(vec3(dv.x, -0.02, dv.z))).rgb;\n' +
          'gl_FragColor.rgb = mix(gl_FragColor.rgb, uNeb, 1.0 - exp(-pow(dd * uDens, 2.0)));\n' +
          '#include <tonemapping_fragment>');
    };
    mat.customProgramCacheKey = function () { return 'chao-paralelepipedo-ceu'; };
    if (DBG.indexOf('chao0') >= 0) mat = new THREE.MeshBasicMaterial({ color: 0x1d1b20 });
    /* o chão é uma grade que acompanha hgt(x, z), com um VÃO no lugar do térreo (x −0,4…53,1 × z −0,7…46,6): sob o térreo ficam os pisos do FBX e as
       piscinas do deque, que descem abaixo do chão (fundo a 0,5 m) — um plano inteiro as taparia e o fundo delas viraria calçada. Os pisos do FBX
       passam alguns cm além do vão, então não há fresta. Linhas a cada 2 m onde o terreno inclina (z de −0,7 a 24); fora, linhas grossas.
       UV = metros do mundo (a textura repete a cada metro). */
    var HX0 = -0.4, HX1 = 53.1, HZ0 = -0.7, HZ1 = 46.6, B = 2000;
    var gx = [-B, -60, TERR.xO, HX0, HX1, TERR.xL, 110, B], gz = [-B, -60, TERR.zN0, HZ0];
    for (var zz = HZ0 + 2; zz < TERR.zN1; zz += 2) gz.push(zz);
    gz.push(TERR.zN1, HZ1, 90, B);
    gx.sort(function (p, q) { return p - q; }); gz.sort(function (p, q) { return p - q; });
    var pP = [], pU = [], pI = [], nxl = gx.length;
    for (var jz = 0; jz < gz.length; jz++) for (var jx = 0; jx < nxl; jx++) { pP.push(gx[jx], hgt(gx[jx], gz[jz]), gz[jz]); pU.push(gx[jx] / tam, gz[jz] / tam); }
    for (var kz = 0; kz < gz.length - 1; kz++) for (var kx = 0; kx < nxl - 1; kx++) {
      var cxm = (gx[kx] + gx[kx + 1]) / 2, czm = (gz[kz] + gz[kz + 1]) / 2;
      if (cxm > HX0 && cxm < HX1 && czm > HZ0 && czm < HZ1) continue;          /* o vão do prédio */
      var q0 = kz * nxl + kx, q1 = q0 + 1, q2 = q0 + nxl, q3 = q2 + 1;
      pI.push(q0, q2, q1, q1, q2, q3);
    }
    var gC = new THREE.BufferGeometry();
    gC.setAttribute('position', new THREE.Float32BufferAttribute(pP, 3));
    gC.setAttribute('uv', new THREE.Float32BufferAttribute(pU, 2));
    gC.setIndex(pI); gC.computeVertexNormals();
    var calcada = new THREE.Mesh(gC, mat);
    calcada.name = 'chao_calcada';
    if (REFL) REFL.chao.push(calcada);
    calcada.receiveShadow = true;
    scene.add(calcada);
  }

  /* PISCINA — água de verdade (pedido do usuário em 14/10): transparente olhando de cima,
     espelho olhando de raspão (Fresnel feito no shader), refletindo o céu do entardecer com
     ondinhas finas que quebram o reflexo em brilhos. As cáusticas — a rede de luz que a
     ondulação desenha — ficam no fundo de mármore, numa lâmina somada por baixo da água. */
  function texturasDaAgua(THREE) {
    var N = 256, c = document.createElement('canvas'); c.width = c.height = N;
    var g = c.getContext('2d'), img = g.createImageData(N, N), h = new Float32Array(N * N);
    for (var y = 0; y < N; y++) for (var x = 0; x < N; x++) {
      var u = x / N * Math.PI * 2, v = y / N * Math.PI * 2;
      h[y * N + x] = Math.sin(u * 3 + Math.sin(v * 2) * 1.3) + 0.6 * Math.sin(v * 5 + u * 2) + 0.35 * Math.sin((u - v) * 7)
                   + 0.18 * Math.sin(u * 13 + v * 4) + 0.12 * Math.sin(v * 17 - u * 6);
    }
    for (var y2 = 0; y2 < N; y2++) for (var x2 = 0; x2 < N; x2++) {
      var dx = h[y2 * N + (x2 + 1) % N] - h[y2 * N + (x2 + N - 1) % N];
      var dy = h[((y2 + 1) % N) * N + x2] - h[((y2 + N - 1) % N) * N + x2];
      var nx = -dx * 0.6, ny = -dy * 0.6, nz = 1, l = Math.sqrt(nx * nx + ny * ny + 1), k = (y2 * N + x2) * 4;
      img.data[k] = (nx / l * 0.5 + 0.5) * 255; img.data[k + 1] = (ny / l * 0.5 + 0.5) * 255;
      img.data[k + 2] = (nz / l * 0.5 + 0.5) * 255; img.data[k + 3] = 255;
    }
    g.putImageData(img, 0, 0);
    var nrm = new THREE.CanvasTexture(c);
    nrm.wrapS = nrm.wrapT = THREE.RepeatWrapping; nrm.repeat.set(1.6, 1.6);   /* ondinhas de 15 a 80 cm */
    var c2 = document.createElement('canvas'); c2.width = c2.height = N;
    var g2 = c2.getContext('2d'), img2 = g2.createImageData(N, N);
    for (var y3 = 0; y3 < N; y3++) for (var x3 = 0; x3 < N; x3++) {
      var a = x3 / N * Math.PI * 2, b = y3 / N * Math.PI * 2;
      var r1 = Math.abs(Math.sin(a * 4 + Math.sin(b * 3) * 1.7)), r2 = Math.abs(Math.sin(b * 5 + Math.sin(a * 2) * 1.4));
      var r3 = Math.abs(Math.sin((a + b) * 3 + Math.sin(a * 5) * 0.9));
      var e = 1 - Math.min(r1, r2, r3), v = e < 0.8 ? 0 : Math.pow((e - 0.8) / 0.2, 1.6);   /* só a rede acende */
      var k2 = (y3 * N + x3) * 4;
      img2.data[k2] = 255 * v; img2.data[k2 + 1] = 226 * v; img2.data[k2 + 2] = 180 * v; img2.data[k2 + 3] = 255;
    }
    g2.putImageData(img2, 0, 0);
    var caus = new THREE.CanvasTexture(c2);
    caus.wrapS = caus.wrapT = THREE.RepeatWrapping; caus.repeat.set(0.6, 0.6); caus.colorSpace = THREE.SRGBColorSpace;
    return { nrm: nrm, caus: caus };
  }

  function vidroFresnel(mat, aMin, aMax, rMin, rMax, intens) {
    mat.userData.fresnel = true;
    mat.envMap = ceuEnv; mat.envMapIntensity = intens;
    mat.onBeforeCompile = function (sh) {
      sh.fragmentShader = sh.fragmentShader.replace('#include <opaque_fragment>',
        'float fresV = pow(1.0 - clamp(abs(dot(normalize(vViewPosition), normal)), 0.0, 1.0), 3.0);\n' +
        'float aV = mix(' + aMin.toFixed(3) + ', ' + aMax.toFixed(3) + ', fresV);\n' +
        'gl_FragColor = vec4(outgoingLight + radiance * mix(' + rMin.toFixed(3) + ', ' + rMax.toFixed(3) + ', fresV) / aV, aV);');
    };
    mat.customProgramCacheKey = function () { return 'vidro-' + mat.name; };
  }

  function aguaDaPiscina(THREE, ceuEnv, tx) {
    var agua = new THREE.MeshStandardMaterial({
      name: 'agua_piscina', color: 0x000000, roughness: 0.04, metalness: 0.0, fog: false,
      normalMap: tx.nrm, normalScale: new THREE.Vector2(0.28, 0.28),
      envMap: ceuEnv, envMapIntensity: 0.15, transparent: true, depthWrite: false   /* 16/10/2026 ("água mais transparente, reflexo suave"): 0,32 → 0,15. Céu HDR: com 1,1 o horizonte
         creme/dourado deixava a água branca de raspão; no Render 9 ela é verde-escura com brilhos */
    });
    /* água não tem cor própria (difuso preto): só reflexo e o que se vê através.
       Fresnel: de cima se vê o fundo, de raspão vira espelho. A saída é dividida pelo alfa
       para o reflexo não sair apagado pela mistura — o fundo escurece (absorção), o brilho fica */
    agua.onBeforeCompile = function (sh) {
      sh.fragmentShader = sh.fragmentShader.replace('#include <opaque_fragment>',
        'float fres = pow(1.0 - clamp(dot(normalize(vViewPosition), normal), 0.0, 1.0), 3.0);\n' +
        'float aAg = mix(0.20, 0.68, fres);\n' +                                   /* de cima: 80% transparente, se vê o fundo claro da piscina */
        'outgoingLight += radiance * mix(0.01, 0.10, fres);\n' +                  /* reflexo só de raspão e suave */
        'gl_FragColor = vec4(outgoingLight / aAg, aAg);');
    };
    agua.customProgramCacheKey = function () { return 'agua-fresnel'; };
    return agua;
  }

  /* rede de luz no fundo: mesma forma da lâmina, 41 cm abaixo (fundo em -0,6, água em -0,18) */
  function causticasDaPiscina(THREE, aguaMesh, tx) {
    var mat = new THREE.MeshBasicMaterial({ name: 'causticas', map: tx.caus, color: 0xb7a48e, transparent: true,
      opacity: 0.06, blending: THREE.AdditiveBlending, depthWrite: false, fog: false });
    var m = new THREE.Mesh(aguaMesh.geometry, mat);
    m.position.y = -0.405; m.renderOrder = -1; m.castShadow = false; m.receiveShadow = false;
    m.raycast = function () {};
    return m;
  }

  function monta(mods, glb) {
    THREE = mods.three;
    R = new THREE.WebGLRenderer({ canvas: canvas, antialias: !leve, alpha: false, powerPreference: 'high-performance' });
    R.toneMapping = THREE.ACESFilmicToneMapping;
    R.toneMappingExposure = 1.4;   /* renders de referencia sao mais claros (15/10/2026) */
    /* PCF simples: a sombra é calculada uma vez só e a PCFSoft deixava cada shader bem mais
       pesado de compilar (no Mac a 1ª compilação chegava a travar segundos) */
    if (!leve && DBG.indexOf('sombra0') < 0) { R.shadowMap.enabled = true; R.shadowMap.type = THREE.PCFShadowMap; }

    scene = new THREE.Scene();
    cam = new THREE.PerspectiveCamera(30, 1, 1, 9000);

    /* reflexos de ambiente fracos (scene.environmentIntensity só existe a partir do r163 —
       aqui vai material a material) */
    var ENV = 0.3;    /* um pouco mais de ambiente que antes, sem lustrar os pisos */
    var pmrem = new THREE.PMREMGenerator(R);
    scene.environment = pmrem.fromScene(new mods.RoomEnvironment(), 0.04).texture;
    pmrem.dispose();

    /* CÉU — um céu só para os Renders 2, 3, 9 e 10 (pedido do usuário em 16/10/2026: "até o
       céu nesse estilo"), variando com o ângulo até o sol já posto:
       - de frente para o sol (Render 2): horizonte laranja-dourado, pêssego empoeirado e um campo
         de altocúmulos em células com a barriga acesa em dourado; o alto cinza-azulado escuro;
       - de lado (Render 3): azul limpo que clareia até um creme quase branco no horizonte,
         tufos baixos cinza-violeta, um banco de nuvem escura e fiapos de cirro;
       - de costas (Renders 3 e 10): azul saturado e, no alto, um teto de nuvem tempestuoso
         azul-escuro com bordas azul-lavanda.
       Abaixo do horizonte, ardósia escura (o chão ao longe cai nessa cor: linha nítida).
       As cores são as dos renders JÁ na tela: cada parada foi invertida do tone mapping ACES
       com exposição 1,4 (uExpo corrige se a exposição mudar) e o cubo é HDR (meia precisão) —
       o creme e o dourado do horizonte passam de 1. O azul é exceção do usuário, só neste céu. */
    var solDir = new THREE.Vector3(Math.cos(SOL_ALT_CEU) * Math.sin(SOL_AZ), Math.sin(SOL_ALT_CEU), Math.cos(SOL_ALT_CEU) * Math.cos(SOL_AZ));
    var sky = new THREE.ShaderMaterial({
      side: THREE.BackSide, depthWrite: false, fog: false,
      uniforms: { sol: { value: solDir }, uExpo: { value: 1.4 / R.toneMappingExposure } },
      vertexShader: 'varying vec3 p;void main(){p=position;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}',
      fragmentShader: [
        'uniform vec3 sol;uniform float uExpo;varying vec3 p;',
        /* ruído 3D na esfera (sem emenda no azimute): o tamanho das nuvens fica em graus */
        'float h3(vec3 p){p=fract(p*.1031);p+=dot(p,p.zyx+31.32);return fract((p.x+p.y)*p.z);}',
        'float n3(vec3 x){vec3 i=floor(x),f=fract(x);f=f*f*(3.-2.*f);',
        ' return mix(mix(mix(h3(i),h3(i+vec3(1,0,0)),f.x),mix(h3(i+vec3(0,1,0)),h3(i+vec3(1,1,0)),f.x),f.y),',
        '            mix(mix(h3(i+vec3(0,0,1)),h3(i+vec3(1,0,1)),f.x),mix(h3(i+vec3(0,1,1)),h3(i+vec3(1,1,1)),f.x),f.y),f.z);}',
        'float fbm(vec3 x){float v=0.,a=.5;for(int i=0;i<6;i++){v+=a*n3(x);x=x*2.03+vec3(1.7,9.2,3.1);a*=.5;}return v;}',
        /* lado oposto ao sol: horizonte #7f93ab, #5d7c9c, #3c628a, #244e78, zênite #183c63 (Render 3) */
        'vec3 frio(float h){vec3 c=mix(vec3(.1225,.1683,.2429),vec3(.0743,.1236,.1980),smoothstep(0.,.06,h));',
        ' c=mix(c,vec3(.0427,.0858,.1566),smoothstep(.06,.18,h));c=mix(c,vec3(.0239,.0596,.1119),smoothstep(.18,.36,h));',
        ' return mix(c,vec3(.0294,.0584,.1136),smoothstep(.36,.8,h));}',
        /* de lado, cinza-lilás enevoado (borda direita do Render 3) */
        'vec3 lado(float h){vec3 c=vec3(.1184,.1299,.1649);c=mix(c,vec3(.1735,.1847,.2190),smoothstep(.057,.108,h));',
        ' c=mix(c,vec3(.1209,.1660,.2394),smoothstep(.108,.159,h));c=mix(c,vec3(.0901,.1414,.2209),smoothstep(.159,.226,h));',
        ' c=mix(c,vec3(.0632,.1139,.1961),smoothstep(.226,.292,h));c=mix(c,vec3(.0491,.0978,.1740),smoothstep(.292,.354,h));',
        ' c=mix(c,vec3(.0373,.0772,.1387),smoothstep(.354,.428,h));c=mix(c,vec3(.020,.062,.115),smoothstep(.428,.495,h));',
        ' return mix(c,vec3(.018,.058,.109),smoothstep(.495,.55,h));}',
        /* de lado para o sol: creme quase branco no horizonte, cinza-lilás, azul (Render 3) */
        'vec3 creme(float h){vec3 c=mix(vec3(.8955,.2638,.1207),vec3(1.0707,.3106,.1379),smoothstep(0.,.06,h));',
        ' c=mix(c,vec3(2.3865,.7271,.2163),smoothstep(.06,.117,h));c=mix(c,vec3(2.6093,.7814,.3290),smoothstep(.117,.17,h));',
        ' c=mix(c,vec3(1.2280,.6632,.5331),smoothstep(.17,.245,h));c=mix(c,vec3(.4088,.4002,.4817),smoothstep(.245,.31,h));',
        ' c=mix(c,vec3(.2144,.2611,.3754),smoothstep(.31,.38,h));c=mix(c,vec3(.1463,.1928,.2872),smoothstep(.38,.455,h));',
        ' c=mix(c,vec3(.0946,.1433,.2142),smoothstep(.455,.525,h));c=mix(c,vec3(.0744,.1122,.1747),smoothstep(.525,.58,h));',
        ' return mix(c,vec3(.0455,.0820,.1421),smoothstep(.58,.95,h));}',
        /* de frente para o sol: laranja-dourado #f6a447 e #f8c47c no horizonte, pêssego empoeirado,
           cinza e o alto cinza-azulado escuro (Render 2) */
        'vec3 ouro(float h){h*=1.4;vec3 c=mix(vec3(1.157,.219,.0096),vec3(1.072,.243,.045),smoothstep(0.,.06,h));c=mix(c,vec3(.741,.241,.077),smoothstep(.06,.14,h));',
        ' c=mix(c,vec3(.488,.216,.103),smoothstep(.14,.2,h));c=mix(c,vec3(.188,.093,.057),smoothstep(.2,.29,h));',
        ' c=mix(c,vec3(.0705,.0743,.0866),smoothstep(.29,.42,h));return mix(c,vec3(.042,.044,.052),smoothstep(.42,.6,h));}',
        'void main(){vec3 d=normalize(p);',
        ' vec2 dz=normalize(d.xz+vec2(1e-5));float teta=acos(clamp(dot(dz,normalize(sol.xz)),-1.,1.));',
        ' float w=1.-smoothstep(1.55,2.0,teta);',                           /* lado quente (dourado + creme) */
        ' float perto=1.-smoothstep(.6,1.5,teta);',                     /* núcleo dourado em volta do sol */
        ' float h=max(d.y,0.);',
        ' vec3 base=mix(mix(lado(h),frio(h),smoothstep(2.4,2.75,teta)),mix(creme(h),ouro(h),perto),w);',
        ' vec3 c;',
        ' if(d.y<0.){',                                                   /* abaixo: ardósia escura */
        '  c=vec3(.028,.032,.042)+vec3(dot(mix(mix(lado(0.),frio(0.),smoothstep(2.4,2.75,teta)),mix(creme(0.),ouro(0.),perto),w),vec3(.2126,.7152,.0722)))*.04;',
        ' }else{',
        '  c=base;',
        '  float mu=max(dot(d,normalize(sol)),0.);',
        '  c+=vec3(1.25,.36,.06)*pow(mu,9.)*(1.-smoothstep(0.,.10,h))*.12;',   /* clarão do sol logo abaixo do horizonte */
        /* C. fiapos de cirro: riscos finos, longos e fracos */
        '  vec3 pc=vec3(dz.x*2.4,h*34.,dz.y*2.4);',
        '  float ci=fbm(pc+vec3(fbm(pc*vec3(1.,.15,1.))*1.6,0.,0.));',
        '  float aci=smoothstep(.6,.8,ci)*smoothstep(.03,.07,h)*(1.-smoothstep(.22,.38,h))*mix(.2,.35,step(.5,w))*(1.-perto);',
        '  c=mix(c,mix(vec3(.1471,.2128,.3336),vec3(1.5907,1.0134,.9219),w*w),aci);',
        /* H. teto de nuvem: tempestuoso e azul no alto do lado oposto (Render 10); em volta do sol,
           um campo de altocúmulos em células, de barriga acesa em dourado (Render 2) */
        '  vec3 ph=vec3(dz.x*3.,h*5.,dz.y*3.)/(.35+h);',
        '  float wh=fbm(ph*.5+7.);',
        '  float nh=fbm(ph+vec3(wh*1.8))+(fbm(ph*3.5)-.5)*.2;',
        '  vec3 pm=vec3(dz.x*10.,h*16.,dz.y*10.)/(.3+h);',                 /* células pequenas (altocúmulo) */
        '  float nm=fbm(pm+vec3(fbm(pm*.3)*2.))*.75+nh*.35;',
        '  float nmUp=fbm(pm+vec3(0.,.5,0.)+vec3(fbm(pm*.3)*2.))*.75+nh*.35;',
        '  float covH=mix(.28,.48,w);',
        '  float lH=mix(.56,.3,smoothstep(2.4,2.75,teta));float kR=smoothstep(2.15,2.5,teta);',
        '  float aH=smoothstep(covH,covH+.16,nh)*smoothstep(lH,lH+.2,h)*(1.-perto*.6);',
        /* núcleo escuro, bordas finas azul-lavanda (é o contraste que desenha a nuvem no Render 10) */
        '  vec3 cH=mix(vec3(.0962,.1407,.2865)*.9,vec3(.0150,.0250,.0460),smoothstep(covH+.02,covH+.22,nh));',
        '  cH=mix(cH,vec3(.0962,.1407,.2865),clamp((nh-fbm(ph+vec3(0.,.25,0.)+vec3(wh*1.8)))*4.,0.,1.)*.6);',
        '  cH=mix(cH,vec3(.0424,.0473,.0640),w*.6);',
        '  cH=mix(cH,mix(vec3(.0419,.0602,.1066),vec3(.1182,.1588,.2993),1.-abs(2.*clamp(nh,0.,1.)-1.)),kR*.5);',
        '  c=mix(c,cH,aH*.95);',
        '  float aM=smoothstep(.60,.72,nm)*smoothstep(.02,.05,h)*(1.-smoothstep(.55,.9,h))*smoothstep(0.,.5,perto);',
        '  float acesa=clamp(.35+(nmUp-nm)*-9.,0.,1.)*(1.-smoothstep(.04,.3,h));',   /* barriga virada para o sol posto */
        '  vec3 cM=mix(mix(vec3(.125,.07,.052),vec3(.031,.033,.040),smoothstep(.40,.52,h)),',
        '             mix(vec3(1.16,.25,.03),vec3(1.0,.33,.12),smoothstep(.04,.3,h)),acesa);',
        '  c=mix(c,cM,aM*.95);',
        /* B. banco de nuvem escura a meia altura, do lado creme (Render 3) */
        '  vec3 pb=vec3(dz.x*2.1,h*5.5,dz.y*2.1);',
        '  float nb=fbm(pb+vec3(fbm(pb*.6+5.)*1.4))+(fbm(pb*4.)-.5)*.14;',
        '  float covb=mix(.7,.6,w);',
        '  float ab=smoothstep(covb,covb+.13,nb)*smoothstep(mix(.06,.27,w),mix(.1,.31,w),h)*(1.-smoothstep(mix(.2,.40,w),mix(.32,.47,w),h))*(1.-perto);',
        '  float topo=clamp((nb-fbm(pb+vec3(0.,.35,0.)+vec3(fbm(pb*.6+5.)*1.4)))*6.,0.,1.);',
        '  vec3 cb=mix(mix(vec3(.0359,.0542,.0851),vec3(.0577,.0600,.0747),w),vec3(.1571,.1725,.2204),topo*.5);',
        '  c=mix(c,cb,ab*.95);',
        /* A. tufos baixos e achatados perto do horizonte (~8° x 2,5°): cinza-violeta, núcleo escuro */
        '  vec3 pa=vec3(dz.x*7.,h*24.,dz.y*7.);',
        '  float na=fbm(pa+vec3(fbm(pa*.4)*1.2,0.,0.))+(fbm(pa*3.)-.5)*.12;',
        '  float covA=.6;',
        '  float aa=smoothstep(covA,covA+.03,na)*smoothstep(.03,.05,h)*(1.-smoothstep(mix(.09,.20,w),mix(.15,.26,w),h));',
        '  vec3 ca=mix(vec3(.0574,.0643,.085),vec3(.078,.0753,.092),w)*mix(1.2,.72,smoothstep(covA,covA+.18,na));',
        '  ca=mix(ca,vec3(.12,.06,.04),perto*.7);',                        /* contra o sol: silhueta quente-escura */
        '  c=mix(c,ca,aa*.93);',
        ' }',
        ' gl_FragColor=vec4(c*uExpo,1.);',
        ' #include <tonemapping_fragment>',
        ' #include <colorspace_fragment>',
        '}'].join('\n')
    });
    /* o céu é calculado UMA vez num cubo (sRGB de 8 bits: sem degraus no azul escuro) e vira o
       fundo da cena — o shader das nuvens custava caro em cada pixel de cada quadro e, com a
       câmera baixa, o céu ocupa quase a tela toda. O mesmo cubo gera o mapa de reflexo */
    /* (feito em etapa própria, num quadro só dele — ver assaCeu) */
    function assaCeu() {
      var ceuCena = new THREE.Scene(); ceuCena.add(new THREE.Mesh(new THREE.SphereGeometry(4200, 32, 16), sky));
      /* HDR (meia precisão, linear): o creme do horizonte passa de 1 antes do tone mapping, e o
         fundo linear passa pelo mesmo ACES da cena no desktop (OutputPass) e no celular */
      var hdr = R.extensions.has('EXT_color_buffer_half_float') || R.extensions.has('EXT_color_buffer_float');
      var cuboRT = new THREE.WebGLCubeRenderTarget(leve ? 512 : 1024, { generateMipmaps: false, type: hdr ? THREE.HalfFloatType : THREE.UnsignedByteType });   /* sem HDR na placa: 8 bits (o creme satura um pouco, mas nada fica preto) */
      ceuCubo = cuboRT.texture;
      new THREE.CubeCamera(1, 10000, cuboRT).update(R, ceuCena);
      scene.background = DBG.indexOf('ceu0') >= 0 ? new THREE.Color(0x26344f) : cuboRT.texture;
      /* o mesmo céu como mapa de reflexo: água da piscina, vidros, mármore e piso molhados */
      var pm2 = new THREE.PMREMGenerator(R);
      ceuEnv = pm2.fromCubemap(cuboRT.texture).texture; pm2.dispose();
      sky.dispose();
      model.traverse(function (o) {
        if (!o.isMesh) return;
        /* vidros de verdade (pedido do usuário em 15/10): de frente se vê a cortina acesa, de
           lado o vidro vira espelho do céu — Fresnel no shader, reflexo sem ser apagado pelo alfa */
        if (o.material.name === 'vidro_claro' && !o.material.userData.fresnel) vidroFresnel(o.material, 0.18, 0.8, 0.06, 0.6, 1.0);
        /* vidro da PORTA e da GUARDA da sacada (16/10/2026: "padronize todas com o reflexo natural do vidro"): o mesmo reflexo do céu
           nos dois — de frente (~8% de reflexo do céu, o interior aparece por trás, levemente fumê), de raspão vira espelho (até ~55%).
           Nenhuma porta fica "apagada" e outra "refletindo": é o mesmo vidro em todas, e só o ângulo de visada muda. */
        if (o.material.name === 'vidro_guarda' && !o.material.userData.fresnel) vidroFresnel(o.material, 0.30, 0.80, 0.05, 0.50, 0.75);
        if (o.material.name === 'vidro_porta' && !o.material.userData.fresnel) vidroFresnel(o.material, 0.16, 0.80, 0.06, 0.50, 0.75);
        /* vidro da CERCA do deque (imagens 14 e 15): lâmina clara que mostra as plantas atrás e reflete o céu de raspão */
        if (o.material.name === 'vidro_deque' && !o.material.userData.fresnel) vidroFresnel(o.material, 0.14, 0.60, 0.04, 0.28, 0.6);
        /* nichos da torre de pedra: sem vidro, sem reflexo nenhum */
        if (o.material.name === 'janela_escada') o.material.envMapIntensity = 0;
        /* deque e piscina em mármore preto MOLHADO (Renders 5 e 9): liso e refletindo o céu */
        /* reflexo contido (pedido do usuário em 15/10: "remova esses excessos de luz e reflexo") */
        if (o.material.name === 'marmore_preto') { o.material.envMap = ceuEnv; o.material.envMapIntensity = 0.3; o.material.roughness = 0.3; }
        /* vidros refletem o céu do entardecer (não a "sala" neutra) */
        if (/^vitrine_terreo/.test(o.material.name) && o.material.envMap !== ceuEnv) {
          o.material.envMap = ceuEnv; o.material.envMapIntensity *= 2.2;
        }
        /* o ambiente aceso atrás da porta não espelha nada (quem reflete é o vidro na frente);
           com reflexo, visto de baixo o céu azul cobria a luz quente (Render 3) */
        if (o.material.name === 'janela_unidade') o.material.envMapIntensity = 0;
        /* muro e embasamento de pedra (imagens 14-16): honed, sem brilho de verniz */
        if (o.material.name === 'muro_pedra') { o.material.envMapIntensity = 0; o.material.roughness = 1; }   /* alicerces: lisos e foscos (sem reflexo de céu em vista rasante) */
        if (o.material.name === 'vidro_terreo') o.material.envMapIntensity = 0.12;
        /* metais refletem o céu de verdade, não a "sala" do RoomEnvironment */
        /* brilhos de luz (gradientes de alfa em quads finos): sem repetição da textura nas bordas (a 1ª linha, clara, vazava
           para o fim do quad e virava pontilhado à distância) — 16/10/2026 */
        if (o.material.name === 'lavagem_luz' || o.material.name === 'poca_luz' || o.material.name === 'facho_luz') {
          ['map', 'emissiveMap'].forEach(function (kk) { var tt = o.material[kk]; if (tt) { tt.wrapS = tt.wrapT = THREE.ClampToEdgeWrapping; tt.needsUpdate = true; } });
          /* poças e lavagens de luz: mistura ADITIVA (16/10/2026, "chapadas"): na mistura por transparência a base preta escurecia o chão em volta
             e a luz virava um decalque cinza; aditiva só soma luz */
          if (o.material.name !== 'facho_luz') { o.material.blending = THREE.AdditiveBlending; o.material.depthWrite = false; o.material.needsUpdate = true; }
        }
        /* acabamentos do térreo e da fachada refletem o céu (pedido do gerador, 16/10/2026) */
        var KENV = { borda_acm: 0.9, moldura_metal: 0.6, torre_escada: 0.2, acm_preto: 0.14, painel_acm: 0.75, borda_sacada: 0.7, forro_marquise: 0.45 };
        if (KENV[o.material.name] !== undefined && o.material.envMap !== ceuEnv) { o.material.envMap = ceuEnv; o.material.envMapIntensity = KENV[o.material.name]; }
        if (o.material.name === 'vidro_claraboia' && !o.material.userData.fresnel) vidroFresnel(o.material, 0.88, 0.96, 0.03, 0.22, 0.5);
        if (o.material.name === 'vidro_corredor' && !o.material.userData.fresnel) vidroFresnel(o.material, 0.9, 0.97, 0.05, 0.35, 0.5);
        if (o.material.name === 'alu_escovado') { o.material.envMap = ceuEnv; o.material.envMapIntensity = 0.35; }
      });
    }

    /* luz do entardecer do Render 2: o sol acabou de se pôr atrás da torre — luz de céu azulada
       por cima, um resto laranja baixo vindo de trás (contorno quente, sombra longa e fraca
       para a frente) e quem acende a fachada são as sacadas e o térreo */
    /* luz de céu forte o bastante para a fachada aparecer no entardecer (pedido do usuário em
       15/10). Sem luz direcional de preenchimento: o brilho dela nos pisos polidos virava um
       clarão ("remova esses excessos de luz e reflexo") */
    /* 16/10/2026: um pouco menos de céu na fachada — nos Renders 2, 3 e 9 ela é escura e quem
       acende é a luz de dentro (forros, studios, lounge) */
    /* 16/10/2026 (2): céu neutro-quente mais forte, com oclusão nas peças recuadas (aoMap abaixo)
       — só a luz forte lava as sacadas de cinza; o tom varia com a direção do sol (tingeLuz) */
    hemi = new THREE.HemisphereLight(0xe7e7ed, 0xcfbfad, 4.0); scene.add(hemi);
    hemiS0 = hemi.color.clone(); hemiG0 = hemi.groundColor.clone();
    var sol = new THREE.DirectionalLight(0xff9a5a, 0.5);
    sol.position.set(CENTRO[0] + Math.cos(SOL_ALT) * Math.sin(SOL_AZ) * 300, Math.sin(SOL_ALT) * 300,
                     CENTRO[2] + Math.cos(SOL_ALT) * Math.cos(SOL_AZ) * 300);
    sol.target.position.set(CENTRO[0], 0, CENTRO[2]);
    scene.add(sol.target);
    if (!leve) {
      sol.castShadow = true;
      sol.shadow.mapSize.set(2048, 2048);
      /* visto do sol, a sombra no chão cai atrás da torre: basta a caixa cobrir a torre e o
         entorno; o fundo da caixa vai até onde a sombra comprida termina */
      sol.shadow.camera.left = -75; sol.shadow.camera.right = 75;
      sol.shadow.camera.top = 95; sol.shadow.camera.bottom = -45;
      sol.shadow.camera.near = 150; sol.shadow.camera.far = 950;
      sol.shadow.bias = -0.0004; sol.shadow.normalBias = 0.03;
    }
    scene.add(sol);


    if (!leve && mods.EffectComposer && DBG.indexOf('bloom0') < 0) {
      /* alvo com textura de profundidade de 24 bits: o padrão do composer é um renderbuffer de 16 bits, que a 190 m
         resolve só ~0,5 m — chão × anel de sombra × piso a poucos cm ficavam pontilhados na base (16/10/2026) */
      var rt0 = new THREE.WebGLRenderTarget(1, 1, { type: THREE.HalfFloatType, depthTexture: new THREE.DepthTexture(1, 1, THREE.UnsignedIntType) });
      composer = new mods.EffectComposer(R, rt0);
      composer.addPass(new mods.RenderPass(scene, cam));
      bloom = new mods.UnrealBloomPass(new THREE.Vector2(1, 1), 0.42, 0.55, 0.9);
      composer.addPass(bloom);
      composer.addPass(new mods.OutputPass());
    }

    model = glb.scene;
    scene.add(model);
    /* oclusão ambiente barata: um aoMap preto 1x1 com a intensidade (1 − k) por material — peças
       recuadas (aletas, forros, vidros, interiores) recebem menos luz de céu; o k é a "profundidade" */
    var AO = { concreto_cinza: 0.3, borda_sacada: 0.1, aleta: 0.3, alu_escovado: 0.2, laje_concreto: 0.5, madeira_sacada: 0.4, janela_unidade: 0.3, vidro_porta: 0.5,
               vidro_guarda: 0.6, ripado_madeira: 0.15, interior_parede: 0.15, interior_piso: 0.2, interior_teto: 0.15, lounge_parede: 0.25, concreto_escuro: 0.2,
               movel_claro: 0.25, movel_escuro: 0.3, cesto_rattan: 0.25, corredor_fundo: 0.25 };   /* valor = fração da luz de céu que a peça recebe (menor = mais escura): o céu forte não pode estourar os interiores (16/10/2026) */
    var aoTex = new THREE.DataTexture(new Uint8Array([0, 0, 0, 255]), 1, 1); aoTex.needsUpdate = true;
    model.traverse(function (o) {
      if (!o.isMesh || o.material.userData.ao || !(o.material.name in AO)) return;
      o.material.aoMap = aoTex; o.material.aoMapIntensity = 1 - AO[o.material.name];
      o.material.userData.ao = true; o.material.needsUpdate = true;
    });
    model.traverse(function (o) {
      if (!o.isMesh) return;
      o.castShadow = !o.material.transparent;
      o.receiveShadow = true;
      o.material.fog = false;
      /* forros e bordas das sacadas acesos em âmbar, como no hero (o .glb traz o brilho base) */
      if (!o.material.userData.hero && /^(madeira_sacada|borda_laje)$/.test(o.material.name)) {
        o.material.emissiveIntensity *= 0.45; o.material.userData.hero = true;   /* o brilho agora vem das poças dos spots (aplicaSpots) */
      }
      if ('envMapIntensity' in o.material) o.material.envMapIntensity = ENV;
      /* praça molhada: o reflexo do ambiente de raspão deixa o chão branco (mesmo caso do véu) */
      if (o.material.name === 'paralelepipedo' || o.material.name === 'placa_pedra') { o.material.envMapIntensity = 0.08; o.material.roughness = 0.85; }
      /* embasamento escuro como no Render 3 (a pedra cinza-clara lia como um muro claro) */
      if (o.material.name === 'placa_pedra') o.material.color.multiplyScalar(0.5);
      /* vidros (janelas e guarda): reflexo do céu com Fresnel — ver vidroFresnel em assaCeu */
      /* filtro anisotrópico: sem ele a madeira em ripas vira chuvisco de lado */
      ['map', 'normalMap', 'emissiveMap'].forEach(function (k) {
        if (o.material[k]) o.material[k].anisotropy = R.capabilities.getMaxAnisotropy();
      });
    });
    /* QA: põe a câmera num ponto exato (yaw, pitch, dist, centro) */
    if (DBG.indexOf('info') >= 0) window.__f3dcam = function (y, p, d, c) {
      girando = false; yaw = alvoYaw = y; pitch = alvoPitch = p; dist = alvoDist = d;
      if (c) { centro = c.slice(); alvoCentro = c.slice(); }
      fino = false; ultimoMov = performance.now(); pede();
    };
    /* QA: campo de visão fixo (graus, vertical), para casar com uma câmera externa */
    if (DBG.indexOf('info') >= 0) window.__f3dfov = function (g) { FOV_LONGE = FOV_PERTO = g; cam.fov = g; cam.updateProjectionMatrix(); pede(); };
    /* QA: qual peça está sob o pixel (x, y) do canvas — todas as camadas, inclusive vidros */
    if (DBG.indexOf('info') >= 0) window.__f3dpick = function (px, py) {
      var rc = new THREE.Raycaster(), v = new THREE.Vector2(px / canvas.clientWidth * 2 - 1, -(py / canvas.clientHeight) * 2 + 1);
      rc.setFromCamera(v, cam);
      return rc.intersectObjects(scene.children, true).slice(0, 8).map(function (h) {
        return [h.object.material && h.object.material.name, h.object.name || h.object.type, +h.distance.toFixed(2), h.point.toArray().map(function (n) { return +n.toFixed(2); }), h.face ? h.face.normal.toArray().map(function (n) { return +n.toFixed(2); }) : null];
      });
    };
    if (DBG.indexOf('info') >= 0) { window.__f3dscene = scene; window.__f3dpede = function () { fino = false; ultimoMov = performance.now(); pede(); }; }   /* QA: esconder materiais para achar defeitos */
    if (DBG.indexOf('info') >= 0) window.__f3dvis = function (pav, stu) {
      var u = unidades['P' + pad(pav) + '-S' + pad(stu)]; if (!u) return null;
      var a = [u.centro.x, u.centro.y, u.centro.z], out = [];
      [0, 0.3, -0.3, Math.PI / 2, Math.PI, -Math.PI / 2, 1.27, 1.57, 1.87].forEach(function (y) { out.push([y.toFixed(2), enxerga(a, y, 0.1, DIST_SEL)]); });
      return { centro: a.map(function (v) { return +v.toFixed(2); }), fachada: u.fachada, testes: out, n: malhasUnidade.length + malhasPav.length + malhasFixas.length,
               cam: { yaw: +yaw.toFixed(3), alvoYaw: +alvoYaw.toFixed(3), pitch: +pitch.toFixed(3), dist: +dist.toFixed(1), centro: centro.map(function (v) { return +v.toFixed(2); }), desloc: desloc.map(function (v) { return +v.toFixed(3); }),
                      escolhida: escolhida ? escolhida.pav + '-' + escolhida.stu : null, luz: escolhida ? [escolhida.luz.janela, escolhida.luz.teto] : null } };
    };
    /* QA: custo por quadro (ms) do desenho normal e do passe de reflexo, e chamadas de desenho */
    if (DBG.indexOf('info') >= 0) window.__f3dtempo = function (n) {
      var gl = R.getContext(); composer ? composer.render() : R.render(scene, cam); gl.finish();
      var t0 = performance.now(); for (var i = 0; i < n; i++) { composer ? composer.render() : R.render(scene, cam); } gl.finish();
      var tr = (performance.now() - t0) / n, rr = -1, calls = R.info.render.calls;
      if (REFL) { reflexoDesenha(); gl.finish(); var t1 = performance.now(); for (var j = 0; j < n; j++) reflexoDesenha(); gl.finish(); rr = (performance.now() - t1) / n; }
      return { quadro_ms: +tr.toFixed(2), reflexo_ms: +rr.toFixed(2), chamadas: calls };
    };
    if (DBG.indexOf('info') >= 0) window.__f3dinfo = function () {
      return { programas: R.info.programs.length, chamadas: R.info.render.calls, triangulos: R.info.render.triangles,
               paralelo: !!R.extensions.get('KHR_parallel_shader_compile'),
               nomes: R.info.programs.map(function (p) { return p.name; }),
               tempos: tempos,
               mats: (function () { var n = {}; scene.traverse(function (o) { if (o.material) n[o.material.name] = (n[o.material.name] || 0) + 1; }); return n; })() };
    };
    /* etapas em quadros separados: céu, chão, unidades, faixas, resto, seletores, água */
    emEtapas([assaCeu, function () { montaChao(THREE, ceuEnv); }, otimizaUnidades, otimizaFaixas, otimizaResto, preparaUnidades, function () {
      /* as UVs do .glb vêm em inteiros de 16 bits e cada textura desfaz a escala
         (KHR_texture_transform): as texturas da água copiam essa escala de qualquer mapa da cena */
      var escUV = 1;
      scene.traverse(function (o) { if (escUV === 1 && o.material && o.material.map && o.material.map.repeat.x < 1) escUV = o.material.map.repeat.x; });
      var tx = texturasDaAgua(THREE), agua = aguaDaPiscina(THREE, ceuEnv, tx);
      tx.nrm.repeat.multiplyScalar(escUV); tx.caus.repeat.multiplyScalar(escUV);
      malhasFixas.forEach(function (m) {
        if (m.material.name !== 'agua') return;
        m.material = agua; m.castShadow = false;
        if (REFL) { reflexoLiga(agua, 1.0, 0.7); REFL.chao.push(m); }
        model.add(causticasDaPiscina(THREE, m, tx));
      });
    }]).then(function () {
      /* a cena é parada: a sombra é calculada uma vez, não a cada quadro */
      if (R.shadowMap.enabled) { R.shadowMap.autoUpdate = false; R.shadowMap.needsUpdate = true; }
      return aquece();
    }).then(function () {
      stage.classList.add('is-webgl');
      redimensiona();
      pede();
    });
  }

  /* sobe as texturas para a placa uma por quadro e compila os shaders em paralelo
     antes do primeiro desenho — era isso que travava a página por ~1 s ao chegar */
  function aquece() {
    var texs = [];
    scene.traverse(function (o) {
      if (!o.material) return;
      [].concat(o.material).forEach(function (m) {
        ['map', 'normalMap', 'emissiveMap', 'roughnessMap', 'metalnessMap', 'alphaMap'].forEach(function (k) {
          if (m[k] && texs.indexOf(m[k]) < 0) texs.push(m[k]);
        });
      });
    });
    var p = Promise.resolve();
    texs.forEach(function (t) { p = p.then(function () { R.initTexture(t); return quadroLivre(); }); });
    return p.then(function () {
      if (!R.compileAsync) return null;
      /* compila as variantes de "render target" (composer e reflexo) quando há composer */
      if (composer) R.setRenderTarget(composer.readBuffer);
      var pr = R.compileAsync(scene, cam);
      R.setRenderTarget(null);
      return pr;
    }).then(function () {
      if (!composer) return null;
      /* um quadro escondido com o brilho ligado compila os passes do bloom e a sombra antes de mostrar */
      redimensiona(); densidade(PARADO);
      posicionaCamera();
      if (bloom) bloom.enabled = true;
      composer.render();
      return quadroLivre();
    }).catch(function () { /* sem compilação paralela: compila no 1º quadro */ });
  }

  /* ------------------------------------------------------------
     DESEMPENHO — o .glb traz 510 studios (30 modelos repetidos em 17 andares)
     e 17 faixas de pavimento: ~2.700 objetos = ~2.700 chamadas de desenho por
     quadro (medido em 15/10/2026: 20 fps no desktop, 6 fps no celular). Aqui:
     - studios: UMA InstancedMesh por material (17 instâncias = os andares), com
       os 30 studios fundidos e um atributo 'stu'; a luz de cada studio vem de
       uma textura 32 x 17 (R = janela, G = teto) — acender é escrever um texel;
     - faixas dos pavimentos: uma malha por material (o andar sai da altura do toque);
     - o resto (térreo, cobertura, núcleo): uma malha por material.
     ------------------------------------------------------------ */
  var RX = /^P(\d\d)-S(\d\d)$/;
  var luzTex = null, luzDados = null, luzSuja = false, malhasUnidade = [], pavDaInstancia = [];
  var malhasPav = [], malhasFixas = [], TERREO_M = 5.6, PE_M = 3.0, N_PAV = 17;

  function injetaLuz(mat, canal) {
    mat.emissiveIntensity = 1;
    mat.onBeforeCompile = function (sh) {
      sh.uniforms.uLuz = { value: luzTex };
      sh.vertexShader = sh.vertexShader
        .replace('#include <common>', '#include <common>\nattribute float stu;\nuniform sampler2D uLuz;\nvarying float vLuz;')
        .replace('#include <begin_vertex>', '#include <begin_vertex>\nvLuz = texelFetch(uLuz, ivec2(int(stu + 0.5), gl_InstanceID), 0).' + canal + ' * 8.0;');
      sh.fragmentShader = sh.fragmentShader
        .replace('#include <common>', '#include <common>\nvarying float vLuz;')
        .replace('#include <emissivemap_fragment>', '#include <emissivemap_fragment>\ntotalEmissiveRadiance *= vLuz;');
    };
    mat.customProgramCacheKey = function () { return 'luz-' + canal; };
  }

  /* normais em 8 bits chegam entrelaçadas (byteStride 4): a fusão não aceita — desentrelaça */
  function plano(g) {
    Object.keys(g.attributes).forEach(function (k) {
      var a = g.attributes[k];
      if (!a.isInterleavedBufferAttribute) return;
      var n = a.count, s = a.itemSize, arr = new Float32Array(n * s);
      for (var i = 0; i < n; i++) {
        arr[i * s] = a.getX(i);
        if (s > 1) arr[i * s + 1] = a.getY(i);
        if (s > 2) arr[i * s + 2] = a.getZ(i);
        if (s > 3) arr[i * s + 3] = a.getW(i);
      }
      g.setAttribute(k, new THREE.BufferAttribute(arr, s));
    });
    return g;
  }

  function funde(geos) {
    var g = mods3.mergeGeometries(geos, false);
    geos.forEach(function (x) { x.dispose(); });
    return g;
  }

  var raizModelo = null;
  function otimizaUnidades() {
    model.updateMatrixWorld(true);
    var raiz = raizModelo = model.getObjectByName('CINNAMON_FACHADA_PROVISORIO');
    if (raiz && raiz.userData) {
      if (raiz.userData.terreo_m) TERREO_M = raiz.userData.terreo_m;
      if (raiz.userData.peDireito_m) PE_M = raiz.userData.peDireito_m;
      if (raiz.userData.pavimentosTipo) N_PAV = raiz.userData.pavimentosTipo;
    }
    /* 1. studios */
    var nos = [];
    model.traverse(function (n) { if (RX.test(n.name)) nos.push(n); });
    var porStu = {}, yDoPav = {};
    nos.forEach(function (n) {
      var m = RX.exec(n.name), pav = +m[1], stu = +m[2];
      var u = { nome: n.name, pav: pav, stu: stu, fachada: (n.userData && n.userData.fachada) || '',
                centro: new THREE.Box3().setFromObject(n).getCenter(new THREE.Vector3()),
                luz: null };
      /* todos os studios com a mesma luz de dentro (16/10/2026: "padronize todas"): nada de porta acesa e porta apagada */
      u.base = { janela: LUZ_BASE.janela, teto: LUZ_BASE.teto };
      u.luz = { janela: u.base.janela, teto: u.base.teto };
      unidades[n.name] = u;
      (unidadesPorAndar[pav] = unidadesPorAndar[pav] || []).push(u);
      yDoPav[pav] = n.matrixWorld.elements[13];
      if (!porStu[stu]) porStu[stu] = n;
    });
    var pavs = Object.keys(yDoPav).map(Number).sort(function (a, b) { return a - b; });
    pavDaInstancia = pavs;
    var NS = 32;
    luzDados = new Uint8Array(NS * pavs.length * 4);
    luzTex = new THREE.DataTexture(luzDados, NS, pavs.length, THREE.RGBAFormat);
    luzTex.magFilter = luzTex.minFilter = THREE.NearestFilter;
    luzTex.needsUpdate = true;
    var porMat = {};
    Object.keys(porStu).forEach(function (k) {
      var n = porStu[k], inv = new THREE.Matrix4().copy(n.matrixWorld).invert();
      n.traverse(function (o) {
        if (!o.isMesh) return;
        var g = plano(o.geometry.clone());
        g.applyMatrix4(new THREE.Matrix4().multiplyMatrices(inv, o.matrixWorld));
        var c = new Float32Array(g.attributes.position.count).fill(+k);
        g.setAttribute('stu', new THREE.BufferAttribute(c, 1));
        var nome = o.material.name;
        (porMat[nome] = porMat[nome] || { mat: o.material, geos: [] }).geos.push(g);
      });
    });
    nos.forEach(function (n) { if (n.parent) n.parent.remove(n); });
    var mInst = new THREE.Matrix4();
    Object.keys(porMat).forEach(function (nome) {
      var e = porMat[nome], mat = e.mat;
      /* 'luz_quente' também é usado nos interiores do térreo: sem clone, a luz dos studios
         zerava a emissão das luminárias fixas (teto do lounge azul-marinho) */
      if (nome === 'janela_unidade' || nome === 'luz_quente') mat = e.mat.clone();
      if (nome === 'luz_quente') {
        /* centro do spot de cada studio (média da geometria fundida) — alimenta as poças de luz */
        var gq = funde(e.geos.map(function (g) { return g.clone(); })), pq = gq.attributes.position, sq = gq.attributes.stu, acc = {};
        for (var iq = 0; iq < pq.count; iq++) {
          var kq = Math.round(sq.getX(iq)), a0 = acc[kq] = acc[kq] || [0, 0, 0, 0];
          a0[0] += pq.getX(iq); a0[1] += pq.getY(iq); a0[2] += pq.getZ(iq); a0[3]++;
        }
        SPOTS = { xz: [], y: 0, pe: yDoPav[pavs[1]] - yDoPav[pavs[0]], y0: yDoPav[pavs[0]], n: pavs.length };
        Object.keys(acc).forEach(function (k2) { var a1 = acc[k2]; SPOTS.xz.push(new THREE.Vector3(a1[0] / a1[3], a1[2] / a1[3], +k2)); SPOTS.y = a1[1] / a1[3]; });
        SPOTS.y0 += SPOTS.y; gq.dispose();
      }
      if (nome === 'janela_unidade') injetaLuz(mat, 'r');
      else if (nome === 'luz_quente') injetaLuz(mat, 'g');
      var im = new THREE.InstancedMesh(funde(e.geos), mat, pavs.length);
      pavs.forEach(function (p, i) { mInst.makeTranslation(0, yDoPav[p], 0); im.setMatrixAt(i, mInst); });
      im.instanceMatrix.needsUpdate = true;
      im.computeBoundingSphere();
      im.userData.unidades = true;
      im.castShadow = !mat.transparent; im.receiveShadow = true;
      malhasUnidade.push(im);
      model.add(im);
    });
    Object.keys(unidades).forEach(function (k) { escreveLuz(unidades[k]); });
  }

  /* 2. faixas dos pavimentos e 3. o resto: uma malha por material */
  function juntaPorMaterial(objs, ePav) {
      var grupos = {};
      objs.forEach(function (raizObj) {
        raizObj.traverse(function (o) {
          if (!o.isMesh || o.isInstancedMesh) return;
          var g = plano(o.geometry.clone()); g.applyMatrix4(o.matrixWorld);
          var nome = o.material.name;
          (grupos[nome] = grupos[nome] || { mat: o.material, geos: [] }).geos.push(g);
        });
      });
      var saida = [];
      Object.keys(grupos).forEach(function (nome) {
        var e = grupos[nome];
        var mesh = new THREE.Mesh(funde(e.geos), e.mat);
        mesh.userData.pav = ePav;
        mesh.castShadow = !e.mat.transparent; mesh.receiveShadow = true;
        if (e.mat.transparent) e.mat.depthWrite = false;   /* vidros fundidos: um não apaga o outro */
        saida.push(mesh);
      });
      return saida;
  }

  function otimizaFaixas() {
    var pavNos = [];
    model.traverse(function (n) { if (/^PAV-\d\d$/.test(n.name)) pavNos.push(n); });
    malhasPav = juntaPorMaterial(pavNos, true);
    pavNos.forEach(function (n) { if (n.parent) n.parent.remove(n); });
    malhasPav.forEach(function (m) { model.add(m); });
  }

  /* soma um trecho de shader ao onBeforeCompile que o material já tem (injetaLuz, reflexo...) */
  function encadeia(mat, chave, fn) {
    var antes = mat.onBeforeCompile, k0 = mat.customProgramCacheKey;
    mat.onBeforeCompile = function (sh, r) { if (antes) antes.call(mat, sh, r); fn(sh); };
    mat.customProgramCacheKey = function () { return (k0 ? k0.call(mat) : mat.name) + '-' + chave; };
  }

  /* POÇAS DE LUZ dos spots (Renders 2, 3 e 10): cada spot de cada studio joga uma poça quente no
     forro, nas aletas e nas lajes em volta — feito no shader (sem decalques): 30 spots por andar,
     o andar sai da altura do fragmento. A poça do studio escolhido acende junto (uLuz2).
     A borda de 10 cm da madeira vira linha quente e a madeira de raspão acende (verniz). */
  function aplicaSpots() {
    if (!SPOTS) return;
    var uS = { value: SPOTS.xz }, uY = { value: new THREE.Vector3(SPOTS.y0, SPOTS.pe, SPOTS.n) };
    var cor = new THREE.Color(0xffdcb0), feitos = {};
    var I = { aleta: 2, concreto_cinza: 1.6, alu_escovado: 1.4, laje_concreto: 1, madeira_sacada: 0.4 }, HALO = { madeira_sacada: 0.5 };   /* 16/10: poças menores, spots como pontinhos (Renders 4, 9, 10) */
    function liga(mat) {
      if (feitos[mat.uuid]) return; feitos[mat.uuid] = true;
      var ki = I[mat.name] || 0, halo = HALO[mat.name] || 0, madeira = mat.name === 'madeira_sacada';
      encadeia(mat, 'spot', function (sh) {
        sh.uniforms.uSp = uS; sh.uniforms.uSpY = uY; sh.uniforms.uLuz2 = { value: luzTex }; sh.uniforms.uSpCor = { value: cor };
        if (sh.vertexShader.indexOf('vMundoS') < 0) {
          sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vMundoS;\nvarying vec3 vNormS;')
            .replace('#include <project_vertex>', '#include <project_vertex>\nvec4 wpS = vec4(transformed, 1.0);\n#ifdef USE_INSTANCING\nwpS = instanceMatrix * wpS;\n#endif\nvMundoS = (modelMatrix * wpS).xyz; vNormS = normalize(mat3(modelMatrix) * objectNormal);');
        }
        sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nvarying vec3 vMundoS;\nvarying vec3 vNormS;\nuniform vec3 uSp[' + SPOTS.xz.length + '];\nuniform vec3 uSpY;\nuniform sampler2D uLuz2;\nuniform vec3 uSpCor;')
          .replace('#include <emissivemap_fragment>', '#include <emissivemap_fragment>\n' +
            '{ float kf = ceil((vMundoS.y - uSpY.x - 0.1) / uSpY.y); vec3 nS = normalize(vNormS);\n' +
            '  if (kf >= 0.0 && kf < uSpY.z) { float ys = uSpY.x + kf * uSpY.y; float acc = 0.0, hal = 0.0;\n' +
            '    for (int i = 0; i < ' + SPOTS.xz.length + '; i++) { vec2 dxz = uSp[i].xy - vMundoS.xz; float d2 = dot(dxz, dxz); if (d2 > 30.0) continue;\n' +
            '      float T = texelFetch(uLuz2, ivec2(int(uSp[i].z + 0.5), int(kf)), 0).g * 8.0;\n' +
            '      vec3 L = vec3(dxz.x, ys - vMundoS.y, dxz.y); float dl = length(L); vec3 Ln = L / max(dl, 1e-3);\n' +
            '      float cone = smoothstep(0.0, 0.6, Ln.y);\n' +
            '      acc += T * (max(dot(nS, Ln), 0.0) * cone / (dl * dl + 0.3) + 0.12 * exp(-d2 / 3.0) * step(-0.5, nS.y));\n' +
            '      hal += T * (exp(-d2 / 1.0) + 5.0 * exp(-d2 / 0.1));\n' +
            '    }\n' +
            (madeira ? '    totalEmissiveRadiance *= mix(1.0, 3.5, step(abs(nS.y), 0.5));\n' +
              '    totalEmissiveRadiance *= mix(0.65, 2.3, pow(1.0 - abs(dot(nS, normalize(vViewPosition))), 2.0));\n' : '') +
            '    totalEmissiveRadiance += diffuseColor.rgb * uSpCor * acc * ' + ki.toFixed(3) + ';\n' +
            (halo ? '    totalEmissiveRadiance += uSpCor * hal * ' + halo.toFixed(3) + ' * step(nS.y, -0.5) * diffuseColor.rgb;\n' : '') +
            '  } }');
      });
      mat.needsUpdate = true;
    }
    model.traverse(function (o) { if (o.isMesh && (o.material.name in I)) liga(o.material); });
  }

  function otimizaResto() {
    var outros = [];
    if (raizModelo) raizModelo.children.forEach(function (n) { if (!/^PAV-\d\d$/.test(n.name)) outros.push(n); });
    malhasFixas = juntaPorMaterial(outros, false);
    outros.forEach(function (n) { if (n.parent) n.parent.remove(n); });
    malhasFixas.forEach(function (m) { model.add(m); });
    aplicaSpots();
    if (REFL) malhasFixas.forEach(function (m) {
      var nm = m.material.name;
      if (nm === 'paralelepipedo') { reflexoLiga(m.material, 0.45, 1.0); REFL.chao.push(m); }
      else if (nm === 'marmore_preto') { reflexoLiga(m.material, 1.0, 0.8); REFL.chao.push(m); }
    });
  }

  /* roda cada etapa num quadro próprio: nenhuma tarefa longa segura a página */
  function quadroLivre() { return new Promise(function (ok) { requestAnimationFrame(function () { ok(); }); }); }
  var tempos = [];                   /* QA: duração de cada etapa (ms), lida por __f3dinfo */
  function emEtapas(fns) {
    return fns.reduce(function (p, fn, i) {
      return p.then(quadroLivre).then(function () { var t = performance.now(); var r = fn(); tempos.push([i, Math.round(performance.now() - t)]); return r; });
    }, Promise.resolve());
  }

  function escreveLuz(u) {
    var i = (pavDaInstancia.indexOf(u.pav) * 32 + u.stu) * 4;
    luzDados[i] = Math.round(clamp(u.luz.janela / 8, 0, 1) * 255);
    luzDados[i + 1] = Math.round(clamp(u.luz.teto / 8, 0, 1) * 255);
    luzSuja = true;
  }

  function preparaUnidades() {
    if (selPav && selStu) {
      var pavs = Object.keys(unidadesPorAndar).map(Number).sort(function (a, b) { return a - b; });
      pavs.forEach(function (p) { selPav.appendChild(new Option('Pavimento ' + pad(p), p)); });
      var stus = (unidadesPorAndar[pavs[0]] || []).map(function (u) { return u.stu; }).sort(function (a, b) { return a - b; });
      stus.forEach(function (s) { selStu.appendChild(new Option('Studio ' + pad(s), s)); });
      selPav.value = pavs[Math.floor(pavs.length / 2)];
      selStu.value = stus[0];
      function escolheSel() {
        var u = unidades['P' + pad(+selPav.value) + '-S' + pad(+selStu.value)];
        if (u) escolhe(u, true);
      }
      selPav.addEventListener('change', escolheSel);
      selStu.addEventListener('change', escolheSel);
    }
    stage.classList.add('is-ready');
  }

  /* ------------------------------------------------------------
     ESCOLHA — a unidade acende (janela + teto da sacada), o andar
     inteiro ganha um brilho leve, a câmera planeia até ela e o painel
     mostra os dados oficiais.
     ------------------------------------------------------------ */
  function acende(u, nivel) {
    var tab = nivel === 'cheia' ? LUZ : nivel === 'andar' ? LUZ_ANDAR : u.base;
    ['janela', 'teto'].forEach(function (k) {
      if (mqReduce.matches) { u.luz[k] = tab[k]; escreveLuz(u); return; }
      /* uma transição por studio e canal: a nova substitui a pendente (trocar pavimento e
         studio em seguida deixava duas, e a mais antiga apagava a janela escolhida no fim) */
      transicoes = transicoes.filter(function (tr) { return tr.u !== u || tr.k !== k; });
      transicoes.push({ u: u, k: k, de: u.luz[k], para: tab[k], t0: 0 });
    });
  }

  /* da órbita (yaw, pitch, d) em volta de 'alvo', a linha até o alvo está livre? Vale o que é
     opaco; o que bate a menos de 4 m do alvo é a própria sacada/janela do studio */
  var visada = null, oVis = null, dVis = null;
  function enxerga(alvo, y, p, d) {
    if (!THREE || !model) return true;
    visada = visada || new THREE.Raycaster(); oVis = oVis || new THREE.Vector3(); dVis = dVis || new THREE.Vector3();
    oVis.set(alvo[0] + d * Math.cos(p) * Math.sin(y), alvo[1] + d * Math.sin(p), alvo[2] + d * Math.cos(p) * Math.cos(y));
    dVis.set(alvo[0], alvo[1], alvo[2]).sub(oVis).normalize();
    visada.set(oVis, dVis); visada.near = 0; visada.far = d - 4;
    var hits = visada.intersectObjects(malhasUnidade.concat(malhasPav, malhasFixas), false);
    for (var i = 0; i < hits.length; i++) { if (!hits[i].object.material.transparent) return false; }
    return true;
  }

  function escolhe(u, viaTeclado) {
    if (escolhida === u) { pede(); return; }
    var anterior = escolhida;
    escolhida = u;
    if (anterior) {
      (unidadesPorAndar[anterior.pav] || []).forEach(function (x) { if (x.pav !== u.pav) acende(x, 'apagada'); });
    }
    (unidadesPorAndar[u.pav] || []).forEach(function (x) { acende(x, x === u ? 'cheia' : 'andar'); });

    /* a câmera mira o próprio studio, a DIST_SEL, quase de frente para a face dele (75% do
       giro: a lâmina continua na vista). Antes de girar, confere se alguma coisa fica entre a
       câmera e o studio (studios de canto, no alto, sumiam atrás da outra ala ou da parede de
       topo); se ficar, tenta de frente, depois um pouco para cada lado e mais de cima */
    var p = u.centro.clone(), alvo = [p.x, p.y, p.z];
    alvoDist = DIST_SEL;
    var yawFace = { norte: Math.PI, sul_barra: 0, leste_haste: Math.PI / 2, oeste: -Math.PI / 2 }[u.fachada];
    if (yawFace !== undefined) {
      var d = ((yawFace - alvoYaw + Math.PI) % (2 * Math.PI) + 2 * Math.PI) % (2 * Math.PI) - Math.PI;
      var y0 = alvoYaw + d * 0.75, yf = alvoYaw + d;
      var p0 = clamp(alvoPitch, -0.1, 0.3);
      /* três pontos da sacada (as duas pontas e o meio), não só o centro: com um só ponto a
         câmera achava uma fresta e o studio continuava escondido atrás da parede de topo */
      var tx = Math.cos(yawFace) * 1.4, tz = -Math.sin(yawFace) * 1.4, ny = 0.6;
      var pontos = [[alvo[0], alvo[1] + ny, alvo[2]], [alvo[0] + tx, alvo[1] + ny, alvo[2] + tz], [alvo[0] - tx, alvo[1] + ny, alvo[2] - tz]];
      var tentativas = [[y0, p0], [yf, p0]];
      [0.2, 0.4, 0.6, 0.8].forEach(function (g) { tentativas.push([yf + g, p0], [yf - g, p0]); });
      [0.35, 0.6].forEach(function (pp) { tentativas.push([yf, pp], [yf + 0.4, pp], [yf - 0.4, pp]); });
      var escolha = tentativas[0], melhor = -1;
      for (var i = 0; i < tentativas.length; i++) {
        var vistos = 0;
        for (var j = 0; j < 3; j++) if (enxerga(pontos[j], tentativas[i][0], tentativas[i][1], alvoDist)) vistos++;
        if (vistos > melhor) { melhor = vistos; escolha = tentativas[i]; }
        if (vistos === 3) break;
      }
      alvoYaw = escolha[0]; alvoPitch = escolha[1];
    }
    /* a janela escolhida fica à vista AO LADO do card: a lente escorrega (à esquerda do card
       no computador; acima da folha no celular) */
    if (!mqFolha.matches) {
      var larg = Math.max(1, canvas.clientWidth);
      /* o painel ainda pode estar escondido no 1º toque: usa a largura do css (min(340px, …)) */
      var pw = (panel && !panel.hidden ? panel.getBoundingClientRect().width : Math.min(340, larg * 0.4)) + 64;
      alvoDesloc = [Math.min(0.3, (pw / larg) / 2), 0];                  /* centro da área livre */
    } else {
      alvoDesloc = [0, 0.2];
    }
    alvoCentro = alvo;
    if (mqReduce.matches) { centro = alvoCentro.slice(); dist = alvoDist; yaw = alvoYaw; pitch = alvoPitch; desloc = alvoDesloc.slice(); }
    girando = false;
    tocou();
    preenche(u);
    if (selPav && selStu && !viaTeclado) { selPav.value = u.pav; selStu.value = u.stu; }
    pede();
  }

  function preenche(u) {
    if (!panel) return;
    var num = panel.querySelector('[data-f-num]');
    var pav = panel.querySelector('[data-f-pav]');
    var pos = panel.querySelector('[data-f-pos]');
    if (num) num.textContent = 'Studio ' + pad(u.stu);
    if (pav) pav.textContent = 'Pavimento ' + pad(u.pav);
    if (pos) pos.textContent = FACHADAS[u.fachada] || '';
    var dl = panel.querySelector('[data-f-dados]');
    if (dl && !dl.childElementCount) {
      METRAGENS.forEach(function (par) {
        var div = document.createElement('div');
        var dt = document.createElement('dt'); dt.textContent = par[0];
        var dd = document.createElement('dd'); dd.textContent = par[1];
        div.appendChild(dt); div.appendChild(dd); dl.appendChild(div);
      });
    }
    panel.hidden = false;
    stage.classList.add('has-panel');
  }

  var closePanel = q('[data-fachada-panel-close]');
  if (closePanel) closePanel.addEventListener('click', function () {
    if (escolhida) (unidadesPorAndar[escolhida.pav] || []).forEach(function (x) { acende(x, 'apagada'); });
    escolhida = null;
    panel.hidden = true;
    stage.classList.remove('has-panel');
    alvoCentro = CENTRO.slice();
    alvoDesloc = [0, 0];
    pede();
  });

  /* ------------------------------------------------------------
     QUADRO — só desenha quando algo muda; parado, espera o repouso e
     desenha uma vez no nível fino (densidade cheia + bloom).
     ------------------------------------------------------------ */
  var pedido = false, ultimoMov = 0, fino = false, dprAtual = 0;

  function pede() { if (!pedido && vivo && visivel) { pedido = true; requestAnimationFrame(quadro); } }

  function densidade(d) {
    if (d === dprAtual) return;
    dprAtual = d;
    R.setPixelRatio(d);
    R.setSize(canvas.clientWidth, canvas.clientHeight, false);
    if (composer) composer.setSize(canvas.clientWidth, canvas.clientHeight);
  }

  function redimensiona() {
    if (!R) return;
    cam.aspect = canvas.clientWidth / Math.max(1, canvas.clientHeight);
    cam.updateProjectionMatrix();
    dprAtual = 0;
    pede();
  }

  function avanca(agora, dt) {
    var mexeu = false;
    if (girando) { alvoYaw += GIRO_AUTO * dt; mexeu = true; }
    if (solto && Math.abs(vYaw) > 1e-5) {
      alvoYaw += vYaw * dt;
      vYaw *= Math.pow(FRICTION, dt / 16.7);
      mexeu = true;
    } else { vYaw = 0; }
    var fa = faixaAltura(alvoDist);
    alvoCentro[1] = clamp(alvoCentro[1], fa[0], fa[1]);
    if (alvoPitch < pitchMin()) alvoPitch = pitchMin();
    if (alvoPitch > pitchMax()) alvoPitch = pitchMax();
    var k = mqReduce.matches ? 1 : 1 - Math.pow(1 - SUAVE, dt / 16.7);
    var dy = alvoYaw - yaw, dp = alvoPitch - pitch, dd = alvoDist - dist;
    yaw += dy * k; pitch += dp * k; dist += dd * k;
    for (var i = 0; i < 3; i++) { var dc = alvoCentro[i] - centro[i]; centro[i] += dc * k; if (Math.abs(dc) > 0.01) mexeu = true; }
    for (var i2 = 0; i2 < 2; i2++) { var dl = alvoDesloc[i2] - desloc[i2]; desloc[i2] += dl * k; if (Math.abs(dl) > 1e-4) mexeu = true; }
    if (Math.abs(dy) > 1e-4 || Math.abs(dp) > 1e-4 || Math.abs(dd) > 0.01) mexeu = true;

    for (var j = transicoes.length - 1; j >= 0; j--) {
      var tr = transicoes[j];
      if (!tr.t0) tr.t0 = agora;
      var f = clamp((agora - tr.t0) / 420, 0, 1);
      f = 1 - Math.pow(1 - f, 3);
      tr.u.luz[tr.k] = tr.de + (tr.para - tr.de) * f;
      escreveLuz(tr.u);
      if (f >= 1) transicoes.splice(j, 1);
      mexeu = true;
    }
    if (luzSuja && luzTex) { luzTex.needsUpdate = true; luzSuja = false; }
    return mexeu;
  }

  var ultimoQuadro = 0;

  /* câmera na órbita + lente de arquitetura (deslocamento vertical da lente em vez de
     inclinar — verticais retas) + campo de visão que abre de perto */
  /* a luz de céu muda de tom com a direção da câmera em relação ao sol: quente-neutra de frente
     (Render 2), fria e mais escura de lado (Render 3), fria de costas (Render 10). Só uniforms:
     vale no celular também */
  var TINTA = [[0, [1, 1, 1]], [1.85, [0.55, 0.64, 0.92]], [2.6, [0.83, 1.03, 1.4]], [3.2, [0.83, 1.03, 1.4]]];
  function tingeLuz() {
    if (!hemi) return;
    var fx = centro[0] - cam.position.x, fz = centro[2] - cam.position.z, l = Math.sqrt(fx * fx + fz * fz) || 1;
    var a = Math.acos(clamp((fx * Math.sin(SOL_AZ) + fz * Math.cos(SOL_AZ)) / l, -1, 1));
    var i = 0; while (i < TINTA.length - 2 && a > TINTA[i + 1][0]) i++;
    var t = clamp((a - TINTA[i][0]) / (TINTA[i + 1][0] - TINTA[i][0]), 0, 1); t = t * t * (3 - 2 * t);
    var k = [0, 1, 2].map(function (c) { return TINTA[i][1][c] + (TINTA[i + 1][1][c] - TINTA[i][1][c]) * t; });
    hemi.color.copy(hemiS0); hemi.color.r *= k[0]; hemi.color.g *= k[1]; hemi.color.b *= k[2];
    hemi.groundColor.copy(hemiG0); hemi.groundColor.r *= k[0]; hemi.groundColor.g *= k[1]; hemi.groundColor.b *= k[2];
  }
  function posicionaCamera() {
    var perto = clamp((150 - dist) / 100, 0, 1);
    var fov = FOV_LONGE + (FOV_PERTO - FOV_LONGE) * perto * perto * (3 - 2 * perto);
    if (Math.abs(cam.fov - fov) > 1e-3) cam.fov = fov;
    cam.position.set(
      centro[0] + dist * Math.cos(pitch) * Math.sin(yaw),
      centro[1] + dist * Math.sin(pitch),
      centro[2] + dist * Math.cos(pitch) * Math.cos(yaw));
    var hx = centro[0] - cam.position.x, hz = centro[2] - cam.position.z, hd = Math.max(1e-3, Math.sqrt(hx * hx + hz * hz));
    var a = Math.atan2(centro[1] - cam.position.y, hd);
    var lente = clamp(a, -LENTE_MAX, LENTE_MAX), incl = a - lente;
    cam.lookAt(cam.position.x + hx, cam.position.y + Math.tan(incl) * hd, cam.position.z + hz);
    var w = Math.max(1, canvas.clientWidth), h = Math.max(1, canvas.clientHeight);
    var sh = Math.tan(lente) / Math.tan(cam.fov * Math.PI / 360);
    if (DBG.indexOf('lente0') >= 0) { cam.lookAt(centro[0], centro[1], centro[2]); cam.clearViewOffset(); return; }
    cam.setViewOffset(w, h, desloc[0] * w, -sh * h / 2 + desloc[1] * h, w, h);    /* já atualiza a projeção */
  }

  function quadro(agora) {
    pedido = false;
    var dt = ultimoQuadro ? Math.min(50, agora - ultimoQuadro) : 16.7;
    ultimoQuadro = agora;
    var mexeu = avanca(agora, dt);
    if (mexeu) { ultimoMov = agora; fino = false; }

    var parado = !mexeu && agora - ultimoMov >= REPOUSO;
    if (parado && fino) { ultimoQuadro = 0; return; }
    densidade(parado ? PARADO : MOVENDO);

    posicionaCamera();
    tingeLuz();
    avisaVista();

    /* no desktop tudo passa pelo composer (o brilho só liga parado): um único conjunto de
       shaders, o mesmo que o aquece() compilou — senão cada material tinha duas variantes
       e a segunda compilava travando a página no 1º quadro */
    if (REFL) { if (parado) reflexoDesenha(); else REFL.u.uReflOn.value = 0; }
    if (composer) { if (bloom) bloom.enabled = parado; composer.render(); } else R.render(scene, cam);
    if (!stage.classList.contains('is-live')) stage.classList.add('is-live');
    if (parado) { fino = true; ultimoQuadro = 0; return; }
    pede();
  }

  /* ------------------------------------------------------------
     GESTOS — um ponteiro gira (e inclina na tela cheia), dois dão
     pinça; toque curto escolhe a unidade sob o dedo.
     ------------------------------------------------------------ */
  var ponteiros = {}, pinca = 0, meio0 = null, ultimoGesto = 0, percorrido = 0, origem = null;
  var ray, ptr, ultimoHover = 0;

  function ativos() { return Object.keys(ponteiros); }
  function distancia() {
    var ids = ativos(); var a = ponteiros[ids[0]], b = ponteiros[ids[1]];
    return Math.sqrt((a.x - b.x) * (a.x - b.x) + (a.y - b.y) * (a.y - b.y));
  }
  function meioY() { var ids = ativos(); return (ponteiros[ids[0]].y + ponteiros[ids[1]].y) / 2; }

  var CHAVE = 'cinnamon-fachada-gesto';
  function tocou() {
    if (stage.classList.contains('is-touched')) return;
    stage.classList.add('is-touched');
    try { window.sessionStorage.setItem(CHAVE, '1'); } catch (err) { /* modo privado */ }
  }
  try { if (window.sessionStorage.getItem(CHAVE)) stage.classList.add('is-touched'); } catch (err) { /* idem */ }

  /* o que conta como "clicar num studio": a janela dele OU qualquer parte da faixa
     do pavimento (sacada, forro, guarda, parede) — a janela fica recuada atrás da
     sacada e, de lado, quase não aparece. No segundo caso vale o studio daquele
     andar (tirado da altura do toque) mais próximo do ponto, até 4,5 m. Núcleo,
     madeira das pontas, cobertura e térreo não escolhem nada. */
  function sobUnidade(x, y) {
    if (!model) return null;
    ray = ray || new THREE.Raycaster();
    ptr = ptr || new THREE.Vector2();
    var r = canvas.getBoundingClientRect();
    ptr.set((x - r.left) / r.width * 2 - 1, -((y - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(ptr, cam);
    var hits = ray.intersectObjects(malhasUnidade.concat(malhasPav, malhasFixas), false);
    for (var i = 0; i < hits.length; i++) {
      var h = hits[i], o = h.object;
      if (o.material.transparent) continue;               /* vidro não esconde a unidade atrás */
      if (o.userData.unidades) {
        var stu = Math.round(o.geometry.attributes.stu.getX(h.face.a));
        return unidades['P' + pad(pavDaInstancia[h.instanceId]) + '-S' + pad(stu)] || null;
      }
      if (!o.userData.pav) return null;                   /* núcleo, pontas, cobertura, térreo */
      var pav = clamp(Math.floor((h.point.y - TERREO_M + 0.3) / PE_M) + 1, 1, N_PAV);
      var melhor = null, dmin = 4.5;
      (unidadesPorAndar[pav] || []).forEach(function (u) {
        var d = u.centro.distanceTo(h.point);
        if (d < dmin) { dmin = d; melhor = u; }
      });
      return melhor;
    }
    return null;
  }

  canvas.addEventListener('pointerdown', function (e) {
    if (e.pointerType === 'mouse' && e.button !== 0) return;
    ponteiros[e.pointerId] = { x: e.clientX, y: e.clientY };
    try { canvas.setPointerCapture(e.pointerId); } catch (err) { /* já solto */ }
    solto = false; vYaw = 0;
    pinca = ativos().length === 2 ? distancia() : 0;
    meio0 = ativos().length === 2 ? meioY() : null;
    ultimoGesto = e.timeStamp; percorrido = 0;
    origem = { x: e.clientX, y: e.clientY };
  });

  canvas.addEventListener('pointermove', function (e) {
    var p = ponteiros[e.pointerId];
    if (!p) {
      if (mqFine.matches && vivo && !ativos().length && e.timeStamp - ultimoHover > 90) {
        ultimoHover = e.timeStamp;
        canvas.classList.toggle('is-hit', !!sobUnidade(e.clientX, e.clientY));
      }
      return;
    }
    var dx = e.clientX - p.x, dy = e.clientY - p.y;
    p.x = e.clientX; p.y = e.clientY;
    var n = ativos().length;
    if (n === 2) {
      /* pinça aproxima no ponto entre os dedos; arrastar os dois dedos sobe/desce a vista */
      var d = distancia(), m = meioY();
      if (pinca && d) { aproxima(pinca / d, true, syDe(m)); tocou(); }
      if (meio0 !== null) { alvoCentro[1] += (m - meio0) * metroPorPx(); centro[1] = alvoCentro[1]; }
      pinca = d; meio0 = m;
      pede();
      return;
    }
    if (n !== 1) return;
    if (!expandido && e.pointerType === 'touch') dy = 0;   /* vertical é da página */
    percorrido += Math.abs(dx) + Math.abs(dy);
    if (percorrido > 12) { tocou(); girando = false; }
    var k = 1.6 / Math.max(1, canvas.clientWidth);        /* meia-volta por largura */
    var dt = Math.max(1, e.timeStamp - ultimoGesto);
    ultimoGesto = e.timeStamp;
    vYaw = vYaw * 0.6 + (-dx * k * Math.PI / dt) * 0.4;
    alvoYaw -= dx * k * Math.PI;
    yaw = alvoYaw - (alvoYaw - yaw) * 0.5;                /* arrasto quase 1:1, planeio só no fim */
    /* vertical: de perto sobe/desce pela torre (o prédio acompanha o dedo); de longe inclina */
    var w = pesoAltura();
    if (w > 0 && dy) { alvoCentro[1] += dy * metroPorPx() * w; centro[1] = alvoCentro[1] - (alvoCentro[1] - centro[1]) * 0.5; }
    alvoPitch = clamp(alvoPitch + dy * k * 1.2 * (1 - w), pitchMin(), pitchMax());
    pede();
  });

  function solta(e) {
    if (!ponteiros[e.pointerId]) return;
    delete ponteiros[e.pointerId];
    pinca = 0; meio0 = null;
    if (ativos().length) { vYaw = 0; return; }
    var curto = origem && Math.abs(e.clientX - origem.x) + Math.abs(e.clientY - origem.y) < 6;
    if (e.type === 'pointerup' && curto) {
      var u = sobUnidade(e.clientX, e.clientY);
      if (u) escolhe(u);
      vYaw = 0;
    } else {
      solto = e.type === 'pointerup' && !mqReduce.matches && e.timeStamp - ultimoGesto <= 80;
    }
    pede();
  }
  canvas.addEventListener('pointerup', solta);
  canvas.addEventListener('pointercancel', solta);

  /* zoom no ponto: o que está sob o cursor (ou entre os dedos) fica no lugar na altura —
     aproximar em cima do térreo desce até ele, em cima da coroa sobe até ela */
  function aproxima(fator, direto, sy) {
    var nova = clamp(alvoDist * fator, DIST_MIN, DIST_MAX), f = nova / alvoDist;
    if (sy) {
      var py = alvoCentro[1] + sy * alvoDist * Math.tan(cam.fov * Math.PI / 360);
      alvoCentro[1] = py + (alvoCentro[1] - py) * f;
    }
    alvoDist = nova;
    if (direto) { dist = alvoDist; centro[1] = alvoCentro[1]; }
    pede();
  }
  /* botões ▲▼ e PageUp/PageDown: sobem e descem a vista (de longe, aproximam antes) */
  function subir(sentido) {
    if (alvoDist > 130) alvoDist = 120;
    alvoCentro[1] += sentido * Math.max(4, alvoDist * Math.tan(cam.fov * Math.PI / 360) * 0.6);
    girando = false;
    pede();
  }

  canvas.addEventListener('wheel', function (e) {
    if (!expandido && !e.ctrlKey) return;
    e.preventDefault();
    tocou();
    aproxima(e.ctrlKey ? clamp(1 + e.deltaY * 0.01, 0.7, 1.4) : (e.deltaY > 0 ? 1 + WHEEL_STEP : 1 - WHEEL_STEP), false, syDe(e.clientY));
  }, { passive: false });

  canvas.addEventListener('keydown', function (e) {
    var k = e.key;
    if (k === 'ArrowLeft') alvoYaw += KEY_STEP;
    else if (k === 'ArrowRight') alvoYaw -= KEY_STEP;
    else if (k === 'ArrowUp') alvoPitch = clamp(alvoPitch + KEY_STEP, pitchMin(), pitchMax());
    else if (k === 'ArrowDown') alvoPitch = clamp(alvoPitch - KEY_STEP, pitchMin(), pitchMax());
    else if (k === 'PageUp') subir(1);
    else if (k === 'PageDown') subir(-1);
    else if (k === '+' || k === '=') aproxima(1 - ZOOM_STEP);
    else if (k === '-' || k === '_') aproxima(1 + ZOOM_STEP);
    else return;
    e.preventDefault();
    girando = false;
    tocou();
    pede();
  });

  Array.prototype.forEach.call(stage.querySelectorAll('[data-fachada-zoom]'), function (btn) {
    var fator = btn.getAttribute('data-fachada-zoom') === 'in' ? 1 - ZOOM_STEP : 1 + ZOOM_STEP;
    btn.addEventListener('click', function () { tocou(); aproxima(fator); });
  });
  Array.prototype.forEach.call(stage.querySelectorAll('[data-fachada-altura]'), function (btn) {
    var sentido = btn.getAttribute('data-fachada-altura') === 'up' ? 1 : -1;
    btn.addEventListener('click', function () { tocou(); subir(sentido); });
  });

  /* ------------------------------------------------------------
     VISTA — API do seletor de ângulos (js/fachada-gizmo.js). O seletor
     não mexe na câmera direto: lê a vista e pede ângulos. A cada quadro
     em que a câmera anda, o palco dispara 'fachada:vista' com
     { yaw, pitch, dist } (radianos e metros; yaw 0 = câmera ao sul da
     torre olhando para o norte, cresce no sentido anti-horário visto de
     cima — a mesma convenção da órbita acima).
     ------------------------------------------------------------ */
  function maisPerto(alvo, atual) {                  /* mesmo ângulo, a volta mais curta */
    var d = ((alvo - atual + Math.PI) % (2 * Math.PI) + 2 * Math.PI) % (2 * Math.PI) - Math.PI;
    return atual + d;
  }
  stage.f3dVista = {
    YAW_INICIAL: YAW_START, PITCH_INICIAL: PITCH_START, DIST_INICIAL: DIST_START,
    le: function () {
      return { yaw: yaw, pitch: pitch, dist: dist, alvoYaw: alvoYaw, alvoPitch: alvoPitch, alvoDist: alvoDist,
               pitchMin: pitchMin(), pitchMax: pitchMax(), vivo: vivo };
    },
    /* gira e inclina a partir do alvo atual (radianos) */
    gira: function (dYaw, dPitch) {
      alvoYaw += dYaw || 0;
      alvoPitch = clamp(alvoPitch + (dPitch || 0), pitchMin(), pitchMax());
      girando = false; tocou(); pede();
    },
    /* vai para um ângulo absoluto; pitch e dist são opcionais (null mantém) */
    vai: function (y, p, d) {
      if (typeof y === 'number') alvoYaw = maisPerto(y, alvoYaw);
      if (typeof d === 'number') alvoDist = clamp(d, DIST_MIN, DIST_MAX);
      if (typeof p === 'number') alvoPitch = clamp(p, pitchMin(), pitchMax());
      girando = false; tocou(); pede();
    },
    /* vista inicial: ângulo, distância, centro e lente de volta ao começo */
    inicio: function () {
      alvoYaw = maisPerto(YAW_START, alvoYaw); alvoPitch = PITCH_START; alvoDist = DIST_START;
      alvoCentro = CENTRO.slice(); alvoDesloc = [0, 0];
      girando = false; tocou(); pede();
    }
  };
  var vistaAnterior = '';
  function avisaVista() {
    var chave = yaw.toFixed(4) + ',' + pitch.toFixed(4) + ',' + dist.toFixed(2);
    if (chave === vistaAnterior) return;
    vistaAnterior = chave;
    stage.dispatchEvent(new CustomEvent('fachada:vista', { detail: { yaw: yaw, pitch: pitch, dist: dist } }));
  }

  /* ------------------------------------------------------------
     TELA CHEIA — igual ao tour: Fullscreen API onde há; no iPhone a
     classe .is-expanded fixa o palco sobre a página.
     ------------------------------------------------------------ */
  var nativa = !!(stage.requestFullscreen && document.fullscreenEnabled);

  function expande(sim) {
    if (sim === expandido) return;
    expandido = sim;
    stage.classList.toggle('is-expanded', sim);
    if (fullBtn) fullBtn.setAttribute('aria-label', sim ? 'Sair da tela cheia' : 'Tela cheia');
    var lenis = window.CINNAMON && window.CINNAMON.lenis;
    if (sim) { if (lenis) lenis.stop(); document.documentElement.style.overflow = 'hidden'; }
    else {
      if (lenis) lenis.start();
      document.documentElement.style.removeProperty('overflow');
      if (fullBtn && stage.contains(document.activeElement)) fullBtn.focus();
    }
    redimensiona();
  }

  function alterna() {
    if (expandido) {
      if (document.fullscreenElement === stage) document.exitFullscreen();
      else expande(false);
    } else if (nativa) {
      stage.requestFullscreen().catch(function () { expande(true); });
    } else { expande(true); }
  }

  document.addEventListener('fullscreenchange', function () { expande(document.fullscreenElement === stage); });
  if (fullBtn) fullBtn.addEventListener('click', alterna);
  var closeBtn = q('[data-fachada-close]');
  if (closeBtn) closeBtn.addEventListener('click', alterna);

  document.addEventListener('keydown', function (e) {
    if (!expandido) return;
    if (e.key === 'Escape') { alterna(); return; }
    if (e.key !== 'Tab') return;
    var alvos = Array.prototype.slice.call(stage.querySelectorAll('button, canvas, select, a'))
      .filter(function (el) { return el.offsetParent !== null; });
    if (!alvos.length) return;
    var primeiro = alvos[0], ultimo = alvos[alvos.length - 1];
    if (e.shiftKey && document.activeElement === primeiro) { e.preventDefault(); ultimo.focus(); }
    else if (!e.shiftKey && document.activeElement === ultimo) { e.preventDefault(); primeiro.focus(); }
  });

  /* ------------------------------------------------------------
     ATALHOS — links para #fachada pousam com o palco inteiro na tela
     (mesma régua do tour).
     ------------------------------------------------------------ */
  function posicaoDoPalco() {
    var barra = document.querySelector('.site-header');
    var topo = barra ? barra.getBoundingClientRect().bottom : 0;
    var doc = document.documentElement;
    var folga = Math.max(0, (doc.clientHeight - topo - stage.offsetHeight) / 2);
    var y = window.pageYOffset + stage.getBoundingClientRect().top - topo - folga;
    return Math.round(clamp(y, 0, doc.scrollHeight - doc.clientHeight));
  }

  /* Sem Lenis (celular): o scroll suave nativo não segura a viagem — numa
     página de ~20 mil px o Chrome de celular o interrompe no meio do
     caminho e o atalho deixa o visitante longe do palco. Aqui a viagem é
     um tween por frame (o CSS tem scroll-behavior:smooth, então cada passo
     pede 'instant') e, no fim, confere o destino de novo. Um toque ou a
     roda do visitante cancelam a viagem. */
  function viajaSemLenis(destino) {
    var inicio = window.pageYOffset;
    var dist = destino - inicio;
    if (mqReduce.matches || Math.abs(dist) < 2) {
      window.scrollTo({ top: destino, behavior: 'instant' });
      return;
    }
    var dur = clamp(Math.abs(dist) / 10, 700, 1500);
    var t0 = null;
    var viva = true;
    function cancela() { viva = false; }
    window.addEventListener('touchstart', cancela, { passive: true, once: true });
    window.addEventListener('wheel', cancela, { passive: true, once: true });
    function passo(agora) {
      if (!viva) return;
      if (t0 === null) t0 = agora;
      var k = Math.min(1, (agora - t0) / dur);
      var e = k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
      window.scrollTo({ top: Math.round(inicio + dist * e), behavior: 'instant' });
      if (k < 1) { requestAnimationFrame(passo); return; }
      var y = posicaoDoPalco();
      if (Math.abs(y - window.pageYOffset) > 1) window.scrollTo({ top: y, behavior: 'instant' });
    }
    requestAnimationFrame(passo);
  }

  Array.prototype.forEach.call(document.querySelectorAll('a[href="#fachada"]'), function (link) {
    link.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      parte();
      var lenis = window.CINNAMON && window.CINNAMON.lenis;
      if (lenis) {
        lenis.scrollTo(posicaoDoPalco(), { onComplete: function () {
          var y = posicaoDoPalco();
          if (Math.abs(y - window.pageYOffset) > 1) lenis.scrollTo(y, { immediate: true, force: true });
        } });
      } else {
        viajaSemLenis(posicaoDoPalco());
      }
    });
  });

  /* ------------------------------------------------------------
     PARTIDA — Three.js e o modelo só vêm quando a seção está a uma
     tela de distância. O pôster segura o lugar; sem WebGL ou com a
     rede falhando ele fica, com o aviso.
     ------------------------------------------------------------ */
  function falha(err) {
    stage.classList.remove('is-loading');
    stage.classList.add('is-failed');
    if (errorEl) errorEl.hidden = false;
    if (window.console && err) console.warn('[fachada3d]', err);
  }

  function parte() {
    if (partiu) return;
    partiu = true;
    var gl = document.createElement('canvas').getContext('webgl2') || document.createElement('canvas').getContext('webgl');
    if (!gl) { falha('sem WebGL'); return; }
    stage.classList.add('is-loading');
    var mods = [
      import('three'),
      import(CDN + 'examples/jsm/loaders/GLTFLoader.js'),
      import(CDN + 'examples/jsm/environments/RoomEnvironment.js'),
      import(CDN + 'examples/jsm/utils/BufferGeometryUtils.js')
    ];
    if (!leve) {
      mods.push(
        import(CDN + 'examples/jsm/postprocessing/EffectComposer.js'),
        import(CDN + 'examples/jsm/postprocessing/RenderPass.js'),
        import(CDN + 'examples/jsm/postprocessing/UnrealBloomPass.js'),
        import(CDN + 'examples/jsm/postprocessing/OutputPass.js'));
    }
    var modelo = fetch(GLB).then(function (r) { if (!r.ok) throw new Error(GLB + ' ' + r.status); return r.arrayBuffer(); });
    Promise.all([Promise.all(mods), modelo]).then(function (res) {
      var m = res[0];
      var pacote = { three: m[0], GLTFLoader: m[1].GLTFLoader, RoomEnvironment: m[2].RoomEnvironment };
      mods3 = m[3];
      if (!leve) {
        pacote.EffectComposer = m[4].EffectComposer;
        pacote.RenderPass = m[5].RenderPass; pacote.UnrealBloomPass = m[6].UnrealBloomPass; pacote.OutputPass = m[7].OutputPass;
      }
      return new Promise(function (ok, erro) {
        new pacote.GLTFLoader().parse(res[1], '', function (glb) { ok([pacote, glb]); }, erro);
      });
    }).then(function (par) {
      vivo = true;
      monta(par[0], par[1]);
      stage.classList.remove('is-loading');
    }).catch(falha);
  }

  if ('IntersectionObserver' in window) {
    new IntersectionObserver(function (entradas) {
      entradas.forEach(function (en) {
        if (en.isIntersecting) parte();
        visivel = en.isIntersecting;
        if (visivel) pede();
      });
    }, { rootMargin: '100% 0px' }).observe(stage);
  } else { parte(); }

  document.addEventListener('visibilitychange', function () { if (!document.hidden) pede(); });
  window.addEventListener('resize', redimensiona);
  window.addEventListener('orientationchange', redimensiona);
}());
