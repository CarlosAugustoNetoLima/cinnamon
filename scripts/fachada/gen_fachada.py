#!/usr/bin/env python3
"""Cinnamon Studio - maquete da torre em glTF binario para a secao #fachada.

Uso:  python3 scripts/fachada/gen_fachada.py        -> img/fachada.glb

MAQUETE PROVISORIA: volumetria lida dos renders de referencia + planta do
pavimento tipo. Nao e o modelo de arquitetura.

Geometria lida dos renders de referencia + planta do pavimento tipo:
  - torre em L, 30 studios por andar nas 4 faces longas (planta);
  - sacadas em faixa continua de madeira, curva em planta, curva diferente
    a cada pavimento, guarda de vidro, teto iluminado (renders 1, 2, 8);
  - NUCLEO NOROESTE na quina externa A (Render 1 casado com a planta): parede
    de topo do Studio 01 em madeira com o letreiro, fenda de vidro do fim do
    corredor e torre escura da escada com frestas, os tres acima da cobertura;
  - pontas das alas externas (B, F) em painel de madeira alto e aberto para
    fora; linha de cobertura subindo para as pontas (renders 1, 2);
  - terreo: base de pedra, marquise com forro ripado e spots, pano de
    vidro, painel do letreiro retroiluminado (renders 4, 6, 7, 10) — a
    posicao da entrada ainda e suposta (canto interno D).

Numeros: 17 pavimentos-tipo = 510 / 30 (DERIVADO, nao confirmado);
pe-direito, terreo, alturas acima da cobertura e profundidades: AJUSTAR.
Escala S calibrada pela camera do Render 1 (ver comentario de S).
Eixos: X leste, Y cima, Z sul. Metros. Texturas: texturas.py.
"""
import json
import math
import os
import struct
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import texturas  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))

# ------------------------------------------------------------ parametros
PAV_TIPO = 17             # DERIVADO 510/30
# pe-direito e terreo medidos no Render 1 (14/10/2026): faixas de sacada detectadas na foto
# ajustadas com a planta fixa -> 3,01 m e 1a laje a 5,6 m. Continuam AJUSTAR ate o projeto.
PE = 3.0                  # AJUSTAR
TERREO_H = 5.6            # AJUSTAR
Y_ROOF = TERREO_H + PAV_TIPO * PE      # 56 m: topo da laje de cobertura
# o predio fica num embasamento de pedra: o deque (y = 0) esta ~2,5 m acima da praca de
# paralelepipedo (render da quina noroeste no nivel da rua, 14/10/2026). Estimado: AJUSTAR
Y_RUA = -2.0      # Render 1: embasamento de ~2 m sobre piso molhado (lago/espelho); a praca de paralelepipedo saiu
# m/px da planta. Partiu de 29,92 m2 por studio (0,0377); calibrada em 14/10/2026 pela
# camera do Render 1 (quinas A, B, F): com pe-direito 3,0 m a proporcao largura/altura
# da foto pede planta 10,5% maior. Continua dentro da margem de +-15%.
S = 0.0416

def X(px): return (px - 235) * S
def Z(py): return (py - 55) * S

# contorno lido na planta do pavimento tipo (px). No canto interno do L ha um RECORTE:
# a face interna da ala 17-30 so comeca em x=795 (Studio 30); entre ela e a ala 01-16
# fica o vao do hall dos elevadores (x 720-795, ate y=308), que avanca ate y=500.
A = (X(235), Z(55));   B = (X(1415), Z(55));  C = (X(1415), Z(515))
# canto interno (correcao do usuario em 15/10/2026): nenhuma sacada da ala 01-16 pode ficar
# escondida atras da ala 17-30. Na planta o Studio 16 comeca logo depois da linha das sacadas
# da ala de cima (y = 515); aqui as sacadas avancam ~1,75 m alem do contorno, entao a face
# interna da haste so comeca depois dessa linha (y = 560, Z = 21,0 m) e o hall dos elevadores
# ocupa o recanto ate la. Os 6 studios da face ficam um pouco mais estreitos (3,9 m)
Y_HASTE0 = 560
# o vao do hall (x 720-795) NAO e vazado (correcao do usuario em 15/10/2026, vista de cima do
# canto interno): o volume vai cheio ate a cobertura; no canto ficam so duas faces escuras do
# nucleo (a faixa preta do Render 8) — a que olha para leste e a que olha para o sul
C2 = (X(795), Z(515)); C3 = (X(795), Z(Y_HASTE0))
D = (X(695), Z(Y_HASTE0));  E = (X(695), Z(1120)); F = (X(235), Z(1120))
POLY = [A, B, C, C2, C3, D, E, F]       # horario visto de cima
# espelho d'agua em L (render da quina, 14/10/2026): piscina na frente da fachada norte (sob o
# painel e a fenda) que vira canal ao longo da fachada oeste. Medidas estimadas: AJUSTAR
POOL_L = [(-5.0, -5.0), (X(490) - 0.5, -5.0), (X(490) - 0.5, -1.4), (-1.4, -1.4), (-1.4, Z(450)), (-5.0, Z(450))]
POOL_RECTS = [(-5.0, X(490) - 0.5, -5.0, -1.4), (-5.0, -1.4, -1.4, Z(450))]
Y_OESTE0 = 88
GUARDA_RECUO = 0.30   # a ponta de madeira da laje avanca isto alem do vidro reto (pedido do usuario)
# borda de fora do painel NO (embaixo) = linha do vidro das sacadas da fachada oeste
X_PAINEL0 = (235 - 235) * 0.0416 - (1.7 - 0.05 - GUARDA_RECUO)                                    # a ala 01-16 comeca em y=88 (a de cima em 55)

# faces: p0, p1, normal externa, [t0,t1] com sacadas (fracao), nº de studios, 1º studio, sentido
FACES = {
    'norte':       dict(p=(A, B), n=(0, -1), sac=(X(590) / B[0], 1.0), n_st=8, s0=17, inv=False),
    'leste_barra': dict(p=(B, C), n=(1, 0),  sac=None),
    'sul_barra':   dict(p=(C, C2), n=(0, 1), sac=(0.0, 1.0), n_st=6, s0=25, inv=False),
    # canto do hall: duas faces do nucleo escuro (Render 8), sem sacada nem studio
    'hall_1':      dict(p=(C2, C3), n=(1, 0),  sac=None, vidro=True),
    'hall_2':      dict(p=(C3, D), n=(0, 1),   sac=None, vidro=True),
    'leste_haste': dict(p=(D, E), n=(1, 0),  sac=(0.0, 1.0), n_st=6, s0=16, inv=True),
    'sul_haste':   dict(p=(E, F), n=(0, 1),  sac=None),
    # sacadas ate a quina: no Render 1 elas comecam logo atras da borda do painel de madeira; com
    # o recuo de 1,4 m da planta (y=88) ficava uma cunha escura entre o painel e a 1a sacada
    'oeste':       dict(p=(F, A), n=(-1, 0), sac=(0.0, 1.0), n_st=10, s0=10, inv=True),
}
PHASE = {'norte': 0.0, 'sul_barra': 1.1, 'leste_haste': 2.3, 'oeste': 3.4}
# barriga das sacadas no meio de cada face (m alem dos 1,7 m da ponta): norte e oeste medidas
# no Render 1; as faces internas no Render 3 (14/10/2026) — curva das lajes da ala 01-16 vista
# de leste (~2 m) e as 'meias-luas' das sacadas 25-30 passando da parede leste (~1,8 m)
# correcao do usuario (14/10/2026): "as sacadas do centro precisam estar mais distantes" — a curva
# das faixas ficava rasa; sobe ate ~5-6% do comprimento da face (norte 34 m, oeste 43 m, internas 26 m)
# e em 15/10/2026, ao contrario: "diminua mais a acentuacao da curvatura" — fica no meio-termo
BARRIGA = {'norte': 1.1, 'oeste': 1.5, 'sul_barra': 1.3, 'leste_haste': 1.4}

def srgb(hexa, a=1.0):
    """cor de projeto em sRGB (#rrggbb) -> baseColorFactor linear do glTF."""
    r, g_, b = (int(hexa[i:i + 2], 16) / 255 for i in (1, 3, 5))
    lin = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return [lin(r), lin(g_), lin(b), a]

# materiais
(M_LAJE, M_PAREDE, M_MADEIRA, M_VIDRO, M_JANELA, M_VITRINE, M_LAMINA,
 M_PEDRA, M_RIPADO, M_LOGO, M_LUZ, M_DIVISORIA, M_TETO, M_AGUA,
 M_BORDA, M_GUARDA, M_FRESTA, M_ALETA, M_PAINEL, M_TORRE, M_CORR_FUNDO,
 M_MOLDURA, M_CORR_ACESO, M_VIDRO_JANELA, M_JANELA_ESC, M_PARALELEPIPEDO, M_PLACA,
 M_MARMORE, M_LOUNGE, M_MOVEL, M_MOVEL_ESC, M_FOLHAGEM, M_CESTO,
 M_ACM, M_RIPADO_CINZA, M_MONOLITO, M_LAVAGEM, M_TAPETE) = range(38)

def tex(img, nrm=None, mr=None):
    return dict(img=img, nrm=nrm, mr=mr)

MATERIAIS = [
    ('laje_concreto', srgb('#2c2d28'), 0.0, 0.85, None, {}),
    ('parede_escura', srgb('#22231f'), 0.0, 0.75, None, {}),
    # forro das sacadas: no Render 1 a madeira brilha quente sob a iluminacao embutida
    # correcao do usuario: forro e borda da sacada sao da MESMA madeira do painel lateral, so que
    # mais claros pela luz amarela da sacada (emissivo quente sobre a propria textura)
    ('madeira_sacada', [1, 1, 1, 1], 0.0, 0.65, tex('madeira_painel.jpg', 'madeira_painel_n.jpg'),
        {'emissiveFactor': [1.0, 0.84, 0.68], 'emis': 'madeira_painel.jpg', 'strength': 0.5}),
    # guarda toda de vidro fume escuro (render do terreo de perto, 14/10/2026): reflete e ainda
    # deixa ver a cortina acesa atras. Sem azul
    # vidro da guarda mais claro e com mais cara de vidro (pedido do usuario): cinza claro,
    # mais transparente, liso e com reflexo
    ('vidro_guarda', srgb('#b4b5b8', 0.30), 0.15, 0.03, None, {'alphaMode': 'BLEND', 'doubleSided': True}),
    ('janela_unidade', srgb('#15181b'), 0.0, 0.25, None,
        {'emissiveFactor': [1, 1, 1], 'emis': 'cortina.jpg', 'strength': 1.0}),
    ('vitrine_terreo', srgb('#121414'), 0.6, 0.08, None, {'emissiveFactor': [0.5, 0.34, 0.18], 'strength': 0.12}),
    ('lamina_ribeada', [1, 1, 1, 1], 0.35, 0.42, tex('lamina.jpg', 'lamina_n.png'), {}),   # grelha de ventilacao do embasamento
    ('pedra_terreo', [1, 1, 1, 1], 0.0, 0.95, tex('pedra.jpg', 'pedra_n.jpg'), {}),
    ('ripado_madeira', [1, 1, 1, 1], 0.0, 0.7, tex('ripado.jpg', 'ripado_n.png'), {}),
    ('letreiro', [0, 0, 0, 1], 0.0, 0.5, None,
        {'emissiveFactor': [1, 1, 1], 'emis': 'logo.png', 'strength': 1.0, 'alphaMode': 'BLEND', 'alpha_img': 'logo.png'}),
    ('luz_quente', srgb('#3a2d20'), 0.0, 0.5, None, {'emissiveFactor': [1.0, 0.72, 0.42], 'strength': 3.0}),
    ('divisoria', srgb('#1c1d1a'), 0.1, 0.6, None, {'doubleSided': True}),
    ('teto_sacada', srgb('#6b5238'), 0.0, 0.8, None, {'emissiveFactor': [1.0, 0.7, 0.4], 'strength': 0.55}),
    # espelho d'agua: quase preto e muito liso — reflete a torre, sem azul (paleta da marca)
    ('agua', srgb('#0b0c0c'), 0.35, 0.03, None, {}),
    # cores medidas no Render 1 (14/10/2026)
    ('borda_laje', [1, 1, 1, 1], 0.0, 0.6, tex('madeira_painel.jpg', 'madeira_painel_n.jpg'),
        {'emissiveFactor': [1.0, 0.85, 0.70], 'emis': 'madeira_painel.jpg', 'strength': 0.45}),   # borda amadeirada (nao cinza)
    ('guarda_opaca', srgb('#434246'), 0.3, 0.45, None, {}),        # painel cinza da guarda
    ('fresta', srgb('#0e0e10'), 0.0, 0.95, None, {}),              # recorte escuro da escada
    ('aleta', srgb('#2e2d31'), 0.1, 0.7, None, {}),                # aleta macica entre studios
    ('madeira_painel', [1, 1, 1, 1], 0.0, 0.85, tex('madeira_painel.jpg', 'madeira_painel_n.jpg'), {}),
    # torre da escada e nucleo: pedra preta em filetes (render do terreo de perto, 14/10/2026)
    ('torre_escada', [1, 1, 1, 1], 0.0, 0.72, tex('pedra_preta.jpg', 'pedra_preta_n.jpg'), {}),
    # fim de corredor visto pelo vidro (Render 3): fundo e laterais apagados, cinza claro fosco
    ('corredor_fundo', srgb('#55545a'), 0.0, 0.8, None, {}),
    # moldura das paredes de madeira: cinza medio de metal (Render 1 #504e52 sob ceu nublado;
    # no Render 3 ela pega o ceu do entardecer)
    ('moldura_metal', srgb('#46474b'), 0.3, 0.55, None, {}),       # metal chumbo escuro FOSCO (pedidos do usuario: o preto ficava pesado; 14/10 fosco)
    # fundo do corredor aceso (Render 3: luz quente vista pelo vidro da parede leste)
    ('corredor_aceso', srgb('#3a3632'), 0.0, 0.8, None, {'emissiveFactor': [1.0, 0.78, 0.55], 'emis': 'interior.jpg', 'strength': 0.8}),
    # vidro transparente da janela e da faixa do corredor
    ('vidro_claro', srgb('#8d8c90', 0.20), 0.3, 0.05, None, {'alphaMode': 'BLEND', 'doubleSided': True}),
    # fundo das janelas da torre da escada: preto fosco (com reflexo, o ceu claro apagava o vao)
    # correcao do usuario (15/10/2026): na torre de pedra NAO ha janela nem vidro — sao NICHOS.
    # Fundo do nicho em pedra escura fosca, sem reflexo; o recuo aparece pela sombra
    ('janela_escada', srgb('#111113'), 0.0, 0.97, None, {}),
    # praca de paralelepipedo molhado (pouca rugosidade: reflete as luzes) e placas do embasamento
    ('paralelepipedo', [0.55, 0.55, 0.55, 1], 0.0, 0.5, tex('paralelepipedo.jpg', 'paralelepipedo_n.jpg'), {}),   # escuro: casa com o chao do site na borda
    ('placa_pedra', [1, 1, 1, 1], 0.0, 0.8, tex('placa_pedra.jpg'), {}),
    # deque e piscinas: marmore preto molhado, veios claros, tom uniforme (render da quina)
    ('marmore_preto', [1, 1, 1, 1], 0.1, 0.22, tex('marmore_preto.jpg'), {}),
    # parede de pedra do lounge, lavada por luz quente (vista pelo vidro)
    ('lounge_parede', [1, 1, 1, 1], 0.0, 0.9, tex('lounge_parede.jpg'),
        {'emissiveFactor': [1.0, 0.66, 0.40], 'emis': 'lounge_parede.jpg', 'strength': 0.07}),   # 16/10/2026: era 0,42 (estourava em branco)
    # mobiliario do lounge e da area externa (vistos de longe: formas simples)
    ('movel_claro', srgb('#7a6650'), 0.0, 0.85, None, {'emissiveFactor': [1.0, 0.7, 0.45], 'strength': 0.16}),
    ('movel_escuro', srgb('#1f1e1c'), 0.1, 0.7, None, {}),
    # folhagem: so contraste de luz — tom neutro quase preto (paleta da marca: nada de verde)
    # folhagem mais viva (usuario, 16/10/2026): cinza-oliva quente claro (sem verde: regra da marca) e um brilho
    # quente de luminaria de piso por baixo
    ('folhagem', srgb('#403d2f'), 0.0, 0.8, None, {'doubleSided': True, 'emissiveFactor': [0.30, 0.20, 0.09], 'strength': 0.07}),
    ('cesto_rattan', srgb('#9a8466'), 0.0, 0.9, None, {}),
    # entrada (Renders 6, 7 e 10, 15/10/2026): borda da marquise em placas grandes cinza-claro
    # (composto de aluminio), revestimento de tabuas cinza envelhecidas, monolito de pedra
    # rustica escura, lavagem de luz da fita de LED e tapete do lounge
    ('painel_acm', srgb('#4a4850'), 0.3, 0.5, None, {}),   # borda da marquise: grafite medio (R10 #42404d)
    ('ripado_cinza', [1, 1, 1, 1], 0.0, 0.8, tex('ripado_cinza.jpg', 'ripado_cinza_n.jpg'), {}),
    ('monolito', [1, 1, 1, 1], 0.0, 0.92, tex('monolito.jpg', 'monolito_n.jpg'), {}),
    ('lavagem_luz', [0, 0, 0, 1], 0.0, 1.0, None,
        {'emissiveFactor': [1.0, 0.84, 0.62], 'emis': 'lavagem.png', 'strength': 0.55, 'alphaMode': 'BLEND', 'alpha_img': 'lavagem.png'}),
    ('tapete', srgb('#3b3733'), 0.0, 0.95, None, {}),
]


