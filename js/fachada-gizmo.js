/* ============================================================
   CINNAMON STUDIO — fachada-gizmo.js
   Seletor de ângulos da torre 3D (#fachada), como o das ferramentas
   de 3D: um círculo com o ponto central e os eixos do prédio.

   - Arrastar dentro do círculo (de qualquer ponto, aro incluído) gira
     360° e inclina, com o mesmo ganho do arraste no canvas.
   - Os eixos são projetados da câmera e giram junto a cada quadro:
     o eixo creme liga as duas faces da ala dos studios 17 a 30, o
     tan as da ala 01 a 16, o tracejado é a vertical. Ponto cheio =
     fachada externa; anel vazado = face interna do L; pontos menores =
     quinas. Tocar num ponto leva à vista.
   - No aro: setas para girar até a próxima fachada ou quina e para
     inclinar 15° (agem ao soltar; segurar repete) e, na diagonal de cima à direita,
     o anel com ponto da vista de cima (fixo: na ponta do eixo vertical
     ele caía sobre o ponto da face de trás).
   - Ponto central: volta à vista inicial.
   - Teclado: com o foco no seletor, as setas giram e inclinam aos
     poucos; Shift + esquerda/direita vai à próxima fachada ou quina;
     Home volta à vista inicial. Uma região aria-live diz a vista
     quando a câmera para.

   Ponteiro: os botões não recebem o ponteiro (pointer-events:none no
   css) — o seletor inteiro escuta e escolhe o alvo mais próximo do
   dedo. Assim nenhum ponto cobre o vizinho e a área de cada um é a
   maior possível; os botões ficam para o teclado e o leitor de tela.

   A planta não traz o norte: nada de pontos cardeais aqui.
   Não mexe na câmera direto — usa stage.f3dVista (js/fachada3d.js) e
   escuta 'fachada:vista'. Reduced-motion: a própria API pula o planeio.

   Desenho: só transform. A projeção do chão é afim, então o chão, a
   planta e os eixos horizontais vivem num <g> com uma matriz; a
   vertical é um scaleY; os pontos, translate.
   ============================================================ */