class Mesh:
    def __init__(self):
        self.prims = {}

    def _p(self, mat):
        return self.prims.setdefault(mat, ([], [], [], []))

    def add(self, mat, verts, norms, uvs, tris):
        pos, nrm, uv, idx = self._p(mat)
        i0 = len(pos)
        V = [np.array(v, float) for v in verts]; Nn = [np.array(n, float) for n in norms]
        pos.extend(verts); nrm.extend(norms); uv.extend(uvs)
        for k in range(0, len(tris), 3):
            a, b, c = tris[k], tris[k + 1], tris[k + 2]
            fn = np.cross(V[b] - V[a], V[c] - V[a])
            if np.dot(fn, Nn[a] + Nn[b] + Nn[c]) < 0:
                b, c = c, b
            idx.extend((i0 + a, i0 + b, i0 + c))

    def quad(self, mat, a, b, c, d, hint, uv=None):
        a, b, c, d = (np.array(v, float) for v in (a, b, c, d))
        n = np.cross(b - a, d - a)
        flip = np.dot(n, hint) < 0
        if flip:
            b, d = d, b; n = -n
        ln = np.linalg.norm(n)
        if ln < 1e-9:
            return
        n = n / ln
        if uv is None:
            uv = [(0, 0), (1, 0), (1, 1), (0, 1)]
        elif flip:
            uv = [uv[0], uv[3], uv[2], uv[1]]
        self.add(mat, [a, b, c, d], [n] * 4, uv, [0, 1, 2, 0, 2, 3])

    def box(self, mat, lo, hi, uvscale=1.0):
        x0, y0, z0 = lo; x1, y1, z1 = hi
        sx, sy, sz = (x1 - x0) * uvscale, (y1 - y0) * uvscale, (z1 - z0) * uvscale
        self.quad(mat, (x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1), (0, 1, 0), [(0, 0), (sx, 0), (sx, sz), (0, sz)])
        self.quad(mat, (x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1), (0, -1, 0), [(0, 0), (sx, 0), (sx, sz), (0, sz)])
        self.quad(mat, (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (0, 0, -1), [(0, 0), (sx, 0), (sx, sy), (0, sy)])
        self.quad(mat, (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1), (0, 0, 1), [(0, 0), (sx, 0), (sx, sy), (0, sy)])
        self.quad(mat, (x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0), (-1, 0, 0), [(0, 0), (sz, 0), (sz, sy), (0, sy)])
        self.quad(mat, (x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0), (1, 0, 0), [(0, 0), (sz, 0), (sz, sy), (0, sy)])

    def prism(self, mat, poly, y0, y1, uvscale=0.25, top=True, bottom=True, side_mat=None, pular=()):
        """poly no sentido horario visto de cima -> normais externas = (dz, -dx)."""
        n = len(poly)
        tris = ear_clip(poly)
        pts_t = [(p[0], y1, p[1]) for p in poly]; pts_b = [(p[0], y0, p[1]) for p in poly]
        uvp = [(p[0] * uvscale, p[1] * uvscale) for p in poly]
        if top:
            self.add(mat, pts_t, [(0, 1, 0)] * n, uvp, [i for t in tris for i in t])
        if bottom:
            self.add(mat, pts_b, [(0, -1, 0)] * n, uvp, [i for t in tris for i in reversed(t)])
        u = 0.0
        for i in range(n):
            a, b = poly[i], poly[(i + 1) % n]
            dx, dz = b[0] - a[0], b[1] - a[1]
            L = math.hypot(dx, dz)
            nn = (dz / L, 0, -dx / L)
            if i in pular:
                u += L * uvscale; continue
            self.quad(side_mat if side_mat is not None else mat,
                      (a[0], y0, a[1]), (b[0], y0, b[1]), (b[0], y1, b[1]), (a[0], y1, a[1]), nn,
                      [(u, 0), (u + L * uvscale, 0), (u + L * uvscale, (y1 - y0) * uvscale), (u, (y1 - y0) * uvscale)])
            u += L * uvscale


def ear_clip(poly):
    n = len(poly); idx = list(range(n))
    area = sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1] for i in range(n))
    if area < 0:
        idx.reverse()
    cross = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    inside = lambda p, a, b, c: cross(a, b, p) >= 0 and cross(b, c, p) >= 0 and cross(c, a, p) >= 0
    out = []; guard = 0
    while len(idx) > 3 and guard < 10000:
        guard += 1
        for k in range(len(idx)):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            a, b, c = poly[i0], poly[i1], poly[i2]
            if cross(a, b, c) <= 1e-12:
                continue
            if any(inside(poly[j], a, b, c) for j in idx if j not in (i0, i1, i2)):
                continue
            out.append((i0, i1, i2)); idx.pop(k); break
        else:
            break
    out.append(tuple(idx))
    # orientacao para cima (y) com poly horario em (x,z): normal (0,1,0) exige CCW visto de +y
    fixed = []
    for t in out:
        a, b, c = poly[t[0]], poly[t[1]], poly[t[2]]
        # em coordenadas (x,z) com y para cima, visto de cima o eixo z aponta para baixo da tela
        if cross(a, b, c) > 0:   # horario em (x,z) == CCW visto de +y
            fixed.append(t)
        else:
            fixed.append((t[0], t[2], t[1]))
    return fixed


def along(face, t):
    p0, p1 = FACES[face]['p']
    return np.array([p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t])


def face_len(face):
    p0, p1 = FACES[face]['p']
    return math.hypot(p1[0] - p0[0], p1[1] - p0[1])


def depth(face, t, floor):
    """profundidade da sacada (m) na fracao t da face, neste pavimento."""
    t0, t1 = FACES[face]['sac']
    s = (t - t0) / (t1 - t0)
    # Render 1 no mesmo angulo: a faixa e quase reta, com barriga leve que muda
    # pouco de um andar para o outro (a v2 exagerava a onda)
    # curva diferente a cada pavimento (texto do conceito), mas pouca: +-0,15 m em volta da medida
    amp = BARRIGA[face] + 0.15 * math.sin(0.72 * floor + PHASE[face])
    return 1.7 + amp * math.sin(math.pi * s) + 0.05 * math.sin(2 * math.pi * s + 0.9 * floor)


def _faixa(mesh, mat, pts, nrms, ya, yb, u_escala=1 / 3.0, v1=1.0):
    """faixa vertical ao longo de uma polilinha (normais suaves), de ya a yb."""
    verts, norms, uvs, tris = [], [], [], []
    u = 0.0
    for k, q in enumerate(pts):
        if k:
            u += float(np.linalg.norm(pts[k] - pts[k - 1])) * u_escala
        verts += [(q[0], ya, q[1]), (q[0], yb, q[1])]; norms += [nrms[k], nrms[k]]; uvs += [(u, 0), (u, v1)]
    for k in range(len(pts) - 1):
        i = 2 * k
        tris += [i, i + 2, i + 3, i, i + 3, i + 1]
    mesh.add(mat, verts, norms, uvs, tris)


def balcony_band(mesh, face, floor, y_slab, cobertura=False):
    """sacadas de um pavimento numa face, como no Render 1 (recortes ampliados, 14/10):
    laje com borda fina e clara; forro de madeira quente; guarda de 1 m alternando painel
    cinza opaco e vidro, com montantes escuros; aleta escura macica do piso ao teto entre
    um studio e outro. A fita de LED fica na malha de cada studio (acende ao escolher)."""
    t0, t1 = FACES[face]['sac']
    n = np.array(FACES[face]['n'], float)
    n_st = FACES[face]['n_st']
    SEG = 8                                        # segmentos por studio (2 por painel da guarda)
    N = SEG * n_st
    V = lambda q, y: (q[0], y, q[1])
    ts = [t0 + (t1 - t0) * k / N for k in range(N + 1)]
    pw = [along(face, t) for t in ts]
    po = [pw[k] + n * depth(face, ts[k], floor) for k in range(N + 1)]
    nrm = []
    for k in range(N + 1):
        a = po[max(0, k - 1)]; b = po[min(N, k + 1)]
        tg = b - a; nn = np.array([tg[1], -tg[0]])
        if np.dot(nn, n) < 0:
            nn = -nn
        nn /= np.linalg.norm(nn); nrm.append((nn[0], 0, nn[1]))
    esp = 0.26                                     # espessura da laje na borda
    ytop, ybot = y_slab, y_slab - esp
    acum = [0.0]
    for k in range(N):
        acum.append(acum[-1] + float(np.linalg.norm(pw[k + 1] - pw[k])))
    for k in range(N):
        w0, w1, o0, o1 = pw[k], pw[k + 1], po[k], po[k + 1]
        # tabuas no sentido da curva (u = comprimento acumulado, v = profundidade), ladrilho 3,6 m
        u0, u1 = acum[k] / 3.6, acum[k + 1] / 3.6
        d0, d1 = float(np.linalg.norm(o0 - w0)) / 3.6, float(np.linalg.norm(o1 - w1)) / 3.6
        # piso da sacada na MESMA madeira do forro (correcao do usuario: estava cinza); o beiral
        # da cobertura segue em concreto
        if cobertura:
            mesh.quad(M_LAJE, V(w0, ytop), V(w1, ytop), V(o1, ytop), V(o0, ytop), (0, 1, 0))
        else:
            mesh.quad(M_MADEIRA, V(w0, ytop), V(w1, ytop), V(o1, ytop), V(o0, ytop), (0, 1, 0),
                      [(u0, 0), (u1, 0), (u1, d1), (u0, d0)])
        # forro de madeira, veio ao longo da fachada
        mesh.quad(M_MADEIRA, V(w0, ybot), V(w1, ybot), V(o1, ybot), V(o0, ybot), (0, -1, 0),
                  [(u0, 0), (u1, 0), (u1, d1), (u0, d0)])
    _faixa(mesh, M_BORDA, po, nrm, ybot, ytop + 0.02, u_escala=1 / 3.6, v1=(ytop + 0.02 - ybot) / 3.6)   # borda amadeirada
    if cobertura:
        # beiral da cobertura: forro e borda como as sacadas e, em cima, a platibanda escura
        # que acompanha a curva (Render 1). Sem ele as fitas de LED do ultimo andar ficam no ar
        _faixa(mesh, M_PAREDE, po, nrm, ytop + 0.02, ytop + 1.0)
        pin = [po[k] - np.array(nrm[k])[[0, 2]] * 0.15 for k in range(N + 1)]
        _faixa(mesh, M_PAREDE, pin, [(-a, 0, -c) for a, _, c in nrm], ytop, ytop + 1.0)
        for k in range(N):
            mesh.quad(M_PAREDE, V(pin[k], ytop + 1.0), V(pin[k + 1], ytop + 1.0), V(po[k + 1], ytop + 1.0), V(po[k], ytop + 1.0), (0, 1, 0))
        return
    # guarda RETA (correcao do usuario, 15/10/2026): a laje e curva, mas o vidro e as divisorias
    # seguem uma linha reta paralela a fachada, na profundidade das pontas da sacada — de lado,
    # a borda curva avanca alem do vidro no meio da faixa. 1,05 m; 4 paineis por studio
    # correcao do usuario (15/10/2026): nas pontas so a laje de madeira sai ~30 cm alem do vidro
    DG = min(float(np.linalg.norm(po[k] - pw[k])) for k in range(N + 1)) - GUARDA_RECUO
    pg = [pw[k] + n * DG for k in range(N + 1)]
    ng = [(n[0], 0, n[1])] * (N + 1)
    yg0, yg1 = ytop + 0.02, ytop + 1.05
    for s in range(n_st):
        for pnl in range(4):
            a, b = s * SEG + pnl * 2, s * SEG + pnl * 2 + 2
            mat = M_VIDRO
            _faixa(mesh, mat, [pg[a], pg[b]], [ng[a], ng[b]], yg0, yg1)     # painel plano
            # montante escuro no inicio de cada painel: uma placa de 6 cm virada para fora
            q = pg[a] + n * 0.01
            tg = pg[a + 1] - pg[a]; tg = tg / (np.linalg.norm(tg) + 1e-9) * 0.03
            mesh.quad(M_ALETA, V(q - tg, yg0), V(q + tg, yg0), V(q + tg, yg1 + 0.02), V(q - tg, yg1 + 0.02), ng[a])
    _faixa(mesh, M_ALETA, [pg[0], pg[N]], [ng[0], ng[N]], yg1, yg1 + 0.04)   # corrimao reto
    # guarda em 8 quadros por studio — 4 em cima e 4 embaixo (Render 4 de perto, correcao do
    # usuario em 15/10/2026): travessa na meia altura, 1 cm para fora do vidro
    ym = (yg0 + yg1) / 2
    _faixa(mesh, M_ALETA, [pg[0] + n * 0.012, pg[N] + n * 0.012], [ng[0], ng[N]], ym - 0.018, ym + 0.018)
    # aletas escuras entre studios (e nas duas pontas da faixa), piso ao teto. Renders 1 e 8
    # de perto + correcoes do usuario (14 e 15/10/2026): RETAS e RECUADAS — saem da parede e
    # param na linha reta do vidro; a borda curva da laje passa inteira na frente
    tang = np.array([-n[1], n[0]])
    for s in range(n_st + 1):
        kk = s * SEG
        w = pw[kk]; D = float(np.linalg.norm(po[kk] - pw[kk]))
        ponta = s in (0, n_st)
        e = 0.08 if ponta else 0.06
        ya, yb = ytop, ytop + PE - esp
        # as das pontas da faixa vao ate a borda: fecham a lateral da sacada (sem vao para o escuro)
        # divisorias retas ate a linha do vidro (as das pontas vao ate a borda e fecham a lateral)
        cima = baixo = w + n * (D if ponta else DG)
        if ponta:
            fora = pw[kk] - pw[1 if s == 0 else N - 1]; fora = fora / np.linalg.norm(fora)
            mesh.quad(M_LAJE, V(w, ybot), V(po[kk], ybot), V(po[kk], ytop), V(w, ytop), (fora[0], 0, fora[1]))
        # a ponta oeste encosta no painel de madeira: ali nao ha aleta (correcao do usuario em
        # 14/10/2026 — as placas escuras empilhadas ao lado do painel nao existem)
        if ponta and face == 'oeste' and s == n_st:
            continue
        for sg in (-1, 1):
            a_, c_, b_ = w + tang * e * sg, cima + tang * e * sg, baixo + tang * e * sg
            mesh.quad(M_ALETA, V(a_, ya), V(b_, ya), V(c_, yb), V(a_, yb), (tang[0] * sg, 0, tang[1] * sg))
        b0, b1 = baixo - tang * e, baixo + tang * e; c0, c1 = cima - tang * e, cima + tang * e
        mesh.quad(M_ALETA, V(b0, ya), V(b1, ya), V(c1, yb), V(c0, yb), (n[0], 0, n[1]))


def unit_meshes():
    """30 malhas (uma por studio), y relativo ao topo da laje do pavimento. Conferido nos
    Renders 1 e 3 (14/10/2026): cortina clara acesa na parede e o vidro transparente 30 cm a
    frente (da profundidade), caixilho escuro de 4 folhas com travessa alta, e UM spot por
    vao no forro da sacada de cima. Cortina e spot sao o que acende ao escolher o studio."""
    out = {}
    for face, f in FACES.items():
        if not f['sac']:
            continue
        t0, t1 = f['sac']; n = np.array(f['n'], float); tang = np.array([-n[1], n[0]])
        n_st, s0, inv = f['n_st'], f['s0'], f['inv']
        V = lambda q, y: (q[0], y, q[1])
        for j in range(n_st):
            tc = t0 + (t1 - t0) * (j + 0.5) / n_st
            k = (s0 - j) if inv else (s0 + j)
            w = along(face, tc)
            half = face_len(face) * (t1 - t0) / n_st / 2 - 0.25
            m = Mesh()
            a0, b0 = w - tang * half, w + tang * half
            yj0, yj1 = 0.05, PE - 0.36
            nn = (n[0], 0, n[1])
            ca, cb = a0 + n * 0.03, b0 + n * 0.03                 # cortina
            ga, gb = a0 + n * 0.30, b0 + n * 0.30                 # vidro
            m.quad(M_JANELA, V(ca, yj0), V(cb, yj0), V(cb, yj1), V(ca, yj1), nn)
            m.quad(M_VIDRO_JANELA, V(ga, yj0), V(gb, yj0), V(gb, yj1), V(ga, yj1), nn)
            # requadro entre a cortina e o vidro: laterais e verga
            m.quad(M_ALETA, V(ca, yj0), V(ga, yj0), V(ga, yj1), V(ca, yj1), (tang[0], 0, tang[1]))
            m.quad(M_ALETA, V(cb, yj0), V(gb, yj0), V(gb, yj1), V(cb, yj1), (-tang[0], 0, -tang[1]))
            m.quad(M_ALETA, V(ca, yj1), V(cb, yj1), V(gb, yj1), V(ga, yj1), (0, -1, 0))
            # porta de vidro de DUAS folhas, fechada, com o encontro no meio (correcao do usuario em
            # 15/10/2026: os 8 quadros sao da guarda da sacada, nao da porta) — so os montantes das
            # pontas e o do meio, mais grosso, sem travessa
            lo_ = lambda p, q: tuple(np.minimum(p, q)); hi_ = lambda p, q: tuple(np.maximum(p, q))
            for tt in (0.0, 0.5, 1.0):
                c = ga + (gb - ga) * tt; e_ = 0.05 if tt == 0.5 else 0.035
                p0 = np.array([c[0] - e_, yj0, c[1] - e_]) - np.array([n[0], 0, n[1]]) * 0.03
                p1 = np.array([c[0] + e_, yj1, c[1] + e_]) + np.array([n[0], 0, n[1]]) * 0.03
                m.box(M_ALETA, lo_(p0, p1), hi_(p0, p1))
            # spot: um por vao, no meio, ~1 m da parede, rente ao forro da sacada de cima
            c = w + n * 1.0; ya = PE - 0.265; r = 0.09
            pts = [(c[0], ya, c[1])] + [(c[0] + r * math.cos(t), ya, c[1] + r * math.sin(t))
                                       for t in np.linspace(0, 2 * math.pi, 9)[:-1]]
            m.add(M_LUZ, pts, [(0, -1, 0)] * 9, [(0.5, 0.5)] * 9,
                  [x for q in range(8) for x in (0, 1 + q, 1 + (q + 1) % 8)])
            out[k] = (m, face)
    return out


def logo_quad(mesh, origin, nn, width, height, mat=None):
    """letreiro: origem no canto inferior esquerdo visto de frente (normal nn), u cresce para a direita."""
    nn = np.array(nn, float); up = np.array([0, 1, 0]); right = np.cross(up, nn)
    o = np.array(origin, float); a = o; b = o + right * width; c = b + up * height; d = o + up * height
    mesh.add(M_LOGO if mat is None else mat, [tuple(a), tuple(b), tuple(c), tuple(d)], [tuple(nn)] * 4, [(0, 1), (1, 1), (1, 0), (0, 0)], [0, 1, 2, 0, 2, 3])


# bordas das paredes de topo (14/10/2026). Medidas no Render 1 (pontas B e F e a quina do
# painel, retroprojetadas com a camera calibrada) e no Render 3 (parede leste de frente): nos
# tres casos a borda sobe reta ate ~20 m e dali se abre para fora numa curva ~u^1,6, de 1,9 a
# 3,2 m a mais no topo (media ~2,5 m). AJUSTAR quando vier corte/fachada cotada.
CURVA_Y0, CURVA_P = 20.0, 1.6


def abertura(y, amp):
    u = max(0.0, (y - CURVA_Y0) / (Y_ROOF - CURVA_Y0))
    return amp * u ** CURVA_P


def _q(mesh, mat, pts, nrm, uvs=None):
    """quad com a normal dada (aceita aresta degenerada: a ponta do painel)."""
    mesh.add(mat, [tuple(p) for p in pts], [tuple(nrm)] * 4, uvs or [(0, 0), (1, 0), (1, 1), (0, 1)], [0, 1, 2, 0, 2, 3])


def _linhas(yb, y_in, y_out, borda, interna, lado):
    """linhas (y, a, b) de um painel: borda(y) e a borda externa curva, 'interna' a reta junto
    ao vidro; acima de y_in o topo sobe em linha reta da interna ate a ponta externa.
    lado -1: a borda externa e a (s menor); +1: e b."""
    ys = list(np.linspace(yb, y_in, 24)) + (list(np.linspace(y_in, y_out, 5)[1:]) if y_out > y_in else [])
    ponta = borda(y_out)
    out = []
    for y in ys:
        ext = borda(y)
        inn = interna if y <= y_in + 1e-9 or y_out <= y_in else interna + (y - y_in) / (y_out - y_in) * (ponta - interna)
        out.append((y, ext, inn) if lado < 0 else (y, inn, ext))
    return out


def painel_curvo(mesh, o, ds, n, rows, wf, wb, costas=None, m=0.3, lat_ext=None, lat_int=None, moldura_ext=True):
    """painel de madeira em ripas verticais com contorno curvo, moldura de metal na face e
    espessura em metal. Ponto = o + s*ds + y*up + w*n (n para fora da fachada).
    rows: [(y, a, b)] de baixo para cima, a <= b; a ultima pode ter a == b (a ponta).
    costas(a, b) -> (a', b'): trecho em que o verso fica a vista (o que avanca alem da ala)."""
    o, ds, n = (np.array(v, float) for v in (o, ds, n)); up = np.array([0.0, 1.0, 0.0])
    P = lambda s, y, w: o + ds * s + up * y + n * w
    uv = lambda s, y: (y / 3.6, s / 3.6)          # ladrilho 3,6 x 3,6 m com 8 tabuas de 0,45 m
    for (y0, a0, b0), (y1, a1, b1) in zip(rows, rows[1:]):
        _q(mesh, M_PAINEL, [P(a0, y0, wf), P(b0, y0, wf), P(b1, y1, wf), P(a1, y1, wf)], n,
           [uv(a0, y0), uv(b0, y0), uv(b1, y1), uv(a1, y1)])
        if costas:
            (c0, d0), (c1, d1) = costas(a0, b0), costas(a1, b1)
            if d0 - c0 > 1e-3 or d1 - c1 > 1e-3:
                _q(mesh, M_PAINEL, [P(c0, y0, wb), P(d0, y0, wb), P(d1, y1, wb), P(c1, y1, wb)], -n,
                   [uv(c0, y0), uv(d0, y0), uv(d1, y1), uv(c1, y1)])
    # contorno sem o pe: sobe pela borda a e desce pela b (horario no plano s-y: o painel fica a direita)
    cont = [np.array((a, y)) for y, a, _ in rows] + [np.array((b, y)) for y, _, b in reversed(rows)]
    nA = len(rows) - 1                                 # os primeiros nA trechos correm pela borda 'a'
    for k_, (p, q) in enumerate(zip(cont, cont[1:])):
        d = q - p; L = float(np.linalg.norm(d))
        if L < 1e-6:
            continue
        lado = 'ext' if k_ < nA else ('int' if abs(p[0] - q[0]) < 1e-6 else 'topo')
        d /= L; den = np.array([d[1], -d[0]])
        fora = -(ds * den[0] + up * den[1])
        mat_lat = (lat_ext if lado == 'ext' else lat_int if lado == 'int' else None) or M_MOLDURA
        uvl = [(p[1] / 3.6, wf / 3.6), (q[1] / 3.6, wf / 3.6), (q[1] / 3.6, wb / 3.6), (p[1] / 3.6, wb / 3.6)]
        _q(mesh, mat_lat, [P(p[0], p[1], wf), P(q[0], q[1], wf), P(q[0], q[1], wb), P(p[0], p[1], wb)], fora, uvl)
        if lado == 'ext' and not moldura_ext:
            continue
        p2, q2 = p + den * m, q + den * m
        _q(mesh, M_MOLDURA, [P(p[0], p[1], wf + 0.02), P(q[0], q[1], wf + 0.02),
                             P(q2[0], q2[1], wf + 0.02), P(p2[0], p2[1], wf + 0.02)], n)


def faixa_vidro(mesh, o, ds, n, sa, sb, w, y_vidro, y_tampa, acesos, mat_tampa=None, fundo=1.1, spots=False,
                lateral=None, w_lat=None):
    """fim do corredor visto pelo vidro (Render 3): pano transparente com travessa a cada meio
    andar e, a 'fundo' m para dentro, o corredor — parede do fundo acesa ou apagada, laje e
    forro de cada andar e as duas laterais. No alto, uma tampa macica (a 'parte preta' do
    Render 1 na fenda da escada; cinza de moldura na parede leste do Render 3)."""
    o, ds, n = (np.array(v, float) for v in (o, ds, n)); up = np.array([0.0, 1.0, 0.0])
    P = lambda s, y, ww: o + ds * s + up * y + n * ww
    wd = w - fundo
    for k in range(PAV_TIPO):
        y0 = TERREO_H + k * PE
        if y0 >= y_vidro:
            break
        y1 = min(y0 + PE, y_vidro)
        _q(mesh, M_CORR_ACESO if acesos(k) else M_CORR_FUNDO,
           [P(sa, y0, wd), P(sb, y0, wd), P(sb, y1, wd), P(sa, y1, wd)], n, [(0, 1), (1, 1), (1, 0), (0, 0)])
        # piso, forro e testeira da laje, vistos pelo vidro
        _q(mesh, M_PAREDE, [P(sa, y0, w - 0.02), P(sb, y0, w - 0.02), P(sb, y0, wd), P(sa, y0, wd)], up)
        if y1 - y0 > 0.5:
            _q(mesh, M_CORR_FUNDO, [P(sa, y1 - 0.25, w - 0.02), P(sb, y1 - 0.25, w - 0.02), P(sb, y1 - 0.25, wd), P(sa, y1 - 0.25, wd)], -up)
        _q(mesh, M_PAREDE, [P(sa, y0 - 0.25, w - 0.03), P(sb, y0 - 0.25, w - 0.03), P(sb, y0, w - 0.03), P(sa, y0, w - 0.03)], n)
        if spots and y1 - y0 > 0.5:                      # um spot no teto de cada andar (render da quina)
            c = P((sa + sb) / 2, y1 - 0.27, w - fundo / 2); r_ = 0.09
            pts = [tuple(c)] + [tuple(c + ds * r_ * math.cos(t) + n * r_ * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 9)[:-1]]
            mesh.add(M_LUZ, pts, [(0, -1, 0)] * 9, [(0.5, 0.5)] * 9, [x for q in range(8) for x in (0, 1 + q, 1 + (q + 1) % 8)])
        for h in range(2):
            ya = y0 + h * PE / 2
            if ya >= y_vidro:
                break
            _q(mesh, M_PAREDE, [P(sa, ya - 0.04, w + 0.02), P(sb, ya - 0.04, w + 0.02),
                                P(sb, ya + 0.04, w + 0.02), P(sa, ya + 0.04, w + 0.02)], n)
    wl = w if w_lat is None else w_lat
    for s_, nn in ((sa + 0.01, ds), (sb - 0.01, -ds)):     # laterais do corredor (1 cm para dentro do caixilho)
        if lateral is None:
            _q(mesh, M_CORR_FUNDO, [P(s_, TERREO_H, w), P(s_, TERREO_H, wd), P(s_, y_vidro, wd), P(s_, y_vidro, w)], nn)
        else:
            dw, hh = abs(wl - wd) / 2, (y_vidro - TERREO_H) / 2        # pedra: ladrilho de 2 m
            _q(mesh, lateral, [P(s_, TERREO_H, wl), P(s_, TERREO_H, wd), P(s_, y_vidro, wd), P(s_, y_vidro, wl)], nn,
               [(0, 0), (dw, 0), (dw, hh), (0, hh)])
    _q(mesh, M_VIDRO_JANELA, [P(sa, TERREO_H, w), P(sb, TERREO_H, w), P(sb, y_vidro, w), P(sa, y_vidro, w)], n)
    if y_tampa:
        # tampa fechada (caixa): ninguem enxerga o oco do predio por cima dela
        c0, c1 = P(sa, y_vidro, wd), P(sb, y_tampa, w + 0.11)
        mesh.box(mat_tampa, tuple(np.minimum(c0, c1)), tuple(np.maximum(c0, c1)))