(function () {
  'use strict';

  var stage = document.querySelector('[data-fachada]');
  if (!stage) return;
  var raiz = stage.querySelector('[data-fachada-gizmo]');
  if (!raiz) return;

  var PI = Math.PI, GRAU = PI / 180;
  var VB = 92;                          /* largura do viewBox do SVG (-46..46) */
  var R_EIXO = 24;                      /* raio dos pontos das fachadas (unidades do viewBox) */
  /* olho do seletor: a inclinação da câmera (−0,4 … 1,48) vira 0,7 … 1,48 — na altura dos
     olhos o chão viraria uma linha e os pontos da frente e de trás encostariam no centro */
  var PITCH_TETO = 1.48, PITCH_PISO = -0.4, OLHO_MIN = 0.7;
  var PITCH_CIMA = 1.45, DIST_CIMA = 150, DIST_CIMA_CELULAR = 230;
  var mqCelular = window.matchMedia('(max-width: 768px)');   /* o mesmo corte do css */
  var PASSO_INCL = 15 * GRAU;
  var TECLA_GIRO = 15 * GRAU, TECLA_INCL = 5 * GRAU;
  var ESPERA = 420, REPETE = 260;       /* segurar a seta: espera e ritmo da repetição (ms) */
  var ARRASTE_MIN = 5;                  /* px: abaixo disso é toque; acima, vira arraste */
  /* alvos do ponteiro (px). Centro: um disco só dele (24 px de diâmetro). Aro: do raio dos
     pontos (+ folga) até a borda do toque, só das setas e da vista de cima — cada seta fica
     com um setor inteiro; a vista de cima é um disco na fronteira cima/direita, então as
     outras fronteiras andam alguns graus (SETOR, medido no celular) para as quatro setas
     ficarem com a mesma área, ~40 × 40 px. Miolo: o ponto mais próximo. */
  var ALCANCE = { cima: 13, centro: 12.5, ponto: 13 };
  var FOLGA_ARO = 1;
  var SETOR = { cima: 45, esquerda: 139.5, baixo: 221.5, direita: 306 };   /* início de cada setor (graus) */
  var MULTA_TRAS = 3;                   /* px: entre dois pontos quase juntos, vence o da frente */

  var plano = raiz.querySelector('[data-gz-plano]');
  var vertical = raiz.querySelector('[data-gz-vertical]');
  var topo = raiz.querySelector('[data-gz-topo]');
  var eixos = Array.prototype.slice.call(raiz.querySelectorAll('[data-gz-eixo]'));
  var pontos = Array.prototype.slice.call(raiz.querySelectorAll('[data-gz-yaw]'));
  var centroBtn = raiz.querySelector('[data-gz-inicio]');
  var passos = Array.prototype.slice.call(raiz.querySelectorAll('[data-gz-passo]'));
  var anuncio = raiz.querySelector('[data-gz-anuncio]');
  var canvas = stage.querySelector('canvas');

  function api() { return stage.f3dVista || null; }
  function yawDo(el) {
    var v = el.getAttribute('data-gz-yaw');
    if (v === 'inicial') { var a = api(); return a ? a.YAW_INICIAL : -2.46; }
    return parseFloat(v) * GRAU;
  }
  function difAng(a, b) {               /* diferença angular em (−π, π] */
    return ((a - b + PI) % (2 * PI) + 2 * PI) % (2 * PI) - PI;
  }
  function nome(el) { return el.getAttribute('data-gz-nome') || el.getAttribute('aria-label') || ''; }
  var vistas = pontos.filter(function (el) { return el.getAttribute('data-gz-tipo') !== 'cima'; });

  /* ------------------------------------------------------------
     DESENHO — projeta os eixos com o yaw/pitch atuais da câmera
     ------------------------------------------------------------ */
  var escala = 1;
  function mede() { escala = (raiz.clientWidth || VB) / VB; }

  var ultimo = { yaw: null, pitch: null };
  function olho(pitch) {
    var t = Math.max(0, Math.min(1, (pitch - PITCH_PISO) / (PITCH_TETO - PITCH_PISO)));
    return OLHO_MIN + (PITCH_TETO - OLHO_MIN) * t;
  }
  function f(n) { return n.toFixed(4); }
  function desenha(yaw, pitch) {
    ultimo.yaw = yaw; ultimo.pitch = pitch;
    var pg = olho(pitch);
    var cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pg), sp = Math.sin(pg);

    /* chão (x, z) -> tela do seletor: x' = x·cy − z·sy ; y' = sp·(x·sy + z·cy) */
    plano.style.transform = 'matrix(' + f(cy) + ',' + f(sp * sy) + ',' + f(-sy) + ',' + f(sp * cy) + ',0,0)';
    vertical.style.transform = 'scale(1,' + f(cp) + ')';
    topo.style.transform = 'translate(0px,' + (-R_EIXO * cp).toFixed(2) + 'px)';

    eixos.forEach(function (ln) {
      var Y = parseFloat(ln.getAttribute('data-gz-eixo')) * GRAU;
      ln.classList.toggle('is-tras', cp * Math.cos(Y - yaw) < -0.12);
    });

    var foco = document.activeElement;
    pontos.forEach(function (el) {
      var atual, z;
      if (el.getAttribute('data-gz-tipo') === 'cima') {
        atual = pitch > 1.35;
        z = 24;
      } else {
        var Y = yawDo(el), x = Math.sin(Y) * R_EIXO, w = Math.cos(Y) * R_EIXO;
        var h = x * sy + w * cy, d = cp * h / R_EIXO;          /* profundidade: + = para a câmera */
        var tx = (x * cy - w * sy) * escala, ty = sp * h * escala;
        el.style.transform = 'translate(' + tx.toFixed(1) + 'px,' + ty.toFixed(1) + 'px)';
        el._gzTras = d < -0.12;
        el.classList.toggle('is-tras', el._gzTras);
        atual = pitch < 0.9 && Math.abs(difAng(Y, yaw)) < 3 * GRAU;
        z = 10 + Math.round((d + 1) * 6);                       /* 10..22: os da frente por cima */
      }
      if (el === foco) z = 40;                                   /* o focado nunca fica embaixo */
      if (el._gzZ !== z) { el._gzZ = z; el.style.zIndex = String(z); }
      el.classList.toggle('is-atual', atual);
      if (atual) el.setAttribute('aria-current', 'true'); else el.removeAttribute('aria-current');
    });
  }

  function redesenha() {
    var a = api();
    if (!a) return;
    var v = a.le();
    desenha(v.yaw, v.pitch);
  }

  stage.addEventListener('fachada:vista', function (e) {
    var d = e.detail || {};
    if (typeof d.yaw === 'number' && typeof d.pitch === 'number') desenha(d.yaw, d.pitch);
    if (anunciar) agendaAnuncio();
  });
  raiz.addEventListener('focusin', function () { redesenha(); seguraGiro(); });
  raiz.addEventListener('focusout', function () { setTimeout(redesenha, 0); });

  /* altura do palco e da folha: no celular, com a folha aberta, o círculo sobe por
     transform até logo acima dela (css) */
  var folha = stage.querySelector('.fachada__panel');
  function medePalco() {
    raiz.style.setProperty('--gz-palco', stage.clientHeight + 'px');
    var hf = folha ? folha.offsetHeight : 0;
    if (hf) raiz.style.setProperty('--gz-folha', hf + 'px'); else raiz.style.removeProperty('--gz-folha');
  }
  if (window.ResizeObserver) {
    new ResizeObserver(function () { mede(); if (ultimo.yaw !== null) desenha(ultimo.yaw, ultimo.pitch); }).observe(raiz);
    var ro = new ResizeObserver(medePalco);
    ro.observe(stage);
    if (folha) ro.observe(folha);
  } else {
    window.addEventListener('resize', function () { mede(); medePalco(); redesenha(); });
  }
  mede();
  medePalco();
  redesenha();

  /* ------------------------------------------------------------
     ANÚNCIO — quando a câmera para depois de um gesto no seletor,
     a região aria-live diz a vista mais próxima
     ------------------------------------------------------------ */
  var anunciar = false, relAnuncio = 0;
  function agendaAnuncio() {
    clearTimeout(relAnuncio);
    relAnuncio = setTimeout(falaVista, 650);
  }
  function pedeAnuncio() { anunciar = true; agendaAnuncio(); }
  function falaVista() {
    anunciar = false;
    var a = api();
    if (!a || !anuncio) return;
    var v = a.le(), txt;
    if (v.pitch > 1.35) txt = 'Vista de cima';
    else {
      var melhor = null, dm = 9;
      vistas.forEach(function (el) {
        var d = Math.abs(difAng(yawDo(el), v.yaw));
        if (d < dm) { dm = d; melhor = el; }
      });
      var g = Math.round(v.pitch / GRAU);
      txt = (dm < 3 * GRAU ? '' : 'Perto de: ') + nome(melhor) + ', câmera ' +
        (g === 0 ? 'na altura do meio da torre' : Math.abs(g) + (g > 0 ? ' graus acima' : ' graus abaixo') + ' do meio da torre');
    }
    anuncio.textContent = txt;
  }

  /* ------------------------------------------------------------
     VISTAS — pontos dos eixos, centro e vista de cima
     ------------------------------------------------------------ */
  function vaiPara(el) {
    var a = api();
    if (!a) return;
    if (el.getAttribute('data-gz-tipo') === 'cima') {
      /* de cima, a torre inteira: o centro e a lente voltam ao meio da maquete (com um
         studio aberto a órbita estava no studio e, no computador, a planta saía cortada
         à esquerda). No celular com a folha aberta, não: o meio da maquete cairia sob a
         folha — a órbita fica no studio, que a lente já pôs acima dela. Celular: de mais
         longe, a lente é estreita. */
      var v = a.le(), y = v.alvoYaw, celular = mqCelular.matches;
      var d = Math.max(v.alvoDist, celular ? DIST_CIMA_CELULAR : DIST_CIMA);
      if (!(celular && stage.classList.contains('has-panel'))) a.inicio();
      a.vai(y, PITCH_CIMA, d);
    } else {
      a.vai(yawDo(el), a.PITCH_INICIAL, null);
    }
    pedeAnuncio();
  }
  /* vista inicial. No celular com a folha do studio aberta, fecha a folha antes: a vista
     inicial é a torre inteira com o térreo e o letreiro, e a folha cobriria a metade de baixo */
  var fechaFolha = stage.querySelector('[data-fachada-panel-close]');
  function inicio() {
    var a = api();
    if (!a) return;
    if (mqCelular.matches && stage.classList.contains('has-panel') && fechaFolha) fechaFolha.click();
    a.inicio();
    pedeAnuncio();
  }

  /* paradas do giro: as 4 fachadas e as 4 quinas (a do letreiro é a da vista inicial) */
  function proximaParada(de, sentido) {
    var melhor = 2 * PI;
    vistas.forEach(function (el) {
      var d = ((sentido * (yawDo(el) - de)) % (2 * PI) + 2 * PI) % (2 * PI);
      if (d > 2 * GRAU && d < melhor) melhor = d;
    });
    return sentido * melhor;
  }
  function giraParada(sentido) {
    var a = api();
    if (!a) return;
    a.gira(proximaParada(a.le().alvoYaw, sentido), 0);
  }
  function passo(el) {
    var a = api();
    if (!a) return;
    var k = el.getAttribute('data-gz-passo');
    if (k === 'esquerda') giraParada(1);
    else if (k === 'direita') giraParada(-1);
    else if (k === 'cima') a.gira(0, PASSO_INCL);
    else if (k === 'baixo') a.gira(0, -PASSO_INCL);
    pedeAnuncio();
  }

  /* teclado e leitor de tela: o clique do botão. Se o mesmo gesto já agiu pelo ponteiro
     (o leitor às vezes manda pointerdown + click), o click é ignorado */
  var ultimoPonteiro = 0;
  function recente() { return Date.now() - ultimoPonteiro < 600; }
  pontos.forEach(function (el) { el.addEventListener('click', function () { if (!recente()) vaiPara(el); }); });
  if (centroBtn) centroBtn.addEventListener('click', function () { if (!recente()) inicio(); });
  passos.forEach(function (el) { el.addEventListener('click', function () { if (!recente()) passo(el); }); });

  /* ------------------------------------------------------------
     PONTEIRO — o alvo sob o dedo (ver alvoEm). Tudo age ao soltar,
     se não virou arraste: tocar e arrastar a partir de qualquer ponto
     do círculo, aro incluído, gira e inclina. Seta segurada repete.
     ------------------------------------------------------------ */
  function tipoDe(el) {
    if (el === centroBtn) return 'centro';
    if (el.hasAttribute('data-gz-passo')) return 'passo';
    return el.getAttribute('data-gz-tipo') === 'cima' ? 'cima' : 'ponto';
  }
  var passoDe = {};
  passos.forEach(function (el) { passoDe[el.getAttribute('data-gz-passo')] = el; });
  var cimaBtn = pontos.filter(function (el) { return el.getAttribute('data-gz-tipo') === 'cima'; })[0] || null;
  function distAo(el, x, y) {
    var r = el.getBoundingClientRect();
    return Math.hypot(x - (r.left + r.width / 2), y - (r.top + r.height / 2));
  }
  function setaDoSetor(graus) {         /* 0° = direita, cresce no sentido anti-horário */
    if (graus >= SETOR.cima && graus < SETOR.esquerda) return passoDe.cima;
    if (graus >= SETOR.esquerda && graus < SETOR.baixo) return passoDe.esquerda;
    if (graus >= SETOR.baixo && graus < SETOR.direita) return passoDe.baixo;
    return passoDe.direita;
  }
  function alvoEm(x, y) {
    var g = raiz.getBoundingClientRect();
    var dx = x - (g.left + g.width / 2), dy = y - (g.top + g.height / 2);
    var r = Math.hypot(dx, dy);
    if (centroBtn && r <= ALCANCE.centro) return centroBtn;
    if (r >= g.width * R_EIXO / VB + FOLGA_ARO) {                 /* aro */
      if (cimaBtn && distAo(cimaBtn, x, y) <= ALCANCE.cima) return cimaBtn;
      var graus = (Math.atan2(-dy, dx) / GRAU + 360) % 360;
      return setaDoSetor(graus) || null;
    }
    var melhor = null, nota = Infinity;                          /* miolo: os pontos */
    vistas.forEach(function (el) {
      var d = distAo(el, x, y);
      if (d > ALCANCE.ponto) return;
      if (el._gzTras) d += MULTA_TRAS;
      if (d < nota) { nota = d; melhor = el; }
    });
    return melhor;
  }
  /* para o QA: qual botão um toque em (x, y) acionaria */
  raiz.f3dGizmoAlvo = function (x, y) { var el = alvoEm(x, y); return el ? el.getAttribute('aria-label') : null; };

  var mira = null;
  function mostraMira(el) {
    if (el === mira) return;
    if (mira) mira.classList.remove('is-mira');
    mira = el;
    if (el) { el.classList.add('is-mira'); raiz.title = nome(el); raiz.classList.add('is-sobre-alvo'); }
    else { raiz.removeAttribute('title'); raiz.classList.remove('is-sobre-alvo'); }
  }

  var relogio = 0;
  function paraRepeticao() { clearTimeout(relogio); clearInterval(relogio); relogio = 0; }

  /* o mesmo ganho do canvas (js/fachada3d.js): giro 1,6π e inclinação 1,6 × 1,2 rad por
     largura do palco */
  function largura() { return Math.max(1, (canvas && canvas.clientWidth) || stage.clientWidth || 1); }

  /* um gesto por vez: arr = { id, x0, y0, x, y, alvo, tipo, ativo (virou arraste),
     repetiu (a seta já deu passo segurando), morto (saiu da seta segurada), foco } */
  var arr = null;
  function fimGesto() {
    if (!arr) return;
    if (arr.tipo === 'passo') arr.alvo.classList.remove('is-apertado');
    paraRepeticao();
    raiz.classList.remove('is-arrastando');
    arr = null;
  }
  function devolveFoco(era, el) {      /* quem usava o teclado continua com o foco no seletor */
    if (!era.foco) return;
    var dest = el || era.foco;
    if (document.activeElement !== dest) { try { dest.focus({ preventScroll: true }); } catch (err) { dest.focus(); } }
  }
  /* a rotação automática pára quando a pessoa vai usar o seletor (os alvos não fogem) */
  function seguraGiro() { var a = api(); if (a && a.le().vivo !== false) a.gira(0, 0); }

  raiz.addEventListener('pointerdown', function (e) {
    if (e.pointerType === 'mouse' && e.button !== 0) return;
    if (arr) {
      /* segundo dedo com um gesto em curso: ignora (o primeiro manda até soltar) */
      if (e.pointerType !== 'mouse' && e.pointerId !== arr.id) return;
      fimGesto();                       /* sobra de um gesto que perdeu o pointerup */
    }
    var el = alvoEm(e.clientX, e.clientY);
    var t = el ? tipoDe(el) : null;
    ultimoPonteiro = Date.now();
    arr = { id: e.pointerId, x0: e.clientX, y0: e.clientY, x: e.clientX, y: e.clientY, alvo: el, tipo: t,
            ativo: false, repetiu: false, morto: false,
            foco: raiz.contains(document.activeElement) && document.activeElement !== raiz ? document.activeElement : null };
    if (arr.foco) e.preventDefault();   /* o clique não tira o foco do botão */
    seguraGiro();
    if (t === 'passo') {
      /* o passo sai ao soltar (dá para desistir arrastando); segurado, repete */
      el.classList.add('is-apertado');
      var gesto = arr;
      relogio = setTimeout(function () {
        if (arr !== gesto) return;
        gesto.repetiu = true;
        passo(el);
        relogio = setInterval(function () { if (arr === gesto) passo(el); else paraRepeticao(); }, REPETE);
      }, ESPERA);
    }
  });
  window.addEventListener('pointermove', function (e) {
    if (!arr) {
      if (e.pointerType === 'mouse' && raiz.contains(e.target)) mostraMira(alvoEm(e.clientX, e.clientY));
      return;
    }
    if (e.pointerId !== arr.id) return;
    if (e.pointerType === 'mouse' && !e.buttons) { fimGesto(); return; }   /* soltou fora sem pointerup */
    if (arr.morto) return;
    var dx = e.clientX - arr.x, dy = e.clientY - arr.y;
    arr.x = e.clientX; arr.y = e.clientY;
    if (!arr.ativo) {
      if (Math.abs(e.clientX - arr.x0) + Math.abs(e.clientY - arr.y0) < ARRASTE_MIN) return;
      if (arr.tipo === 'passo') {
        if (arr.repetiu) {              /* já repetindo: sair da seta pára, sem arraste */
          if (alvoEm(e.clientX, e.clientY) !== arr.alvo) {
            arr.alvo.classList.remove('is-apertado'); paraRepeticao(); arr.morto = true;
          }
          return;
        }
        arr.alvo.classList.remove('is-apertado'); paraRepeticao();   /* virou arraste: sem passo */
      }
      arr.ativo = true;
      raiz.classList.add('is-arrastando');
      mostraMira(null);
      dx = e.clientX - arr.x0; dy = e.clientY - arr.y0;
    }
    var a = api();
    if (!a) return;
    var w = largura();
    a.gira(-dx * 1.6 * PI / w, dy * 1.6 * 1.2 / w);
  });
  function solta(e) {
    if (!arr || e.pointerId !== arr.id) return;
    var era = arr;
    fimGesto();
    if (era.ativo || era.morto || e.type !== 'pointerup') { devolveFoco(era, null); return; }
    ultimoPonteiro = Date.now();
    if (era.tipo === 'passo') {         /* toque curto na seta: um passo; segurado já passou */
      if (!era.repetiu) passo(era.alvo);
      devolveFoco(era, era.alvo);
      return;
    }
    /* toque curto: vale o alvo sob o ponto onde soltou (se é o mesmo do toque) */
    var el = alvoEm(e.clientX, e.clientY);
    if (!el || el !== era.alvo) { devolveFoco(era, null); return; }
    if (el === centroBtn) inicio(); else vaiPara(el);
    devolveFoco(era, el);
  }
  window.addEventListener('pointerup', solta);
  window.addEventListener('pointercancel', solta);
  raiz.addEventListener('pointerenter', function (e) { if (e.pointerType === 'mouse') seguraGiro(); });
  raiz.addEventListener('pointerleave', function (e) { if (e.pointerType === 'mouse' && !arr) mostraMira(null); });
  window.addEventListener('blur', function () { fimGesto(); mostraMira(null); });

  /* ------------------------------------------------------------
     TECLADO — com o foco em qualquer botão do seletor
     ------------------------------------------------------------ */
  raiz.addEventListener('keydown', function (e) {
    var a = api();
    if (!a || e.altKey || e.ctrlKey || e.metaKey) return;
    var s = e.shiftKey;
    switch (e.key) {
      case 'ArrowLeft':  if (s) giraParada(1); else a.gira(TECLA_GIRO, 0); break;
      case 'ArrowRight': if (s) giraParada(-1); else a.gira(-TECLA_GIRO, 0); break;
      case 'ArrowUp':    a.gira(0, s ? PASSO_INCL : TECLA_INCL); break;
      case 'ArrowDown':  a.gira(0, s ? -PASSO_INCL : -TECLA_INCL); break;
      case 'Home':       inicio(); return stopa(e);
      default: return;
    }
    pedeAnuncio();
    stopa(e);
  });
  function stopa(e) { e.preventDefault(); e.stopPropagation(); }

  raiz.classList.add('is-pronto');
})();