def torre_com_janelas(mesh, ta, tb, zt, zb, yt, furos, prof=0.32):
    """torre da escada em pedra preta com as janelas FUNDAS na face da frente (z = zt): uma por
    andar, todas alinhadas; os renders de perto mostram janelas com requadro de pedra e vidro
    escuro no fundo (largura e posicao vem de quem chama)."""
    uv = lambda a, b: (a * 0.5, b * 0.5)                  # ladrilho da pedra: 2 x 2 m
    def frente(x0, x1, y0, y1):
        if y1 - y0 > 1e-6 and x1 - x0 > 1e-6:
            mesh.quad(M_TORRE, (x0, y0, zt), (x1, y0, zt), (x1, y1, zt), (x0, y1, zt), (0, 0, -1),
                      [uv(x0, y0), uv(x1, y0), uv(x1, y1), uv(x0, y1)])
    y = 0.0; zi = zt + prof
    for xa, xb, ya, yb in sorted(furos, key=lambda f: f[2]):
        frente(ta, tb, y, ya); frente(ta, xa, ya, yb); frente(xb, tb, ya, yb)
        mesh.quad(M_TORRE, (xa, yb, zt), (xb, yb, zt), (xb, yb, zi), (xa, yb, zi), (0, -1, 0), [uv(xa, zt), uv(xb, zt), uv(xb, zi), uv(xa, zi)])
        mesh.quad(M_TORRE, (xa, ya, zt), (xb, ya, zt), (xb, ya, zi), (xa, ya, zi), (0, 1, 0), [uv(xa, zt), uv(xb, zt), uv(xb, zi), uv(xa, zi)])
        mesh.quad(M_TORRE, (xa, ya, zt), (xa, yb, zt), (xa, yb, zi), (xa, ya, zi), (1, 0, 0), [uv(zt, ya), uv(zt, yb), uv(zi, yb), uv(zi, ya)])
        mesh.quad(M_TORRE, (xb, ya, zt), (xb, yb, zt), (xb, yb, zi), (xb, ya, zi), (-1, 0, 0), [uv(zt, ya), uv(zt, yb), uv(zi, yb), uv(zi, ya)])
        mesh.quad(M_JANELA_ESC, (xa, ya, zi), (xb, ya, zi), (xb, yb, zi), (xa, yb, zi), (0, 0, -1))
        y = yb
    frente(ta, tb, y, yt)
    for x, nx in ((ta, -1), (tb, 1)):
        mesh.quad(M_TORRE, (x, 0, zt), (x, 0, zb), (x, yt, zb), (x, yt, zt), (nx, 0, 0), [uv(zt, 0), uv(zb, 0), uv(zb, yt), uv(zt, yt)])
    mesh.quad(M_TORRE, (ta, 0, zb), (tb, 0, zb), (tb, yt, zb), (ta, yt, zb), (0, 0, 1), [uv(ta, 0), uv(tb, 0), uv(tb, yt), uv(ta, yt)])
    mesh.quad(M_TORRE, (ta, yt, zt), (tb, yt, zt), (tb, yt, zb), (ta, yt, zb), (0, 1, 0), [uv(ta, zt), uv(tb, zt), uv(tb, zb), uv(ta, zb)])


def nucleo_noroeste(mesh):
    """quina noroeste (A), conferida em recortes ampliados do Render 1 (14/10/2026).
    Na face da ala 17-30, de fora para dentro:
      - parede de topo do Studio 01 em ripas verticais de madeira (#5e473f) com moldura
        de metal; a borda da quina sobe reta e se abre para fora na curva medida, ate a
        ponta no alto; o topo desce em linha reta ate a fenda; letreiro no pe;
      - fenda de vidro cinza do fim do corredor, quase rente a madeira, com travessas e
        uma tampa escura no alto;
      - torre da escada em pedra preta com uma janela funda por andar, todas alinhadas
        (~40% da face, do lado da ala 17-30); acima da cobertura ela sobe em degraus."""
    V = lambda x, y, z: (x, y, z)
    # correcao do usuario: embaixo o vidro e as divisorias da fachada oeste acompanham a borda do
    # painel ("ponta com ponta") e so a ponta de madeira da laje passa ~30 cm; no alto o painel
    # se abre e passa das sacadas. A borda fica na linha do vidro: 1,7 m da sacada na ponta,
    # menos a variacao de 5 cm, menos o recuo da guarda
    x0, x1 = X_PAINEL0, X(440)
    # topo medido no Render 1 (retroprojetado): +1,2 m junto a fenda, ponta +2,3 m. AJUSTAR
    # correcao do usuario (15/10/2026): o topo do painel de madeira e RETO, na horizontal
    yb, y_in, y_out = TERREO_H - 0.1, Y_ROOF + 2.3, Y_ROOF + 2.3
    linhas = _linhas(yb, y_in, y_out, lambda y: x0 - abertura(y, 2.2), x1, -1)
    # a madeira avanca 1,1 m da fachada norte (w = -z); o verso fica a vista so a oeste da quina
    # painel como placa FINA (0,35 m) de cima a baixo — correcao do usuario: a lateral estava
    # grossa (1,5 m) e aparecia como um bloco preto ao lado do painel
    # o painel vai ate a parede (verso em z = 0); a borda de fora volta com as placas de metal
    # chumbo fosco (correcao do usuario em 14/10/2026: o que sobrava eram as aletas da 1a sacada
    # oeste, ja removidas em balcony_band). A lateral da fenda e pedra
    painel_curvo(mesh, (0, 0, 0), (1, 0, 0), (0, 0, -1), linhas, 1.1, 0.0,
                 costas=lambda a, b: (min(a, 0.0), min(b, 0.0)), m=0.5,
                 lat_int=M_TORRE)
    zf = -1.1
    # render da quina no nivel da rua: a madeira termina numa faixa grossa de metal preto e as
    # laterais da moldura descem como pilares pretos ate o deque, emoldurando o lounge de vidro
    mesh.box(M_MOLDURA, (x0, TERREO_H - 1.1, zf - 0.02), (x1, yb, -0.4))
    for xa_, xb_ in ((x0, x0 + 0.5), (x1 - 0.5, x1)):
        mesh.box(M_MOLDURA, (xa_, 0.0, zf - 0.02), (xb_, TERREO_H - 1.1, -0.75))
    # letreiro ~70% da largura, ~1,5 andar acima do pe da madeira (Renders 2, 4, 5 e 9 conferidos
    # em 15/10/2026: estava a 1 m do pe, baixo demais)
    lw = 7.0; lh = lw * 487 / 2048
    logo_quad(mesh, (x0 + 0.5 + 1.0 + lw, yb + 3.9, zf - 0.04), (0, 0, -1), lw, lh)
    # fenda de vidro do corredor X(440)..X(490): no Render 1 ela aparece inteira, entao fica
    # quase rente a madeira (12 cm atras); so o pano do ultimo andar aceso
    fa, fb = X(440), X(490)
    # correcao do usuario: a janela tem PROFUNDIDADE entre a pedra e o painel de madeira (vidro
    # recuado ~0,55 m do plano do painel) e as laterais sao so pedra — sem cinza entre a janela e a pedra
    faixa_vidro(mesh, (0, 0, 0), (1, 0, 0), (0, 0, -1), fa, fb, 0.55, Y_ROOF - 1.1, None,
                acesos=lambda k: True, fundo=0.9, spots=True, lateral=M_TORRE, w_lat=0.75)
    # no pe da fenda, um beiral com forro de madeira sobre a entrada lateral (porta escura)
    mesh.box(M_MOLDURA, (fa - 0.3, TERREO_H - 1.1, -2.3), (fb + 0.6, TERREO_H - 0.8, -0.4))
    mesh.quad(M_MADEIRA, (fa - 0.3, TERREO_H - 1.11, -2.3), (fb + 0.6, TERREO_H - 1.11, -2.3), (fb + 0.6, TERREO_H - 1.11, -0.4), (fa - 0.3, TERREO_H - 1.11, -0.4), (0, -1, 0),
              [(0, 0), (1.2, 0), (1.2, 0.6), (0, 0.6)])
    mesh.quad(M_JANELA_ESC, (fa, 0.0, -0.46), (fb, 0.0, -0.46), (fb, TERREO_H - 1.1, -0.46), (fa, TERREO_H - 1.1, -0.46), (0, 0, -1))
    # torre da escada: X(490)..X(590), fundo ate Z(265), passa ~7,2 m da cobertura
    ta, tb, yt = X(490), X(590), Y_ROOF + 7.5   # AJUSTAR (casado com o recorte do topo do Render 1)
    zt = -2.2                                   # a torre avanca 2,2 m (1,1 m a frente do painel): laterais de pedra largas (correcao do usuario)
    # janelas da escada: CENTRALIZADAS na face (correcao do usuario), ~45% da largura, 0,6 m de
    # altura, todas alinhadas — um por andar
    w = tb - ta; xa, xb = ta + w * 0.275, ta + w * 0.725
    # Render 1 retroprojetado (14/10/2026): 17 janelas de ~0,5 m num passo unico de ~3,36 m, de
    # ~6,3 m a ~60,1 m (centro) — nao acompanham os andares (3,0 m); com o passo dos andares a
    # penultima ficava ~1 m alta demais (correcao do usuario)
    ys = [6.26 + k * (60.08 - 6.26) / 16 - 0.25 for k in range(17)]
    torre_com_janelas(mesh, ta, tb, zt, Z(265), yt, [(xa, xb, y, y + 0.5) for y in ys])
    # coroamento em degraus: sobre a fenda um volume escuro mais baixo (desce 1,1 m e tampa a
    # fenda: a parte preta no alto do vidro), e outro atras
    mesh.box(M_PAREDE, (fa - 0.1, Y_ROOF - 1.1, -1.0), (fb + 0.05, Y_ROOF + 4.6, Z(200)))
    mesh.box(M_PAREDE, (tb, Y_ROOF, Z(60)), (tb + 2.6, Y_ROOF + 1.6, Z(230)))


def parede_topo(mesh, face, amp, e0, logo=False):
    """parede de topo de uma ala (Render 3 = parede leste de frente; pontas B e F no Render 1):
    dois paineis de madeira com moldura de metal e, no meio, a faixa de vidro do fim do
    corredor com uma tampa no alto. As bordas externas passam e0 da fachada e se abrem
    na curva medida. O verso do que avanca tambem e de madeira: e ele que aparece nas pontas
    quando se olha a fachada de quina (Render 1) — por isso ali a madeira alarga para cima."""
    (ax, az), (bx, bz) = FACES[face]['p']; nx, nz = FACES[face]['n']
    L = math.hypot(bx - ax, bz - az)
    o = (ax, 0.0, az); ds = ((bx - ax) / L, 0.0, (bz - az) / L); n = (nx, 0.0, nz)
    wf, wb = 0.35, 0.02
    # Render 3 de perto (14/10/2026): topo dos paineis RETO na horizontal (a ponta e so a curva
    # da borda), moldura de metal de ~0,6 m em volta da madeira, vidro do corredor de ~1,6 m
    # entre duas molduras e uma tampa cinza ~0,75 m abaixo do topo
    yb, y_top = TERREO_H - 0.4, Y_ROOF + 1.4
    e = lambda y: e0 + abertura(y, amp)
    sa, sb = L / 2 - 0.8, L / 2 + 0.8
    m = 0.6
    painel_curvo(mesh, o, ds, n, _linhas(yb, y_top, y_top, lambda y: -e(y), sa, -1), wf, wb,
                 costas=lambda a, b: (min(a, 0.0), min(b, 0.0)), m=m)
    painel_curvo(mesh, o, ds, n, _linhas(yb, y_top, y_top, lambda y: L + e(y), sb, 1), wf, wb,
                 costas=lambda a, b: (max(a, L), max(b, L)), m=m)
    semente = len(face)
    faixa_vidro(mesh, o, ds, n, sa, sb, wf - 0.12, y_top - 0.75 - 1.1, y_top - 0.75,
                acesos=lambda k: (k * 7919 + semente * 31) % 7 < 4, mat_tampa=M_MOLDURA, fundo=1.2)
    if logo:
        # Render 3: letreiro ~7 m no alto do painel do lado de p0, 1,35 m abaixo do topo e
        # ~1,3 m para dentro da moldura da borda externa
        lw = 7.0; lh = lw * 487 / 2048; yl = y_top - 1.35
        assert np.dot(np.cross([0, 1, 0], n), ds) < 0   # visto de frente, o lado de p0 fica a direita
        s_org = -e(yl) + m + 1.3 + lw
        org = np.array(o) + np.array(ds) * s_org + np.array(n) * (wf + 0.04) + np.array([0, yl - lh, 0])
        logo_quad(mesh, tuple(org), n, lw, lh)


def paredes_topo(mesh):
    # medido no Render 1 (silhueta das pontas retroprojetada): embaixo a borda escura e o que
    # fica mais para fora (nenhuma sacada passa dela) e no topo chega a ~3,9 m (B) e ~3,0 m (F)
    # da fachada. Aqui as sacadas das pontas tem 1,7 m, entao a borda parte de 1,75 m
    parede_topo(mesh, 'leste_barra', amp=2.2, e0=1.75, logo=True)
    # a parede sul nao aparece em render: mesmo desenho da leste, letreiro no mesmo lugar —
    # e a MESMA curva (correcao do usuario em 15/10/2026: com 1,4 m ela parecia menos curva no alto)
    parede_topo(mesh, 'sul_haste', amp=2.2, e0=1.75, logo=True)


def roof(mesh):
    """laje de cobertura, platibanda subindo para as pontas, casa de maquinas."""
    mesh.prism(M_PAREDE, POLY, Y_ROOF - 0.25, Y_ROOF, top=True, bottom=False)
    n = len(POLY)
    for i in range(n):
        a, b = POLY[i], POLY[(i + 1) % n]
        face = list(FACES)[i]
        if FACES[face].get('vidro'):
            continue                                # faces do nucleo: sobem direto no prisma escuro
        dx, dz = b[0] - a[0], b[1] - a[1]; L = math.hypot(dx, dz)
        nn = np.array([dz / L, -dx / L])
        # platibanda baixa e reta: no Render 1 a cobertura nao sobe para as pontas
        ha = hb = Y_ROOF + 1.0
        for sgn, mat in ((1, M_PAREDE), (-1, M_PAREDE)):
            o = nn * 0.18 * sgn
            mesh.quad(mat, (a[0] + o[0], Y_ROOF, a[1] + o[1]), (b[0] + o[0], Y_ROOF, b[1] + o[1]),
                      (b[0] + o[0], hb, b[1] + o[1]), (a[0] + o[0], ha, a[1] + o[1]), (nn[0] * sgn, 0, nn[1] * sgn))
        o = nn * 0.18
        mesh.quad(M_PAREDE, (a[0] - o[0], ha, a[1] - o[1]), (b[0] - o[0], hb, b[1] - o[1]),
                  (b[0] + o[0], hb, b[1] + o[1]), (a[0] + o[0], ha, a[1] + o[1]), (0, 1, 0))
    # nucleo escuro sobre a cobertura: liga a torre da escada (quina noroeste) ao centro do L,
    # por cima do predio (Render 8: a faixa preta do canto interno passa da cobertura). AJUSTAR
    nucleo = [(X(490), Z(265)), (X(795), Z(265)), (X(795), Z(Y_HASTE0)), (X(490), Z(Y_HASTE0))]
    mesh.prism(M_TORRE, nucleo, Y_ROOF, Y_ROOF + 4.0, uvscale=0.5, bottom=False)


def podium(mesh):
    """terreo: pano de vidro quase alinhado com a torre em todas as faces (Render 1: vitrine
    iluminada sob as duas alas), montantes escuros, pavilhao envidracado alem da ponta B,
    marquise e letreiro. Posicao da entrada e do pavilhao: AJUSTAR."""
    inset = 0.4
    poly = []
    n = len(POLY)
    for i in range(n):
        p = np.array(POLY[i]); prev = np.array(POLY[i - 1]); nxt = np.array(POLY[(i + 1) % n])
        def nrm(a, b):
            d = b - a; d /= np.linalg.norm(d); return np.array([d[1], -d[0]])
        n1, n2 = nrm(prev, p), nrm(p, nxt)
        # esquadria em miter: vale para cantos convexos e reentrantes (o recorte do hall tem os dois)
        off = (n1 + n2) / (1.0 + float(np.dot(n1, n2)))
        poly.append(tuple(p - off * inset))
    y0, y1 = 0.0, TERREO_H
    # render da quina no nivel da rua: o terreo e vidro transparente com caixilho preto e o
    # lounge aceso por dentro. O interior e um prisma fechado 3,4 m para dentro (parede quente
    # acesa); no vao do hall o nucleo de pedra preta desce ate o deque
    # lounge da quina noroeste (render de perto da piscina): a caixa de vidro sai ate o plano do
    # painel de madeira (norte) e ate a linha do vidro das sacadas (oeste) — "ponta com ponta";
    # o vidro recuado do terreo nesses trechos sai para nao dobrar
    zl0, zl1, xl1 = -1.0, Z(450) + 0.5, X(440)
    yl = TERREO_H - 1.1
    corte = {0: lambda q: q[0] < xl1 - 0.01, len(POLY) - 1: lambda q: q[1] < zl1 + 0.01}
    u = 0.0
    def pano(a, b, nn, mat, y1_, u):
        dx, dz = b[0] - a[0], b[1] - a[1]; L = math.hypot(dx, dz)
        mesh.quad(mat, (a[0], y0, a[1]), (b[0], y0, b[1]), (b[0], y1_, b[1]), (a[0], y1_, a[1]), nn,
                  [(u * 3, 0), ((u + L / 6) * 3, 0), ((u + L / 6) * 3, (y1_ - y0) / 2), (u * 3, (y1_ - y0) / 2)])
        if mat != M_VIDRO_JANELA:
            return
        nseg = max(1, int(round(L / 1.5)))
        for k in range(1, nseg):
            t = k / nseg; px, pz = a[0] + dx * t, a[1] + dz * t
            mesh.box(M_MOLDURA, (px - 0.04 + nn[0] * 0.06, y0, pz - 0.04 + nn[2] * 0.06), (px + 0.04 + nn[0] * 0.06, y1_ - 0.05, pz + 0.04 + nn[2] * 0.06), 0.2)
        for yy in (0.04, 2.6):
            mesh.quad(M_MOLDURA, (a[0] + nn[0] * 0.06, yy, a[1] + nn[2] * 0.06), (b[0] + nn[0] * 0.06, yy, b[1] + nn[2] * 0.06),
                      (b[0] + nn[0] * 0.06, yy + 0.06, b[1] + nn[2] * 0.06), (a[0] + nn[0] * 0.06, yy + 0.06, a[1] + nn[2] * 0.06), nn)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        if i in corte:                                  # trecho coberto pelo lounge da quina
            if i == 0: a = (xl1, a[1])
            else: b = (b[0], zl1)
        dx, dz = b[0] - a[0], b[1] - a[1]; L = math.hypot(dx, dz); nn = (dz / L, 0, -dx / L)
        nucleo = bool(FACES[list(FACES)[i]].get('vidro'))
        mat = M_TORRE if nucleo else M_VIDRO_JANELA
        pano(a, b, nn, mat, y1, u)
        if not nucleo:   # faixa preta no alto do vidro
            mesh.quad(M_MOLDURA, (a[0] + nn[0] * 0.07, y1 - 0.8, a[1] + nn[2] * 0.07), (b[0] + nn[0] * 0.07, y1 - 0.8, b[1] + nn[2] * 0.07),
                      (b[0] + nn[0] * 0.07, y1, b[1] + nn[2] * 0.07), (a[0] + nn[0] * 0.07, y1, a[1] + nn[2] * 0.07), nn)
        u += L / 6
    # caixa do lounge: vidro norte (plano do painel) e oeste (linha do vidro das sacadas), pontas
    # fechadas, piso de madeira, forro aceso e faixa escura ate o forro da sacada no lado oeste
    pano((X_PAINEL0, zl0), (xl1, zl0), (0, 0, -1), M_VIDRO_JANELA, yl, 0.0)
    pano((X_PAINEL0, zl1), (X_PAINEL0, zl0), (-1, 0, 0), M_VIDRO_JANELA, yl, 0.0)
    mesh.quad(M_MOLDURA, (xl1, 0, zl0), (xl1, 0, inset), (xl1, yl, inset), (xl1, yl, zl0), (1, 0, 0))
    mesh.quad(M_MARMORE, (X_PAINEL0, 0, zl1), (inset, 0, zl1), (inset, TERREO_H - 0.3, zl1), (X_PAINEL0, TERREO_H - 0.3, zl1), (0, 0, 1))
    mesh.quad(M_MOLDURA, (X_PAINEL0 - 0.02, yl, zl1), (X_PAINEL0 - 0.02, yl, zl0), (X_PAINEL0 - 0.02, TERREO_H - 0.26, zl0), (X_PAINEL0 - 0.02, TERREO_H - 0.26, zl1), (-1, 0, 0))
    for (xa_, xb_, za_, zb_) in ((X_PAINEL0, xl1, zl0, inset), (X_PAINEL0, inset, inset, zl1)):
        mesh.quad(M_MADEIRA, (xa_, 0.02, za_), (xb_, 0.02, za_), (xb_, 0.02, zb_), (xa_, 0.02, zb_), (0, 1, 0),
                  [(xa_ / 3.6, za_ / 3.6), (xb_ / 3.6, za_ / 3.6), (xb_ / 3.6, zb_ / 3.6), (xa_ / 3.6, zb_ / 3.6)])
        mesh.quad(M_CORR_ACESO, (xa_, yl - 0.01, za_), (xb_, yl - 0.01, za_), (xb_, yl - 0.01, zb_), (xa_, yl - 0.01, zb_), (0, -1, 0))
    mesh.box(M_MOLDURA, (X_PAINEL0 - 0.45, 0.0, zl0 - 0.45), (X_PAINEL0 + 0.45, yl, zl0 + 0.45))   # pilar da quina
    for cx_, cz_ in poly:                                 # pilares pretos de ~0,9 m em cada canto do terreo
        mesh.box(M_MOLDURA, (cx_ - 0.45, 0.0, cz_ - 0.45), (cx_ + 0.45, TERREO_H - 0.3, cz_ + 0.45))
    sem_hall = [A, B, C, C2, D, E, F]                    # contorno sem o recorte do hall
    m_ = len(sem_hall); interno = []
    for i in range(m_):
        p = np.array(sem_hall[i]); prev = np.array(sem_hall[i - 1]); nxt = np.array(sem_hall[(i + 1) % m_])
        d1 = p - prev; d1 /= np.linalg.norm(d1); d2 = nxt - p; d2 /= np.linalg.norm(d2)
        n1, n2 = np.array([d1[1], -d1[0]]), np.array([d2[1], -d2[0]])
        interno.append(tuple(p - (n1 + n2) / (1.0 + float(np.dot(n1, n2))) * 3.4))
    mesh.prism(M_LOUNGE, interno, 0.0, TERREO_H - 0.35, uvscale=0.25, top=False, bottom=False)
    ti = ear_clip(interno); mi = len(interno)
    mesh.add(M_MADEIRA, [(q[0], 0.02, q[1]) for q in interno], [(0, 1, 0)] * mi, [(q[0] / 3, q[1] / 3) for q in interno], [k for t in ti for k in t])
    mesh.add(M_CORR_ACESO, [(q[0], TERREO_H - 0.36, q[1]) for q in interno], [(0, -1, 0)] * mi, [(0.5, 0.5)] * mi, [k for t in ti for k in t])
    mobiliario_lounge(mesh)
    # pavilhao envidracado SOB a ala 17-30 (Render 1, recorte do terreo): da ponta B ate ~1/3
    # do caminho para a escada, na linha da borda das sacadas, montantes em diagonal alternados
    px0, px1 = X(590) + 0.35 * (B[0] - X(590)), B[0] - 0.3
    pz, ph = -1.65, TERREO_H - 0.3
    mesh.quad(M_VIDRO_JANELA, (px0, 0, pz), (px1, 0, pz), (px1, ph, pz), (px0, ph, pz), (0, 0, -1))
    # ponta oeste do pavilhao: parede escura com CORTE DIAGONAL (render de perto da piscina),
    # estreita no pe e larga em cima, como os montantes inclinados
    mesh.add(M_PAREDE, [(px0, 0, 0.0), (px0, 0, pz + 0.45), (px0, ph, pz - 0.9), (px0, ph, 0.0)], [(-1, 0, 0)] * 4,
             [(0, 0), (1, 0), (1, 1), (0, 1)], [0, 1, 2, 0, 2, 3])
    L = px1 - px0; n = int(L / 1.5)
    for k in range(n + 1):
        x = px0 + L * k / n; dx = 0.75 if k % 2 else -0.75
        mesh.quad(M_ALETA, (x, 0, pz - 0.05), (x + 0.1, 0, pz - 0.05), (x + 0.1 + dx, ph, pz - 0.05), (x + dx, ph, pz - 0.05), (0, 0, -1))
    mesh.box(M_ALETA, (px0 - 0.1, ph, pz - 0.15), (px1 + 0.1, ph + 0.3, 0.0))
    # laje do terreo sobre as sacadas do 1º pavimento: a torre sobressai; fundo da laje de cima e ripado
    mesh.prism(M_RIPADO, POLY, TERREO_H - 0.35, TERREO_H, uvscale=0.5, top=False, bottom=True, side_mat=M_PAREDE)
    entrada(mesh)
    embasamento(mesh, -6.5, B[0] + 9, -6.5, F[1] + 9)
    entorno_noroeste(mesh)


# entrada no patio do L (Renders 6, 7, 8 e 10, conferidos em 15/10/2026): na base da ala
# 17-30 (face sul), de oeste para leste — monolito do letreiro em pedra rustica escura com a fita
# de LED no alto e um canteiro aceso na frente; depois a marquise em balanco sobre o embarque:
# borda alta de placas cinza-claro (a ponta oeste em metal escuro), forro de tabuas de madeira
# com spots em fileira e uma claraboia de vidro escuro rebaixada no meio, apoiada num pilar
# redondo escuro. A fachada do lobby por tras e revestida de tabuas cinza envelhecidas com os
# panos de vidro da entrada e uma porta escura. Medidas estimadas pelos renders: AJUSTAR
X_MON0, X_MON1, Z_MON = 23.8, 32.0, 21.4               # monolito (frente virada para o sul)
X_MQ0, X_MQ1, Z_MQ1 = 33.0, 45.4, 28.6                  # marquise: de x0 a x1, da fachada ate z1
Y_MQ0, Y_MQ1 = 4.4, 5.3                                 # forro e topo da marquise


def entrada(mesh):
    zg = C[1] - 0.4                                     # pano de vidro do terreo (podium, inset 0,4)
    # ---- marquise
    x0, x1, z0, z1, ya, yb = X_MQ0, X_MQ1, zg, Z_MQ1, Y_MQ0, Y_MQ1
    mesh.quad(M_PAREDE, (x0, yb, z0), (x1, yb, z0), (x1, yb, z1), (x0, yb, z1), (0, 1, 0))
    def borda(a, b, nn, mat, emendas=True):
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        mesh.quad(mat, (a[0], ya, a[1]), (b[0], ya, b[1]), (b[0], yb, b[1]), (a[0], yb, a[1]), nn)
        if emendas:                                     # juntas das placas a cada ~2,5 m
            n = max(1, int(round(L / 2.5)))
            for k in range(1, n):
                t = k / n; px, pz = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
                o = (nn[0] * 0.006, nn[2] * 0.006); tx, tz = (b[0] - a[0]) / L * 0.012, (b[1] - a[1]) / L * 0.012
                mesh.quad(M_ALETA, (px - tx + o[0], ya, pz - tz + o[1]), (px + tx + o[0], ya, pz + tz + o[1]),
                          (px + tx + o[0], yb, pz + tz + o[1]), (px - tx + o[0], yb, pz - tz + o[1]), nn)
    borda((x0, z1), (x1, z1), (0, 0, 1), M_ACM)
    borda((x1, z1), (x1, z0), (1, 0, 0), M_ACM)
    borda((x0, z0), (x0, z1), (-1, 0, 0), M_MOLDURA, emendas=False)
    # forro de tabuas no sentido da fachada, com o recorte da claraboia
    sx0, sx1, sz0, sz1 = 36.2, 42.2, 21.6, 25.6
    for (ax, bx, az, bz) in ((x0, x1, z0, sz0), (x0, x1, sz1, z1), (x0, sx0, sz0, sz1), (sx1, x1, sz0, sz1)):
        mesh.quad(M_RIPADO, (ax, ya, az), (bx, ya, az), (bx, ya, bz), (ax, ya, bz), (0, -1, 0),
                  [(ax / 3, az / 3), (bx / 3, az / 3), (bx / 3, bz / 3), (ax / 3, bz / 3)])
    # claraboia: caixa de vidro escuro pendurada ~0,3 m abaixo do forro, com moldura escura
    gx0, gx1, gz0, gz1, yg = sx0 + 0.2, sx1 - 0.2, sz0 + 0.2, sz1 - 0.2, ya - 0.3
    mesh.quad(M_JANELA_ESC, (gx0, yg, gz0), (gx1, yg, gz0), (gx1, yg, gz1), (gx0, yg, gz1), (0, -1, 0))   # vidro escuro (Render 6)
    for (a, b, nn) in (((gx0, gz0), (gx1, gz0), (0, 0, -1)), ((gx1, gz0), (gx1, gz1), (1, 0, 0)),
                       ((gx1, gz1), (gx0, gz1), (0, 0, 1)), ((gx0, gz1), (gx0, gz0), (-1, 0, 0))):
        mesh.quad(M_MOLDURA, (a[0], yg, a[1]), (b[0], yg, b[1]), (b[0], ya, b[1]), (a[0], ya, a[1]), nn)
    for (ax, bx, az, bz) in ((sx0, sx1, sz0, gz0), (sx0, sx1, gz1, sz1), (sx0, gx0, gz0, gz1), (gx1, sx1, gz0, gz1)):
        mesh.quad(M_MOLDURA, (ax, ya + 0.01, az), (bx, ya + 0.01, az), (bx, ya + 0.01, bz), (ax, ya + 0.01, bz), (0, -1, 0))
    # spots do forro em fileiras (Render 7)
    for zc in (20.1, 27.4):
        for xc in np.arange(x0 + 1.1, x1 - 0.6, 1.9):
            mesh.box(M_LUZ, (xc - 0.08, ya - 0.012, zc - 0.08), (xc + 0.08, ya, zc + 0.08))
    for xc in (x0 + 1.4, x1 - 1.4):
        for zc in (22.4, 24.8):
            mesh.box(M_LUZ, (xc - 0.08, ya - 0.012, zc - 0.08), (xc + 0.08, ya, zc + 0.08))
    cilindro(mesh, M_ALETA, 43.6, 22.3, 0.32, 0.0, ya, seg=20)            # pilar redondo (Render 6)
    # ---- fachada do lobby: tabuas cinza na frente do vidro, menos nos vaos de entrada
    zr = zg + 0.09
    def tabuas(xa, xb, y0_=0.0, y1_=TERREO_H - 0.3):
        mesh.quad(M_RIPADO_CINZA, (xa, y0_, zr), (xb, y0_, zr), (xb, y1_, zr), (xa, y1_, zr), (0, 0, 1),
                  [(y0_ / 3, xa / 1.5), (y0_ / 3, xb / 1.5), (y1_ / 3, xb / 1.5), (y1_ / 3, xa / 1.5)])
    tabuas(C2[0] + 0.3, 35.0)                            # atras do monolito ate a entrada
    tabuas(39.4, 40.4)                                   # montante de madeira entre os vidros
    tabuas(42.4, 46.2)                                   # em volta da porta escura
    tabuas(35.0, 39.4, ya, TERREO_H - 0.3); tabuas(40.4, 42.4, ya, TERREO_H - 0.3)   # acima dos vidros
    mesh.quad(M_JANELA_ESC, (42.9, 0.0, zr + 0.01), (44.1, 0.0, zr + 0.01), (44.1, 3.2, zr + 0.01), (42.9, 3.2, zr + 0.01), (0, 0, 1))
    # base da ala 01-16 no patio (Render 10: atras do letreiro a base e fechada, em tabuas)
    xr = D[0] - 0.4 + 0.09
    mesh.quad(M_RIPADO_CINZA, (xr, 0.0, E[1] - 0.4), (xr, 0.0, D[1] - 0.4), (xr, TERREO_H - 0.3, D[1] - 0.4), (xr, TERREO_H - 0.3, E[1] - 0.4), (1, 0, 0),
              [(0, (E[1] - 0.4) / 1.5), (0, (D[1] - 0.4) / 1.5), ((TERREO_H - 0.3) / 3, (D[1] - 0.4) / 1.5), ((TERREO_H - 0.3) / 3, (E[1] - 0.4) / 1.5)])
    mesh.box(M_ALETA, (38.0, 1.6, zr), (38.8, 2.3, zr + 0.03))                       # placa escura na madeira
    # ---- monolito do letreiro
    m0, m1, zm, hm = X_MON0, X_MON1, Z_MON, 4.6
    zf_ = zm + 0.6
    mesh.quad(M_MONOLITO, (m0, 0, zf_), (m1, 0, zf_), (m1, hm, zf_), (m0, hm, zf_), (0, 0, 1),
              [(m0 / 2, 0), (m1 / 2, 0), (m1 / 2, hm / 2), (m0 / 2, hm / 2)])
    mesh.quad(M_MONOLITO, (m1, 0, zm), (m0, 0, zm), (m0, hm, zm), (m1, hm, zm), (0, 0, -1),
              [(m1 / 2, 0), (m0 / 2, 0), (m0 / 2, hm / 2), (m1 / 2, hm / 2)])
    for x_, nx in ((m0, -1), (m1, 1)):
        mesh.quad(M_MONOLITO, (x_, 0, zm), (x_, 0, zf_), (x_, hm, zf_), (x_, hm, zm), (nx, 0, 0),
                  [(0, 0), (0.3, 0), (0.3, hm / 2), (0, hm / 2)])
    mesh.quad(M_MONOLITO, (m0, hm, zm), (m1, hm, zm), (m1, hm, zf_), (m0, hm, zf_), (0, 1, 0),
              [(m0 / 2, 0), (m1 / 2, 0), (m1 / 2, 0.3), (m0 / 2, 0.3)])
    # fita de LED no alto e a lavagem de luz descendo pela pedra (Renders 6 e 10)
    mesh.quad(M_LUZ, (m0 + 0.15, hm - 0.1, zf_ + 0.03), (m1 - 0.15, hm - 0.1, zf_ + 0.03),
              (m1 - 0.15, hm - 0.04, zf_ + 0.03), (m0 + 0.15, hm - 0.04, zf_ + 0.03), (0, 0, 1))
    mesh.add(M_LAVAGEM, [(m0 + 0.1, hm - 0.1, zf_ + 0.015), (m1 - 0.1, hm - 0.1, zf_ + 0.015),
                         (m1 - 0.1, hm - 2.3, zf_ + 0.015), (m0 + 0.1, hm - 2.3, zf_ + 0.015)],
             [(0, 0, 1)] * 4, [(0, 0), (1, 0), (1, 1), (0, 1)], [0, 2, 1, 0, 3, 2])
    lw = 4.9; lh = lw * 487 / 2048
    logo_quad(mesh, (m0 + 0.6, 2.0, zf_ + 0.02), (0, 0, 1), lw, lh)
    # canteiro baixo na frente, com touceiras e balizadores acesos
    mesh.box(M_MOVEL_ESC, (m0 + 0.2, 0.0, zf_ + 0.2), (m1 - 0.2, 0.42, zf_ + 1.0))
    for k, xc in enumerate(np.arange(m0 + 0.7, m1 - 0.4, 0.95)):
        tufo(mesh, float(xc), 0.42, zf_ + 0.6, h=0.95, r=0.5, folhas=9, seed=200 + k)
        if k % 2 == 0:
            mesh.box(M_LUZ, (xc - 0.05, 0.42, zf_ + 1.0), (xc + 0.05, 0.5, zf_ + 1.04))


def embasamento(mesh, x0, x1, z0, z1):
    """deque de pedra (y = 0) sobre o embasamento, e a praca de paralelepipedo em volta, ~2,5 m
    abaixo (render da quina noroeste no nivel da rua, 14/10/2026). Parede do embasamento, de
    cima para baixo: placas grandes de pedra cinza, uma faixa escura de grelha de ventilacao
    (subsolos) e mais uma fiada de placas ate a praca. Alturas: AJUSTAR."""
    # patio da entrada (Renders 6 e 10): paralelepipedo molhado, com uma faixa de pedra escura
    # polida junto as fachadas e sob a marquise; o resto do deque (piscina e lounge) segue em marmore
    polido = [(C2[0], C[0], C[1], C[1] + 3.5), (X_MQ0, X_MQ1, C[1], Z_MQ1),
              (D[0], D[0] + 3.5, D[1], E[1]), (D[0], C2[0], C[1], D[1])]
    patio = lambda x, z: x > D[0] and z > C[1]
    xs = sorted({x0, x1, *[v for p in POOL_RECTS for v in p[:2]], *[v for p in polido for v in p[:2]], D[0]})
    zs = sorted({z0, z1, *[v for p in POOL_RECTS for v in p[2:]], *[v for p in polido for v in p[2:]], C[1]})
    for i in range(len(xs) - 1):
        for j in range(len(zs) - 1):
            cx, cz = (xs[i] + xs[i + 1]) / 2, (zs[j] + zs[j + 1]) / 2
            if any(p[0] < cx < p[1] and p[2] < cz < p[3] for p in POOL_RECTS):
                continue                                     # aqui e agua
            ax, bx, az, bz = xs[i], xs[i + 1], zs[j], zs[j + 1]
            if patio(cx, cz) and not any(p[0] < cx < p[1] and p[2] < cz < p[3] for p in polido):
                mesh.quad(M_PARALELEPIPEDO, (ax, 0, az), (bx, 0, az), (bx, 0, bz), (ax, 0, bz), (0, 1, 0),
                          [(ax / 2, az / 2), (bx / 2, az / 2), (bx / 2, bz / 2), (ax / 2, bz / 2)])
                continue
            mesh.quad(M_MARMORE, (ax, 0, az), (bx, 0, az), (bx, 0, bz), (ax, 0, bz), (0, 1, 0),
                      [(ax / 3.6, az / 3.6), (bx / 3.6, az / 3.6), (bx / 3.6, bz / 3.6), (ax / 3.6, bz / 3.6)])
    # Render 1: concreto cinza liso em cima e, embaixo, uma faixa escura (a grelha de ventilacao)
    faixas = ((0.0, -1.3, M_PLACA), (-1.3, Y_RUA, M_LAMINA))
    lados = (((x0, z0), (x1, z0), (0, 0, -1)), ((x1, z0), (x1, z1), (1, 0, 0)),
             ((x1, z1), (x0, z1), (0, 0, 1)), ((x0, z1), (x0, z0), (-1, 0, 0)))
    for (ax, az), (bx, bz), nn in lados:
        L = math.hypot(bx - ax, bz - az)
        for ya, yb, mat in faixas:
            if mat == M_LAMINA:      # ripas na horizontal: a textura ribeada vai de lado
                uv = [(0, 0), (0, L / 4), (0.3, L / 4), (0.3, 0)]
            else:                    # placas de 1,2 x 0,65 m (ladrilho 2,4 x 1,3 m)
                uv = [(0, -ya / 1.3), (L / 2.4, -ya / 1.3), (L / 2.4, -yb / 1.3), (0, -yb / 1.3)]
            mesh.quad(mat, (ax, ya, az), (bx, ya, bz), (bx, yb, bz), (ax, yb, az), nn, uv)
    # pingadeira clara no alto do embasamento
    for lo, hi in (((x0 - 0.05, -0.06, z0 - 0.05), (x1 + 0.05, 0.02, z0 + 0.3)), ((x0 - 0.05, -0.06, z0 - 0.05), (x0 + 0.3, 0.02, z1 + 0.05)),
                   ((x0 - 0.05, -0.06, z1 - 0.3), (x1 + 0.05, 0.02, z1 + 0.05)), ((x1 - 0.3, -0.06, z0 - 0.05), (x1 + 0.05, 0.02, z1 + 0.05))):
        mesh.box(M_PLACA, lo, hi)
    # piso em volta: o chao molhado e espelhado do proprio site (veu + reflexo), como a agua do
    # Render 1 — a praca de paralelepipedo da rodada anterior saiu


def espelho_L(mesh):
    """espelho d'agua afundado (render da quina): paredes e fundo de marmore preto, lamina d'agua
    escura 18 cm abaixo do deque e luzinhas quentes submersas junto as paredes."""
    poly = POOL_L; n = len(poly)
    prof, ya = -0.6, -0.18
    tris = ear_clip(poly)
    mesh.add(M_AGUA, [(p[0], ya, p[1]) for p in poly], [(0, 1, 0)] * n, [(p[0] / 3.6, p[1] / 3.6) for p in poly], [k for t in tris for k in t])
    mesh.add(M_MARMORE, [(p[0], prof, p[1]) for p in poly], [(0, 1, 0)] * n, [(p[0] / 3.6, p[1] / 3.6) for p in poly], [k for t in tris for k in t])
    inside = lambda x, z: any(r[0] < x < r[1] and r[2] < z < r[3] for r in POOL_RECTS)
    # degrau/banco submerso de marmore junto as bordas de fora (render de perto da piscina)
    (ax0, ax1, az0, az1), (bx0, bx1, bz0, bz1) = POOL_RECTS
    mesh.box(M_MARMORE, (ax0, prof, az0), (ax1, -0.34, az0 + 0.6), 0.28)
    mesh.box(M_MARMORE, (bx0, prof, bz0), (bx0 + 0.6, -0.34, bz1), 0.28)
    for k in range(n):
        a, b = poly[k], poly[(k + 1) % n]
        dx, dz = b[0] - a[0], b[1] - a[1]; L = math.hypot(dx, dz)
        nn = (-dz / L, 0, dx / L)
        mid = ((a[0] + b[0]) / 2 + nn[0] * 0.05, (a[1] + b[1]) / 2 + nn[2] * 0.05)
        if not inside(*mid):
            nn = (-nn[0], 0, -nn[2])                         # normal para dentro da agua
        mesh.quad(M_MARMORE, (a[0], 0, a[1]), (b[0], 0, b[1]), (b[0], prof, b[1]), (a[0], prof, a[1]), nn,
                  [(0, 0), (L / 3.6, 0), (L / 3.6, 0.17), (0, 0.17)])
        for q in range(max(1, int(L / 1.6))):
            t = (q + 0.5) / max(1, int(L / 1.6))
            cx, cz = a[0] + dx * t + nn[0] * 0.03, a[1] + dz * t + nn[2] * 0.03
            mesh.box(M_LUZ, (cx - 0.035, -0.13, cz - 0.035), (cx + 0.035, -0.07, cz + 0.035))   # pontinho acima da agua


def cilindro(mesh, mat, cx, cz, r, y0, y1, seg=16):
    ring = [(cx + r * math.cos(2 * math.pi * k / seg), cz + r * math.sin(2 * math.pi * k / seg)) for k in range(seg)]
    for k in range(seg):
        a, b = ring[k], ring[(k + 1) % seg]
        nm = (math.cos(2 * math.pi * (k + 0.5) / seg), 0, math.sin(2 * math.pi * (k + 0.5) / seg))
        mesh.quad(mat, (a[0], y0, a[1]), (b[0], y0, b[1]), (b[0], y1, b[1]), (a[0], y1, a[1]), nm)
    pts = [(cx, y1, cz)] + [(p[0], y1, p[1]) for p in ring]
    mesh.add(mat, pts, [(0, 1, 0)] * (seg + 1), [(0.5, 0.5)] * (seg + 1), [x for q in range(seg) for x in (0, 1 + q, 1 + (q + 1) % seg)])


def tufo(mesh, cx, y, cz, h=0.9, r=0.5, folhas=10, seed=0):
    """touceira de folhas longas (tipo agave): cada folha e um triangulo fino que se abre para fora."""
    rng = np.random.default_rng(seed)
    for k in range(folhas):
        ang = 2 * math.pi * k / folhas + rng.uniform(-0.25, 0.25)
        dx, dz = math.cos(ang), math.sin(ang)
        topo = (cx + dx * r * rng.uniform(0.7, 1.0), y + h * rng.uniform(0.75, 1.0), cz + dz * r * rng.uniform(0.7, 1.0))
        w = 0.07
        a = (cx - dz * w, y, cz + dx * w); b = (cx + dz * w, y, cz - dx * w)
        mesh.add(M_FOLHAGEM, [a, b, topo], [(dx * 0.6, 0.5, dz * 0.6)] * 3, [(0, 0), (1, 0), (0.5, 1)], [0, 1, 2])


def palmeira(mesh, cx, y, cz, alt=8.5, seed=0, baixa=False):
    """palmeira-das-canarias (16/10/2026). CADA FOLHA E DIFERENTE (pedido do usuario: 'cada uma de um jeito diferente pra dar mais
    dinamismo'): comprimento, angulo de saida, curvatura, arqueamento para o lado, tamanho/queda/densidade dos foliolos e cor variam por
    folha; o azimute segue a espiral de ouro com ruido (nunca alinhadas), ha folhas quebradas, folhas velhas caindo e folhas novas
    subindo no centro. Tronco MARROM CLARO. baixa=True (palmeiras internas do patio): copa limitada a ~1,6 m acima do alto do tronco
    (nao cobre a vista dos studios; o usuario quer so ate a altura do vidro da sacada do 1o andar)."""
    rng = np.random.default_rng(seed)
    mt = globals().get('M_TRONCO', M_MOVEL_ESC)
    cilindro(mesh, mt, cx, cz, 0.21, y, y + alt * 0.40, seg=10)
    cilindro(mesh, mt, cx, cz, 0.17, y + alt * 0.40, y + alt - 0.30, seg=10)
    cilindro(mesh, mt, cx, cz, 0.25, y + alt - 0.40, y + alt + 0.04, seg=10)          # engrossamento sob a copa
    topo = y + alt
    pal = [globals().get(n, M_FOLHAGEM) for n in ('M_PALMA', 'M_PALMA2', 'M_PALMA3', 'M_PALMA_SECA')]
    nf = int(rng.integers(40, 53))
    ouro = 2.399963; ang0 = rng.uniform(0, 2 * math.pi)
    rise_max = 1.0 if baixa else 99.0
    for k in range(nf):
        f = k / (nf - 1)                                    # 0 = folhas velhas (embaixo) ... 1 = folhas novas (centro)
        if rng.random() < 0.05:
            continue                                        # falha: uma folha a menos
        ang = ang0 + k * ouro + rng.uniform(-0.22, 0.22)
        novo = f > 0.80
        quebrada = (not novo) and rng.random() < 0.08
        if novo:                                            # lanca de folha nova: curta, sobe
            L = rng.uniform(1.9, 3.0); p0 = math.radians(rng.uniform(52, 70)); p1 = math.radians(rng.uniform(25, 55)); ce = rng.uniform(1.2, 1.8)
        else:
            base = (1.0 - f)
            L = rng.uniform(2.9, 4.9) * (0.78 + 0.22 * base)
            p0 = math.radians(rng.uniform(-6, 24) if baixa else rng.uniform(10, 52))
            p1 = math.radians(rng.uniform(-88, -38))
            ce = rng.uniform(1.05, 1.95)
            if quebrada:
                L *= rng.uniform(0.45, 0.7); p1 = math.radians(rng.uniform(-90, -75)); ce = rng.uniform(0.8, 1.2)
        bend = rng.uniform(-0.65, 0.65) * (0.4 if novo else 1.0)     # arqueamento para o lado (yaw total ao longo da folha)
        ls = rng.uniform(0.72, 1.35)                        # tamanho dos foliolos
        droop = rng.uniform(0.35, 0.98)                     # quanto os foliolos pendem
        ww = rng.uniform(0.07, 0.13)                        # largura da base do foliolo
        pares = [(0.0, 0.5), (0.0, 0.33, 0.66), (0.0, 0.25, 0.5, 0.75)][int(rng.choice(3, p=[0.25, 0.4, 0.35]))]
        r_ = rng.random()
        if novo:
            mat_f = pal[2] if r_ < 0.65 else pal[1]
        elif quebrada or r_ < 0.10:
            mat_f = pal[3]                                  # folha seca/oliva
        else:
            mat_f = pal[0] if r_ < 0.40 else (pal[1] if r_ < 0.75 else pal[2])
        seg = 10
        pts = [np.zeros(3)]; cur = np.zeros(3)
        for s_ in range(seg):
            t = (s_ + 0.5) / seg
            pit = p0 + (p1 - p0) * t ** ce
            ya = ang + bend * t
            step = L / seg
            cur = cur + np.array([math.cos(ya) * step * math.cos(pit), step * math.sin(pit), math.sin(ya) * step * math.cos(pit)])
            pts.append(cur.copy())
        pts = np.array(pts)
        if pts[:, 1].max() > rise_max:
            pts[:, 1] *= rise_max / pts[:, 1].max()         # copa baixa: achata a subida, a folha so cai
        for s_ in range(1, len(pts)):
            a0, a1 = pts[s_ - 1], pts[s_]
            h_ = np.array([a1[0] - a0[0], 0.0, a1[2] - a0[2]]); n_ = np.linalg.norm(h_)
            if n_ < 1e-6:
                continue
            fwd = h_ / n_; perp = np.array([-fwd[2], 0.0, fwd[0]])
            t = s_ / seg; w = 0.035 * (1 - 0.6 * t)
            A = np.array([cx, topo - 0.1, cz])
            p_a, p_b = A + a0, A + a1
            mesh.add(mat_f, [tuple(p_a + perp * w), tuple(p_a - perp * w), tuple(p_b - perp * w), tuple(p_b + perp * w)],
                     [tuple(0.3 * fwd + np.array([0, 0.9, 0]))] * 4, [(0, 0), (1, 0), (1, 1), (0, 1)], [0, 1, 2, 0, 2, 3])
            if s_ < 2:
                continue
            for frac in pares:
                tt = (s_ - 1 + frac) / seg
                base_p = A + a0 + (a1 - a0) * frac
                ll = ls * (0.35 + 1.15 * math.sin(math.pi * min(1, tt * 1.05)) ** 0.8) * (0.7 if novo else 1.0)
                for sg in (-1, 1):
                    lado = perp * sg
                    queda = (0.45 + 0.4 * tt) * droop / 0.7
                    ponta = base_p + lado * ll * math.cos(0.5) + fwd * ll * 0.3 + np.array([0, -1.0, 0]) * ll * queda * 0.8
                    c = fwd * ww
                    mesh.add(mat_f, [tuple(base_p - c), tuple(base_p + c), tuple(ponta + c * 0.2)],
                             [tuple(0.2 * lado + np.array([0, 0.95, 0]))] * 3, [(0, 0), (1, 0), (0.5, 1)], [0, 1, 2])


def arvore(mesh, cx, y, cz, r=1.8, seed=0):
    """arvore frondosa: 70 cartoes de folha de 0,45 m dentro de um elipsoide (copa), tronco fino"""
    rng = np.random.default_rng(seed)
    cilindro(mesh, M_MOVEL_ESC, cx, cz, 0.12, y, y + r * 1.3, seg=8)
    for k in range(70):
        while True:
            v = rng.uniform(-1, 1, 3)
            if v @ v <= 1:
                break
        c = (cx + v[0] * r, y + r * 1.3 + v[1] * r * 0.8 + r * 0.6, cz + v[2] * r)
        a = rng.uniform(0, 2 * math.pi); t = rng.uniform(0, 1)
        u = np.array([math.cos(a), 0, math.sin(a)]) * 0.225
        w = np.array([-math.sin(a) * t, 1 - t, math.cos(a) * t]); w = w / np.linalg.norm(w) * 0.225
        nrm = tuple(np.cross(u, w) / np.linalg.norm(np.cross(u, w)))
        mesh.add(M_FOLHAGEM, [tuple(np.array(c) - u - w), tuple(np.array(c) + u - w), tuple(np.array(c) + u + w), tuple(np.array(c) - u + w)],
                 [nrm] * 4, [(0, 0), (1, 0), (1, 1), (0, 1)], [0, 1, 2, 0, 2, 3])


def espreguicadeira(mesh, x, z, y=0.0, sentido=1):
    """espreguicadeira de tela escura: quadro baixo, assento e encosto inclinado (~1,9 x 0,7 m)."""
    L, Wd = 1.9, 0.7
    for dz in (-Wd / 2, Wd / 2 - 0.04):
        mesh.box(M_MOVEL_ESC, (x - 0.04, y, z + dz), (x + L - 0.04, y + 0.06, z + dz + 0.04))
    for ex in (0.1, L - 0.14):
        mesh.box(M_MOVEL_ESC, (x + ex, y, z - Wd / 2), (x + ex + 0.04, y + 0.3, z + Wd / 2))
    mesh.box(M_MOVEL_ESC, (x + 0.05, y + 0.3, z - Wd / 2 + 0.02), (x + L * 0.62, y + 0.34, z + Wd / 2 - 0.02))
    a0 = (x + L * 0.62, y + 0.32); a1 = (x + L * 0.62 + 0.55, y + 0.78)
    mesh.quad(M_MOVEL_ESC, (a0[0], a0[1], z - Wd / 2), (a1[0], a1[1], z - Wd / 2), (a1[0], a1[1], z + Wd / 2), (a0[0], a0[1], z + Wd / 2), (0, 1, 0))


def area_externa_noroeste(mesh):
    """deque na frente da escada e do painel (render da quina): plataforma 30 cm mais alta com
    jardineira preta e touceiras, daybed redondo de rattan e quatro espreguicadeiras."""
    x0, x1, z0, z1 = X(490) - 0.5, X(840), -6.2, -2.0
    mesh.box(M_MARMORE, (x0, 0.0, z0), (x1, 0.3, z1), 0.28)
    yb = 0.3
    mesh.box(M_PAREDE, (x0 + 0.9, yb, -3.8), (x0 + 5.1, yb + 0.75, -2.6))
    for k in range(7):
        tufo(mesh, x0 + 1.5 + k * 0.55, yb + 0.75, -3.2, h=0.95, r=0.55, seed=k)
    cx, cz = x0 + 8.6, -3.7
    cilindro(mesh, M_CESTO, cx, cz, 1.15, yb, yb + 0.5)
    cilindro(mesh, M_MOVEL, cx, cz, 0.95, yb + 0.5, yb + 0.68)
    for q in range(int((x1 - x0) / 2.4)):                       # luzinhas na borda da plataforma, na frente
        cx = x0 + 1.2 + q * 2.4
        mesh.box(M_LUZ, (cx - 0.07, 0.2, z0 - 0.02), (cx + 0.07, 0.26, z0 + 0.03))
    for k in range(4):                                         # quatro espreguicadeiras em fila
        espreguicadeira(mesh, x0 + 11.6, -5.35 + k * 0.95, y=yb)


def mobiliario_lounge(mesh):
    """lounge visto pelo vidro: grupos de sofa, poltronas e mesa de centro, e vasos com touceira,
    junto as faces norte (sob o painel) e oeste. Formas simples; so o conjunto importa."""
    def grupo(eixo, t, k):
        # eixo 'n': corre ao longo de x, fundo em z = 3,6; 'o': ao longo de z, fundo em x = 3,6
        fx = (lambda u, v: (u, v)) if eixo == 'n' else (lambda u, v: (v, u))
        def caixa(mat, u0, v0, u1, v1, y0, y1):
            (a, b), (c, d) = fx(u0, v0), fx(u1, v1)
            mesh.box(mat, (min(a, c), y0, min(b, d)), (max(a, c), y1, max(b, d)))
        # Render 5 de perto (15/10/2026): tapete cinza, sofa claro com almofadas, mesa de centro de
        # madeira, poltronas de quadro escuro com assento claro e planta alta num vaso preto
        caixa(M_TAPETE, t - 0.5, 0.6, t + 2.7, 3.4, 0.02, 0.035)        # tapete
        caixa(M_MOVEL, t, 2.7, t + 2.2, 3.55, 0.0, 0.45)                 # sofa
        caixa(M_MOVEL, t, 3.3, t + 2.2, 3.55, 0.45, 0.95)                # encosto
        for du in (0.15, 0.85, 1.55):                                    # almofadas
            caixa(M_MOVEL, t + du, 3.1, t + du + 0.5, 3.28, 0.45, 0.85)
        caixa(M_MADEIRA, t + 0.4, 1.5, t + 1.6, 2.2, 0.0, 0.38)         # mesa de centro de madeira
        for du in (-0.2, 1.7):                                           # poltronas
            caixa(M_MOVEL_ESC, t + du, 0.9, t + du + 0.8, 1.7, 0.0, 0.18)
            caixa(M_MOVEL, t + du + 0.06, 0.96, t + du + 0.74, 1.64, 0.18, 0.42)
            caixa(M_MOVEL_ESC, t + du, 0.9, t + du + 0.8, 1.02, 0.42, 0.9)
        # planta alta no fim do grupo: vaso preto, tronco e copa de folhas longas
        (px, pz) = fx(t + 2.9, 3.0)
        mesh.box(M_MOVEL_ESC, (px - 0.28, 0.0, pz - 0.28), (px + 0.28, 0.75, pz + 0.28))
        mesh.box(M_MOVEL_ESC, (px - 0.03, 0.75, pz - 0.03), (px + 0.03, 1.5, pz + 0.03))
        tufo(mesh, px, 1.2, pz, h=1.0, r=0.6, folhas=12, seed=k)
        tufo(mesh, px, 0.75, pz, h=0.7, r=0.45, folhas=8, seed=k + 50)
    ng = 0
    for t in np.arange(1.2, X(440) - 2.5, 6.0):                    # norte, sob o painel
        grupo('n', float(t), ng); ng += 1
    for t in np.arange(2.5, Z(450) - 2.0, 6.0):                    # oeste
        grupo('o', float(t), ng); ng += 1
    for t in np.arange(X(590) + 3.0, X(590) + 3.0 + 14.0, 6.0):  # norte, atras do pavilhao diagonal
        grupo('n', float(t), ng); ng += 1


def entorno_noroeste(mesh):
    """quina noroeste no nivel da rua (Renders 4, 5, 9): espelho d'agua em L na frente do
    lounge de vidro, e muro baixo de pedra com gradil na borda do deque. Medidas: AJUSTAR."""
    espelho_L(mesh)
    area_externa_noroeste(mesh)
    # guarda-corpo na borda do deque (render da quina no nivel da rua): paineis de vidro entre
    # montantes pretos altos a cada ~1,5 m; na frente do pavilhao da ala 17-30, gradil de barras
    px0 = X(590) + 0.35 * (B[0] - X(590)) - 1.0
    trechos = [((-6.35, -6.35), (px0, -6.35), 'vidro'), ((px0, -6.35), (B[0] + 6.5, -6.35), 'gradil'),
               ((-6.35, -6.35), (-6.35, F[1] + 6.5), 'vidro')]
    for (ax, az), (bx, bz), tipo in trechos:
        L = math.hypot(bx - ax, bz - az)
        passo = 1.5 if tipo == 'vidro' else 0.12
        nseg = max(1, int(round(L / passo)))
        h = 1.85 if tipo == 'vidro' else 1.15                 # Render 1: montantes altos, acima das agaves
        e_ = 0.04 if tipo == 'vidro' else 0.012          # montante de 8 cm ou barra de 2,4 cm
        for k in range(nseg + 1):
            x = ax + (bx - ax) * k / nseg; z = az + (bz - az) * k / nseg
            mesh.box(M_PAREDE, (x - e_, 0.0, z - e_), (x + e_, h, z + e_))
        if tipo == 'vidro':
            nx_, nz_ = (0, -1) if az == bz else (-1, 0)
            mesh.quad(M_VIDRO_JANELA, (ax, 0.05, az), (bx, 0.05, bz), (bx, 1.6, bz), (ax, 1.6, az), (nx_, 0, nz_))
        else:
            mesh.box(M_PAREDE, (min(ax, bx), h - 0.05, min(az, bz) - 0.03), (max(ax, bx), h, max(az, bz) + 0.03))
    # Render 1: fileira continua de agaves numa jardineira baixa junto ao guarda-corpo, nas duas faces
    for (ax, az), (bx, bz) in (((-5.9, -5.9), (px0 - 0.3, -5.9)), ((-5.9, -5.3), (-5.9, Z(450) + 0.6))):
        lo = (min(ax, bx) - 0.35, 0.0, min(az, bz) - 0.35); hi = (max(ax, bx) + 0.35, 0.35, max(az, bz) + 0.35)
        mesh.box(M_PAREDE, lo, hi)
        L = math.hypot(bx - ax, bz - az); nt = int(L / 0.95)
        for k in range(nt + 1):
            x = ax + (bx - ax) * k / nt; z = az + (bz - az) * k / nt
            tufo(mesh, x, 0.35, z, h=0.95, r=0.55, folhas=11, seed=100 + k)
    # anexo no fim do espelho d'agua da fachada oeste (render de perto da piscina): parede de
    # MARMORE GRAFITE com uma porta escura e uma janela acesa, virada para o deque (norte)
    za, zb = Z(450) + 1.0, Z(450) + 7.0
    mesh.box(M_MARMORE, (-6.0, 0.0, za), (-1.2, 3.2, zb), 0.28)
    mesh.quad(M_JANELA_ESC, (-5.4, 0.0, za - 0.01), (-4.3, 0.0, za - 0.01), (-4.3, 2.4, za - 0.01), (-5.4, 2.4, za - 0.01), (0, 0, -1))
    mesh.quad(M_CORR_ACESO, (-3.6, 0.9, za - 0.01), (-1.8, 0.9, za - 0.01), (-1.8, 2.5, za - 0.01), (-3.6, 2.5, za - 0.01), (0, 0, -1),
              [(0, 1), (1, 1), (1, 0), (0, 0)])


# -------------------------------------------------------------- montagem
def build():
    nodes, mesh_list = [], []
    add_mesh = lambda m, nome: (mesh_list.append((m, nome)) or len(mesh_list) - 1)
    add_node = lambda **kw: (nodes.append(kw) or len(nodes) - 1)

    um = unit_meshes()
    unit_mesh_idx = {k: add_mesh(m, f'unidade-S{k:02d}') for k, (m, _) in um.items()}
    children = []

    m = Mesh(); podium(m)
    children.append(add_node(name='TERREO', mesh=add_mesh(m, 'terreo'), extras={'provisorio': True}))

    for i in range(PAV_TIPO):
        y0 = TERREO_H + i * PE
        m = Mesh()
        # sem a parede das duas faces de topo: ficam atras da madeira, e o corredor visto pela
        # faixa de vidro precisa de fundo
        m.prism(M_PAREDE, POLY, y0, y0 + PE, uvscale=0.2, top=False, bottom=False,
                pular={list(FACES).index('leste_barra'), list(FACES).index('sul_haste')})
        for face, f in FACES.items():
            if f['sac']:
                balcony_band(m, face, i, y0)
            elif f.get('vidro'):
                # centro do L (Render 8): o nucleo escuro da escada atravessa o predio e aparece
                # aqui como uma faixa preta do terreo ao alto, sem vidro
                (ax, az), (bx, bz) = f['p']; nx, nz = f['n']; o = 0.04
                Lh = math.hypot(bx - ax, bz - az)
                m.quad(M_TORRE, (ax + nx * o, y0, az + nz * o), (bx + nx * o, y0, bz + nz * o),
                       (bx + nx * o, y0 + PE, bz + nz * o), (ax + nx * o, y0 + PE, az + nz * o), (nx, 0, nz),
                       [(0, y0 * 0.5), (Lh * 0.5, y0 * 0.5), (Lh * 0.5, (y0 + PE) * 0.5), (0, (y0 + PE) * 0.5)])
        pav = add_node(name=f'PAV-{i + 1:02d}', mesh=add_mesh(m, f'pav{i + 1:02d}'), children=[],
                       extras={'pavimentoTipo': i + 1, 'nivel_m': round(y0, 2)})
        for k in range(1, 31):
            u = add_node(name=f'P{i + 1:02d}-S{k:02d}', mesh=unit_mesh_idx[k], translation=[0, round(y0, 3), 0],
                         extras={'pavimentoTipo': i + 1, 'studio': k, 'fachada': um[k][1]})
            nodes[pav]['children'].append(u)
        children.append(pav)

    m = Mesh(); roof(m); paredes_topo(m)
    for face, f in FACES.items():
        if f['sac']:
            balcony_band(m, face, PAV_TIPO, Y_ROOF, cobertura=True)
    children.append(add_node(name='COBERTURA', mesh=add_mesh(m, 'cobertura'), extras={'provisorio': True}))
    m = Mesh(); nucleo_noroeste(m)
    children.append(add_node(name='NUCLEO_NOROESTE', mesh=add_mesh(m, 'nucleo_noroeste'), extras={'provisorio': True}))

    root = add_node(name='CINNAMON_FACHADA_PROVISORIO', children=children, extras={
        'status': 'PROVISORIO - maquete a partir de renders + planta; nao e o modelo de arquitetura',
        'pavimentosTipo': PAV_TIPO, 'pavimentosTipo_origem': 'DERIVADO 510/30; total NAO confirmado',
        'studiosPorPavimento': 30, 'escala': '29,92 m2/studio sobre a planta, +-15%',
        'peDireito_m': PE, 'terreo_m': TERREO_H, 'laje_cobertura_m': Y_ROOF,
        'numeracao': 'P<pav>-S<studio da planta>; numeracao comercial das unidades NAO conhecida',
    })
    return nodes, mesh_list, root


def pack(nodes, mesh_list, root):
    chunks, views, accessors, images, textures, samplers = [], [], [], [], [], [{'magFilter': 9729, 'minFilter': 9987, 'wrapS': 10497, 'wrapT': 10497}]
    off = 0

    def view(data, target=None, stride=None):
        nonlocal off
        pad = (4 - len(data) % 4) % 4
        v = {'buffer': 0, 'byteOffset': off, 'byteLength': len(data)}
        if target: v['target'] = target
        if stride: v['byteStride'] = stride
        views.append(v); chunks.append(data + b'\0' * pad); off += len(data) + pad
        return len(views) - 1

    img_idx = {}
    def image(name):
        if name not in img_idx:
            data = texturas.render(name)
            mime = 'image/png' if name.endswith('.png') else 'image/jpeg'
            images.append({'bufferView': view(data), 'mimeType': mime, 'name': name})
            textures.append({'sampler': 0, 'source': len(images) - 1})
            img_idx[name] = len(textures) - 1
        return img_idx[name]

    usados = {mat for m, _ in mesh_list for mat, p in m.prims.items() if p[0]}
    # UVs em 16 bits (KHR_mesh_quantization + KHR_texture_transform): inteiro = uv * ESC_UV, e
    # cada textura desfaz a escala. ESC_UV e a maior potencia de 2 que cabe no maior |uv|
    uv_max = max(float(np.abs(np.array(p[2], np.float32)).max()) for m, _ in mesh_list for p in m.prims.values() if p[0])
    ESC_UV = 2 ** int(math.floor(math.log2(32000 / max(uv_max, 1e-6))))
    ESC_UV = min(ESC_UV, 4096)
    tt = {'KHR_texture_transform': {'scale': [1.0 / ESC_UV, 1.0 / ESC_UV]}}
    mats = []
    for i_mat, (nome, base, metal, rough, t, extra) in enumerate(MATERIAIS):
        if i_mat not in usados:               # sem uso (ex.: lamina): nao embute textura
            mats.append({'name': nome}); continue
        pbr = {'baseColorFactor': base, 'metallicFactor': metal, 'roughnessFactor': rough}
        m = {'name': nome, 'pbrMetallicRoughness': pbr}
        if t:
            pbr['baseColorTexture'] = {'index': image(t['img']), 'extensions': tt}
            if t.get('nrm'): m['normalTexture'] = {'index': image(t['nrm']), 'extensions': tt}
            if t.get('mr'): pbr['metallicRoughnessTexture'] = {'index': image(t['mr']), 'extensions': tt}
        if 'emissiveFactor' in extra:
            m['emissiveFactor'] = extra['emissiveFactor']
            m.setdefault('extensions', {})['KHR_materials_emissive_strength'] = {'emissiveStrength': extra.get('strength', 1.0)}
        if extra.get('emis'):
            m['emissiveTexture'] = {'index': image(extra['emis']), 'extensions': tt}
        if extra.get('alpha_img'):
            pbr['baseColorTexture'] = {'index': image(extra['alpha_img']), 'extensions': tt}
            pbr['baseColorFactor'] = [1, 1, 1, 1]
        for k in ('alphaMode', 'doubleSided'):
            if k in extra: m[k] = extra[k]
        mats.append(m)

    gl_meshes = []
    for m, nome in mesh_list:
        prims = []
        for mat, (pos, nrm, uv, idx) in m.prims.items():
            if not pos: continue
            P = np.array(pos, np.float32); N = np.array(nrm, np.float32); U = np.array(uv, np.float32)
            assert len(P) < 65535, nome
            I = np.array(idx, np.uint16)
            # normais em 8 bits (KHR_mesh_quantization): 4 bytes por vertice em vez de 12 — o .glb
            # cai ~1 MB e o Three.js/Blender leem sem decodificador
            Nq = np.zeros((len(N), 4), np.int8)
            Nq[:, :3] = np.clip(np.round(N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9) * 127), -127, 127)
            Uq = np.round(U * ESC_UV).astype(np.int16)
            vp, vn, vu, vi = view(P.tobytes(), 34962), view(Nq.tobytes(), 34962, 4), view(Uq.tobytes(), 34962), view(I.tobytes(), 34963)
            b = len(accessors)
            accessors += [
                {'bufferView': vp, 'componentType': 5126, 'count': len(P), 'type': 'VEC3', 'min': P.min(0).tolist(), 'max': P.max(0).tolist()},
                {'bufferView': vn, 'componentType': 5120, 'normalized': True, 'count': len(N), 'type': 'VEC3'},
                {'bufferView': vu, 'componentType': 5122, 'count': len(U), 'type': 'VEC2'},
                {'bufferView': vi, 'componentType': 5123, 'count': len(I), 'type': 'SCALAR'}]
            prims.append({'attributes': {'POSITION': b, 'NORMAL': b + 1, 'TEXCOORD_0': b + 2}, 'indices': b + 3, 'material': mat})
        gl_meshes.append({'name': nome, 'primitives': prims})

    gltf = {'asset': {'version': '2.0', 'generator': 'scripts/fachada/gen_fachada.py (maquete provisoria)'},
            'extensionsUsed': ['KHR_materials_emissive_strength', 'KHR_mesh_quantization', 'KHR_texture_transform'],
            'extensionsRequired': ['KHR_mesh_quantization'],
            'scene': 0, 'scenes': [{'nodes': [root]}], 'nodes': nodes, 'meshes': gl_meshes,
            'materials': mats, 'textures': textures, 'images': images, 'samplers': samplers,
            'accessors': accessors, 'bufferViews': views, 'buffers': [{'byteLength': off}]}
    js = json.dumps(gltf, separators=(',', ':')).encode(); js += b' ' * ((4 - len(js) % 4) % 4)
    blob = b''.join(chunks)
    total = 12 + 8 + len(js) + 8 + len(blob)
    return (struct.pack('<4sII', b'glTF', 2, total) + struct.pack('<I4s', len(js), b'JSON') + js +
            struct.pack('<I4s', len(blob), b'BIN\0') + blob)


if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'img', 'fachada.glb')
    nodes, mesh_list, root = build()
    glb = pack(nodes, mesh_list, root)
    open(out, 'wb').write(glb)
    tri = sum(len(p[3]) // 3 for m, _ in mesh_list for p in m.prims.values())
    print(f'{out}: {len(glb) / 1e6:.2f} MB, {len(nodes)} nos, {len(mesh_list)} malhas, ~{tri} triangulos; '
          f'footprint {B[0]:.1f} x {F[1]:.1f} m, cobertura {Y_ROOF:.0f} m')
