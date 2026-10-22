#!/usr/bin/env python3
"""Cinnamon Studio - torre a partir do MODELO DO ARQUITETO (FBX do 3ds Max, 09/2026).

Uso:  python3 scripts/fachada/modelo-real/gen_fachada_real.py <pasta com partes.npz/json> <saida.glb>

Pipeline (Blender 4.5, headless; FBX.rar do arquiteto extraido numa pasta):
  1. blender -b --factory-startup --python visivel.py -- <pasta FBX> visivel.json 0.3
  2. blender -b --factory-startup --python extrai.py  -- <pasta FBX> visivel.json <pasta partes>
  3. python3 gen_fachada_real.py <pasta partes> img/fachada-real.glb
  4. QA (Chrome headless, GPU real): node f3d_qa.mjs site <saida>   |   node f3d_sel.mjs site <saida> "9,1;12,28"
  5. Comparar com os renders: node f3d_cams.mjs dados/cameras_site.json <saida> 40  (13 camerasdos renders,
     lidas da cena Twinmotion por twinmotion/mapa.py; dados/caixas_interior.json vem de bl/caixas.py)

partes.npz vem de extrai.py (Blender): so as faces vistas de fora, ja em coordenadas
do site (X leste, Y cima, Z sul, metros). Aqui: materiais do FBX -> materiais da
maquete (mesmas texturas de texturas.py), UVs por projecao na caixa e o mesmo
contrato de nos que js/fachada3d.js espera (P<pav>-S<studio>, PAV-nn, raiz
CINNAMON_FACHADA_PROVISORIO). Os 17 pavimentos reusam a mesma malha (so translacao).
"""
import json
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # scripts/fachada
sys.path.insert(0, REPO)
import gen_fachada as G  # noqa: E402

PASTA, SAIDA = sys.argv[1], sys.argv[2]

# Materiais lidos da cena do Twinmotion do arquiteto (CINNAMON-certo-10_000.tm, 22/09/2026) e
# afinados pelos renders (Renders Still CINNAMON, 08/2026). O FBX nao trouxe texturas e as cores dele
# sao placeholder do V-Ray; a cena do Twinmotion diz qual material de biblioteca foi aplicado a cada
# peca (caixilhos = Brushed aluminium 01, vidros = Clear glass, guarda = Clear glass 51% fume, forro
# das sacadas = forro pvc madeirado, topo das lajes = Bare concrete, aletas e molduras = Aluminium
# panels, placas de madeira = Chestnut 01 A, torre da escada e nucleo = Pedra (escura), rua =
# Herringbone cobblestone, base = porcelanato cimenticio). Cores: ver os renders.
for _i, _m in enumerate(G.MATERIAIS):
    # cortinas dos studios: creme claro mesmo apagadas (Render 5); a emissao continua sendo o 'acende'
    # Render 3 (16/10/2026): todos os studios com o ambiente aceso em tom quente atras do vidro —
    # a base fica media e quente (sem o lilas que o ceu azul dava ao creme) e o emissivo (ver
    # LUZ_BASE no js) faz o resto
    if _m[0] == 'janela_unidade':
        G.MATERIAIS[_i] = ('janela_unidade', G.srgb('#3a3028'), 0.0, 0.6, None,
                           {'emissiveFactor': [1, 1, 1], 'emis': 'cortina.jpg', 'strength': 1.0})
    # guarda das sacadas: vidro claro e refletivo (Render 4: le como faixa clara em cada andar)
    if _m[0] == 'vidro_guarda':
        # Render 2 de perto (16/10/2026): fume cinza-medio, quase sem espelho
        G.MATERIAIS[_i] = ('vidro_guarda', G.srgb('#4c525e', 0.52), 0.05, 0.05, None, {'alphaMode': 'BLEND', 'doubleSided': True})   # alvo ~#52596c
    if _m[0] == 'madeira_sacada':
        G.MATERIAIS[_i] = ('madeira_sacada', [1, 1, 1, 1], 0.0, 0.5, G.tex('madeira_forro.jpg', 'madeira_forro_n.jpg'),
                           {'emissiveFactor': [1.0, 0.72, 0.38], 'emis': 'madeira_forro.jpg', 'strength': 1.6})   # 16/10 (Renders 6/7 de perto): mediana #5a3f2d, castanho-dourado, menos vermelho
    # letreiro retroiluminado em branco quente (Render 3: as letras brilham creme sobre a madeira)
    if _m[0] == 'letreiro':
        # Renders 3 e 9: letras em creme quente (meio-termo de intensidade, o bloom do js faz o halo)
        G.MATERIAIS[_i] = ('letreiro', [0, 0, 0, 1], 0.0, 0.5, None,
                           {'emissiveFactor': [1.0, 0.72, 0.45], 'emis': 'logo.png', 'strength': 1.0, 'alphaMode': 'BLEND', 'alpha_img': 'logo.png'})
    # revestimento de ripado da entrada: cedro escuro e quente (Render 10: #352319)
    if _m[0] == 'ripado_cinza':
        # madeira envelhecida cinza-amarronzada (Render 6, 16/10/2026): a cor vem da textura; o fator so esfria um pouco
        G.MATERIAIS[_i] = ('ripado_cinza', [0.93, 0.88, 0.82, 1], 0.0, 0.75, G.tex('ripado_cinza.jpg', 'ripado_cinza_n.jpg'), {})
    if _m[0] == 'painel_acm':
        # fascia da marquise (Render 6): ACM CHAMPANHE acetinado — cinza-areia claro, metalico, com juntas finas escuras
        G.MATERIAIS[_i] = ('painel_acm', G.srgb('#948f84'), 0.5, 0.42, None, {})
    # fundo do corredor visto pela fenda de vidro: aceso em tom quente (Render 3: as placas de vidro
    # da fenda mostram a luz do corredor atras)
    if _m[0] == 'corredor_fundo':
        G.MATERIAIS[_i] = ('corredor_fundo', G.srgb('#4a4238'), 0.0, 0.8, None,
                           {'emissiveFactor': [1.0, 0.66, 0.40], 'emis': 'interior.jpg', 'strength': 0.14})   # 16/10: era 0,9
    if _m[0] == 'ripado_madeira':
        G.MATERIAIS[_i] = ('ripado_madeira', [1, 1, 1, 1], 0.0, 0.7, G.tex('ripado.jpg', 'ripado_n.png'),
                           {'emissiveFactor': [1.0, 0.62, 0.32], 'emis': 'ripado.jpg', 'strength': 1.0})
    if _m[0] == 'movel_claro':
        G.MATERIAIS[_i] = ('movel_claro', G.srgb('#7a6650'), 0.0, 0.85, None, {'emissiveFactor': [1, 0.62, 0.30], 'strength': 0.6})
    # divisorias entre sacadas: cinza-chumbo escuro, nao preto (Render 2)
    if _m[0] == 'aleta':
        G.MATERIAIS[_i] = ('aleta', G.srgb('#2a2a2f'), 0.15, 0.55, None, {})   # caixilhos, perfis e montantes (as paredes passam a 'concreto_cinza')
G.MATERIAIS += [
    # piscina (usuario, 16/10/2026: 'mais vazia, agua mais transparente'): fundo e degraus em pedra grafite CLARA e fosca (o mármore preto sob
    # a agua lia como uma laje preta) + luzinhas bem mais fracas
    ('piscina_fundo', G.srgb('#2c2f33'), 0.0, 0.6, None, {}),
    ('led_agua', G.srgb('#f2d8b0'), 0.0, 0.5, None, {'emissiveFactor': [1.0, 0.72, 0.45], 'strength': 0.9}),
    # muro e embasamento (imagens 14-16 do usuario, 16/10/2026): placas grandes de pedra cinza-chumbo, fosca; sem madeira
    # ALICERCES e muros (usuario, 16/10/2026): 'essa parte dos alicerces esta muito clara, segue o mesmo tom da coluna de pedra com nicho e
    # das laterais em metal preto chumbo, sao lisas sem detalhes' -> UM so material, liso (sem placas, sem juntas, sem textura) e escuro,
    # na mesma familia do metal chumbo (#33363d) e da pedra preta da torre. Fosco: o js tira o reflexo de ceu (vista rasante lia azul-claro)
    ('muro_pedra', G.srgb('#35373c'), 0.0, 0.9, None, {}),
    ('concreto_escuro', G.srgb('#2b2a2d'), 0.0, 0.8, None, {}),   # fundo escuro da sala NE (render 14)
    # sacada (16/10/2026, Renders 6/7 de perto): borda da laje em faixa CLARA champagne-acetinada (ACM) e divisorias/paredes em
    # concreto pintado cinza-medio (medianas do render: #464244 a #4e4d51; as pecas iam todas para 'aleta', escuras)
    # piso da sacada (parte de CIMA da laje): madeira, a mesma do forro e da borda; sem emissao propria (so a luz de ceu e as de dentro)
    ('piso_sacada', [1, 1, 1, 1], 0.0, 0.5, G.tex('madeira_forro.jpg', 'madeira_forro_n.jpg'), {'emissiveFactor': [1.0, 0.72, 0.38], 'emis': 'madeira_forro.jpg', 'strength': 0.30}),
    # divisorias e pilares entre as sacadas (usuario, 16/10/2026): PRETO CHUMBO, igual a barra entre o vidro da sacada e o piso
    # ('guarda_perfil' e 'aleta': #2a2a2f, metal 0,15, rugosidade 0,55) — antes cinza #4e4c4d
    ('concreto_cinza', G.srgb('#2a2a2f'), 0.15, 0.55, None, {}),
    # perfis da guarda de vidro (montantes, corrimao e travessa): grafite escuro, igual ao caixilho da porta ('aleta')
    ('guarda_perfil', G.srgb('#2a2a2f'), 0.15, 0.55, None, {}),                                                        # alvo na tela ~#39332f (divisorias na sombra)
    # forro da marquise (Render 10): reguas estreitas de teca saturada e brilhante
    # 16/10/2026 (Render 6): nogueira escura LACADA — o brilho vem do reflexo do ceu (js: KENV), nao de emissao laranja
    ('forro_marquise', [1, 1, 1, 1], 0.0, 0.28, G.tex('forro_marquise.jpg', 'forro_marquise_n.jpg'),
     {'emissiveFactor': [1.0, 0.62, 0.32], 'emis': 'forro_marquise.jpg', 'strength': 0.10}),
    # fita de LED do monolito: ambar-quente FINA (Render 6), sem o estouro do luz_quente (strength 3)
    ('led_fita', G.srgb('#f2d8b0'), 0.0, 0.5, None, {'emissiveFactor': [1.0, 0.78, 0.50], 'strength': 2.0}),
    # spots embutidos da marquise: pontos branco-quentes pequenos (nos renders: #ffe9c8, sem laranja)
    ('spot_marquise', G.srgb('#f6ecda'), 0.0, 0.4, None, {'emissiveFactor': [1.0, 0.93, 0.78], 'strength': 4.0}),
    # letreiro do monolito: letras em PRATA FOSCA (Render 6 — sem brilho proprio, lidas pela luz do ambiente); halo so leve
    ('letreiro_prata', [0.86, 0.84, 0.80, 1], 0.0, 0.45, None,
     {'emissiveFactor': [1.0, 0.93, 0.82], 'emis': 'logo.png', 'strength': 0.30, 'alphaMode': 'BLEND', 'alpha_img': 'logo.png'}),
    # claraboia (Render 6): vidro ESPELHADO escuro, quase preto — o ceu so aparece de raspao
    ('vidro_claraboia', G.srgb('#101214', 0.90), 0.6, 0.03, None, {'alphaMode': 'BLEND', 'doubleSided': True}),
    ('piso_madeira', [1, 1, 1, 1], 0.0, 0.45, G.tex('madeira_forro.jpg', 'madeira_forro_n.jpg'),
     {'emissiveFactor': [1.0, 0.7, 0.42], 'emis': 'madeira_forro.jpg', 'strength': 0.12}),
    ('portao_escuro', G.srgb('#151517'), 0.3, 0.5, None, {}),
    ('grade_ripada', G.srgb('#1f1d1c'), 0.2, 0.6, G.tex('ripado.jpg'), {}),
    ('vidro_deque', G.srgb('#6c7473', 0.14), 0.0, 0.05, None, {'alphaMode': 'BLEND', 'doubleSided': True}),
    ('facho_luz', [0, 0, 0, 1], 0.0, 1.0, None,
     {'emissiveFactor': [1.0, 0.72, 0.45], 'emis': 'facho.png', 'strength': 0.55, 'alphaMode': 'BLEND', 'alpha_img': 'facho.png'}),
    ('poca_luz', [0, 0, 0, 1], 0.0, 1.0, None,
     {'emissiveFactor': [1.0, 0.80, 0.55], 'emis': 'poca_luz.png', 'strength': 1.4, 'alphaMode': 'BLEND', 'alpha_img': 'poca_luz.png'}),   # o js troca a mistura por ADITIVA (so soma luz, nao escurece o chao)
    ('letras', G.srgb('#f3eee5'), 0.0, 0.5, None, {'emissiveFactor': [1.0, 0.96, 0.9], 'strength': 1.8}),   # letreiro retroiluminado
    # caixilhos das sacadas e corrimao da guarda: aluminio escovado claro (Render 4)
    ('alu_escovado', G.srgb('#8f9093'), 0.9, 0.38, None, {}),
    # molduras das pontas das alas: grafite escuro que reflete o ceu (azulado no R3, quente no R2)
    ('borda_acm', G.srgb('#33363d'), 0.7, 0.32, None, {}),
    # vidro do terreo: transparente, caixilho preto; o interior aceso aparece atras (Renders 5, 7)
    ('vidro_terreo', G.srgb('#1b1b1b', 0.09), 0.0, 0.04, None, {'alphaMode': 'BLEND', 'doubleSided': True}),
    # marquise e platibandas do terreo: ACM preto fosco (Renders 6, 7)
    ('acm_preto', G.srgb('#2a282e'), 0.15, 0.5, None, {}),
    # vidro das portas de correr dos studios: transparente e limpo (nos renders a cortina acesa
    # aparece nitida atras); sem o fresnel do vidro_claro, que deixava a porta leitosa
    ('vidro_porta', G.srgb('#18191a', 0.10), 0.0, 0.04, None, {'alphaMode': 'BLEND', 'doubleSided': True}),
    # fenda de vidro do fim dos corredores: no Twinmotion e 'Reflective glass' (67%); nos renders le
    # como vidro espelhado escuro com os montantes, nao se ve atraves. Quase opaco e refletivo
    # Render 3 de perto (16/10/2026): vidro cinza-claro refletindo o ceu, deixando ver o corredor aceso
    # Render 3 (fenda leste): vidro reflexivo quase opaco em placas, montantes escuros, algumas placas acesas
    ('vidro_corredor', G.srgb('#4b4b4e', 0.95), 0.4, 0.08, None,
     {'alphaMode': 'BLEND', 'doubleSided': True, 'emissiveFactor': [1, 0.82, 0.66], 'emis': 'fenda.png', 'strength': 0.6}),
    # interior do terreo visto pelo vidro: piso escuro e forro/paredes quentes acesos (Render 5)
    # Renders 3 e 9: lobby e lounge bem acesos em ambar atras do vidro
    # 16/10/2026 (Render 6: lobby #5c4631 por tras do vidro, ~2,3x mais claro que antes): interior aceso em ambar quente
    # 16/10/2026: emissao a ~1/3 do que era (1,3 / 2,4 / 0,9 estouravam em BRANCO-creme atras das janelas e dos vaos): ambar quente e suave
    # valores calculados da cor DESEJADA NA TELA (aces.py: #6a4e34 = amber suave = radiancia 0,10 / 0,062 / 0,034 antes da exposicao)
    # 2a passada (usuario: 'bem mais suave'): alvo na tela #5c4631 (lum ~74, o ambar do lobby dos Renders 6/7) — de #775b3f, razao de radiancia 0,68
    ('interior_piso', G.srgb('#2a2622'), 0.0, 0.6, None, {'emissiveFactor': [1.0, 0.62, 0.34], 'strength': 0.037}),
    ('interior_teto', G.srgb('#6a5238'), 0.0, 0.8, None, {'emissiveFactor': [1.0, 0.62, 0.34], 'strength': 0.082}),
    ('interior_parede', G.srgb('#3a2a1c'), 0.0, 0.85, None, {'emissiveFactor': [1.0, 0.62, 0.34], 'strength': 0.075}),   # ambar suave, nao creme nem branco
]
# palmeiras em VERDE vivo (pedido do usuario, 16/10/2026: 'mais verde vivo, mais cheio, mais realista'): excecao da regra da marca
# de nao ter verde, so para esta vegetacao. Dois tons alternados entre as folhas e brilho quente de luminaria de piso por baixo.
G.MATERIAIS += [
    # 16/10/2026 (usuario: 'deixa as folhas mais escuras'): verde-floresta fundo, sem emissao — a luz de ceu (4x) ja clareia
    ('palma_verde', G.srgb('#0f2a0e'), 0.0, 0.7, None, {'doubleSided': True}),
    ('palma_verde2', G.srgb('#1a3a12'), 0.0, 0.65, None, {'doubleSided': True}),
    # variacao folha a folha (16/10/2026): verde um pouco mais vivo, e oliva/seco em algumas folhas velhas
    ('palma_verde3', G.srgb('#27501b'), 0.0, 0.6, None, {'doubleSided': True}),
    ('palma_seca', G.srgb('#4b4a22'), 0.0, 0.75, None, {'doubleSided': True}),
    # tronco MARROM CLARO (usuario, 16/10/2026: 'um marrom mais clarinho'); era quase preto (movel_escuro)
    ('palma_tronco', G.srgb('#7e5f40'), 0.0, 0.85, None, {}),
]
IDX = {nome: i for i, (nome, *_) in enumerate(G.MATERIAIS)}

G.M_PALMA = IDX['palma_verde']; G.M_PALMA2 = IDX['palma_verde2']; G.M_PALMA3 = IDX['palma_verde3']; G.M_PALMA_SECA = IDX['palma_seca']; G.M_TRONCO = IDX['palma_tronco']

MAPA = {
    # pavimento-tipo (nomes do FBX da casca; CASCA-NOVA: para as pecas soltas)
    'aluminium.001': 'guarda_perfil', 'aluminium': 'alu_escovado', 'VIDRO ': 'vidro_porta',   # montantes, travessas e perfil da guarda: escuros (Renders 4 e 9); vidro das portas
    'parede porta': 'aleta', 'aluminium.001_porta': 'aleta',   # caixilho escuro das portas (Render 4)                 # faixa entre o topo da porta e o forro (fechava o vao)
    'Material #2100517301': 'vidro_guarda', 'parede lateral': 'concreto_cinza', 'concreto ': 'concreto_cinza',
    'parede corredor': 'corredor_fundo', 'granito sao gabriel': 'marmore_preto',
    'Porcelanato Calacata': 'piso_sacada', 'área livre': 'madeira_sacada', 'pilar': 'aleta',
    '__cortina__': 'janela_unidade', '__spot__': 'luz_quente',
    # casca
    'brises': 'piso_sacada',              # topo das placas curvas das sacadas (Bare concrete 02)
    'piso mad ripado': 'madeira_sacada',    # forro das sacadas, aceso (forro pvc madeirado)
    'acm borda': 'moldura_metal',           # moldura escura das placas de madeira (Aluminium panels)
    'madeiradoo': 'madeira_painel',         # placas de madeira (Chestnut 01 A): NO, pontas e leste
    'Material #2100517296': 'torre_escada', # torre da escada em fatias + topo (pedra escura)
    'elevadores': 'torre_escada',           # nucleo do canto interno: a lamina escura dos Renders 8-10
    'madeiradoo_ponta': 'madeira_painel', 'acm borda_ponta': 'borda_acm',   # pontas das alas: madeira (Chestnut no Twinmotion, render da ponta leste), moldura clara
    'TELHADO': 'laje_concreto', 'Metal_Galvanized_A_10cm': 'moldura_metal',
    'cinnamon': None, 'Material #2147455081': None,   # letras 3D do FBX saem; letreiro = logo_quad (abaixo)
    'vidro corredor': 'vidro_corredor', 'gesso': 'corredor_fundo',
    # terreo: caixilhos pretos (aluminio preto), vidro transparente, deque de marmore preto, rua de
    # paralelepipedo, base de pedra cinza, marquise de ACM preto com forro de madeira aceso
    'REVIT:cobogo': 'portao_escuro', 'REVIT:.Alumínio': 'aleta', 'TERREO:aluminio preto': 'acm_preto',
    'TERREO:aluminium.002': 'acm_preto', 'TERREO:aluminium.003': 'acm_preto', 'REVIT:aluminium.004': 'aleta',
    'TERREO:Material #2100517293': 'acm_preto', 'TERREO:Material #2100519244': 'portao_escuro',
    'TERREO:Material #2147455183': 'aleta', 'TERREO:tela': 'vidro_deque', 'TERREO:estrutur metal': 'acm_preto',
    'TERREO:vrido': 'vidro_claraboia',
    'TERREO:pedra lago': 'placa_pedra', 'TERREO:agua lago': 'agua', 'TERREO:casca': 'folhagem',
    'TERREO:área livre.001': 'marmore_preto',
    'TERREO:travertino porcelanato': 'marmore_preto',   # deque em volta das piscinas: marmore preto molhado (Render 9); como piso aceso virava uma faixa creme
    'TERREO:Porcelanato BEJE': 'marmore_preto', 'TERREO:granito sao gabriel.001': 'marmore_preto',
    'TERREO:Pastilha Azul claro': 'piscina_fundo', 'TERREO:Material #2147455579': 'marmore_preto',
    'TERREO:venez': None,   # lamas da grelha do FBX (serrilham): viram faixas lisas no interior()
    'TERREO:Material #2100517301.001': 'vidro_terreo',   # vidro solto do lounge noroeste (mesmo numero do vidro da guarda); caia no padrao ambar
    'TERREO:parede': 'muro_pedra', 'TERREO:asfalto': None,   # rampas/rua do FBX: o chao plano do site (js montaChao) faz o papel
    'TERREO:platibanda': 'painel_acm', 'TERREO:forro': 'madeira_sacada', 'REVIT:maddd': 'madeira_painel',
    'TERREO:forro lob': 'madeira_sacada', 'TERREO:CONCRETO LAJE': 'madeira_sacada', 'TERREO:ajuste forro': 'interior_teto',
    'TERREO:Água': 'agua', 'TERREO:Pastilha Azul escuro': 'piscina_fundo', 'TERREO:Grama': None,
    'TERREO:Materparede terreo': 'ripado_cinza', 'TERREO:2parede': 'placa_pedra',
    'TERREO:MDF insta': 'lounge_parede',   # painel de MDF do lounge: madeira quente acesa vista pelo vidro (Render 9), nao a pedra da torre
    'TERREO:laca branca': 'ripado_madeira', 'TERREO:Material #2147455196': 'ripado_madeira', 'TERREO:porta': 'portao_escuro',   # porta de servico do lounge NO: escura (era ripado de madeira aceso, laranja); usuario 16/10/2026: sem madeira na area social
    
    'TERREO:cromo puchador ': 'moldura_metal', 'TERREO:pucgaaa': 'moldura_metal', 'TERREO:mertalll': 'moldura_metal',
    'TERREO:sauna': 'interior_parede', 'TERREO:bem estar': 'ripado_cinza',
    'REVIT:.pintura Externa.001': 'acm_preto', 'REVIT:.pintura Externa': 'ripado_cinza', 'REVIT:.pintura': 'ripado_cinza', 'TERREO:Material #2100519321': 'folhagem',
    'TERREO:Material #2100519323': 'movel_escuro', 'TERREO:Material #2100519336': 'interior_parede',
    'TERREO:parede lateral.001': 'aleta', 'TERREO:TELHADO.001': 'acm_preto', 'TERREO:mad': 'forro_marquise',
    'TERREO:Material #2147455181': 'interior_piso', 'TERREO:Material #2147455182': 'vidro_terreo',
    'TERREO:Material #2147455580': None, 'REVIT:Material #2147483569': 'aleta', 'REVIT:esp': 'interior_parede',
    'REVIT:Material #2147483583': 'folhagem', 'REVIT:Material #2147455209': 'aleta', 'REVIT:-': 'interior_parede', 'TERREO:-': None,
}

FALLBACK = {}   # materiais do FBX sem regra propria (caem no padrao 'interior_parede', ambar aceso): avisados no fim da geracao


def site_mat(m):
    m = str(m)
    if m in MAPA:
        return MAPA[m]
    curto = m.split(':', 1)[-1]
    if curto in MAPA:
        return MAPA[curto]
    if curto.startswith('brises Slot'):
        # borda de 10 cm das placas: a mesma madeira do forro. Decisao do usuario (16/10/2026): 'a parte da sacada e toda
        # amadeirada, tanto borda, quanto em baixo e acima' (a faixa clara dos Renders 6/7 foi tentada e revertida)
        return 'madeira_sacada'
    if 'vidro' in curto.lower() or 'vrido' in curto:
        return 'vidro_terreo' if m.startswith(('TERREO', 'REVIT')) else 'vidro_claro'
    if curto.startswith(('Generic', 'aluminium', 'Metal', 'cromo')):
        return 'aleta'
    if curto.startswith('.pintura'):
        return 'acm_preto'
    if m.startswith(('TERREO', 'REVIT')):
        FALLBACK[m] = FALLBACK.get(m, 0) + 1
        return 'interior_parede'
    return 'parede_escura'


# forros do terreo: a face de BAIXO e o forro (madeira acesa); a de CIMA e a cobertura do bloco
# (ACM preto). O FBX usa um material so para as duas
SPLIT_CIMA = {'TERREO:forro lob', 'TERREO:CONCRETO LAJE', 'TERREO:forro', 'TERREO:mad', 'TERREO:ajuste forro'}
for _m in SPLIT_CIMA:
    MAPA[_m + '__cima'] = 'acm_preto'


# piso de travertino: o mesmo material no deque das piscinas (aberto) e no lounge (coberto). Sob
# um forro e piso aceso do lounge; a ceu aberto, marmore preto molhado (Render 9)
MAPA['__piso_lounge__'] = 'interior_piso'
MAPA.update({'__piso_entrada__': 'marmore_preto', '__rua__': None, '__tampo_marquise__': 'acm_preto', '__ne_parede__': 'concreto_escuro', '__ne_piso__': 'marmore_preto', '__ne_forro__': 'acm_preto', '__muro_sul__': 'muro_pedra', '__plat_preta__': 'acm_preto',
             '__monolito__': 'monolito', '__parede_lobby__': 'interior_parede', '__parede_trav__': 'torre_escada',
             '__piso_lounge_no__': 'piso_madeira', '__granito_v__': 'muro_pedra', '__tampa_muro__': 'muro_pedra',
             '__portao__': 'portao_escuro', '__grade__': None,   # a cerca SE (grade ao redor das palmeiras, ao lado do portao) nao existe (usuario, 16/10/2026)
              '__ne_alu__': 'portao_escuro'})


def cobertos(P, M, alvo, forros, N=None):
    """faces de cima de 'alvo' sob um forro: o centroide (x,z) cai DENTRO de um triangulo de forro com
    pelo menos 1,5 m de folga acima; no lounge NO so dentro da linha do vidro (x>3,86, z>4,25 no site)"""
    f = np.isin(M, list(forros)) & (N.mean(1)[:, 1] < -0.5)
    cand = (M == alvo) & (N.mean(1)[:, 1] > 0.7)
    out = np.zeros(len(M), bool)
    if not f.any() or not cand.any():
        return out
    T = P[f]
    A, B, C = T[:, 0, [0, 2]], T[:, 1, [0, 2]], T[:, 2, [0, 2]]
    yf = T[:, :, 1].mean(1)
    den = (B[:, 1] - C[:, 1]) * (A[:, 0] - C[:, 0]) + (C[:, 0] - B[:, 0]) * (A[:, 1] - C[:, 1])
    ok = np.abs(den) > 1e-9
    for i in np.where(cand)[0]:
        c = P[i].mean(0); x, y, z = c
        xs, zs = x + DESLOCA[0], z + DESLOCA[2]
        if xs < 11.4 and zs < 20.3 and not (xs > 3.86 and zs > 4.25):
            continue
        l1 = ((B[:, 1] - C[:, 1]) * (x - C[:, 0]) + (C[:, 0] - B[:, 0]) * (z - C[:, 1])) / np.where(ok, den, 1)
        l2 = ((C[:, 1] - A[:, 1]) * (x - C[:, 0]) + (A[:, 0] - C[:, 0]) * (z - C[:, 1])) / np.where(ok, den, 1)
        l3 = 1 - l1 - l2
        dentro = ok & (l1 >= 0) & (l2 >= 0) & (l3 >= 0) & (yf - y > 1.5)
        out[i] = dentro.any()
    return out


def prepara(P, N, M):
    """renomeia faces de cima dos forros, remapeia por posicao (cs = centroide em coordenadas do SITE) e
    tira o que esta mapeado para None"""
    M = np.array([str(m) for m in M])
    ns = N.mean(1); up = ns[:, 1] > 0.5
    cs = P.mean(1) + DESLOCA
    # --- deque / lounge NO (lote 7)
    M[cobertos(P, M, 'TERREO:travertino porcelanato', SPLIT_CIMA, N)] = '__piso_lounge__'
    M[(M == 'TERREO:travertino porcelanato') & (np.abs(ns[:, 1]) < 0.3)] = '__parede_trav__'
    M[(M == 'TERREO:Porcelanato BEJE') & (cs[:, 0] > 3.77) & (cs[:, 0] < 11.4) & (cs[:, 2] > 4.2) & (cs[:, 2] < 20.3)] = '__piso_lounge_no__'
    M[(M == 'TERREO:granito sao gabriel.001') & (np.abs(ns[:, 1]) < 0.5)] = '__granito_v__'
    for m in SPLIT_CIMA:
        M[(M == m) & up] = m + '__cima'
    # --- entrada (lote 5): faces 'TERREO:-' que o FBX deixava sem material (buraco no piso, terreno, tampo)
    t_ = (M == 'TERREO:-')
    M[t_ & up & (np.abs(cs[:, 1] - 1.08) < 0.06) & (cs[:, 0] > 44.5) & (cs[:, 0] < 47.3) & (cs[:, 2] > 17.5) & (cs[:, 2] < 34.5)] = '__piso_entrada__'
    M[t_ & up & (cs[:, 1] > 5.4) & (cs[:, 1] < 5.6)] = '__tampo_marquise__'
    # pátio e rua a leste (x > 51,4): o FBX tem rampas de asfalto em varias alturas e faixas de gramado planas que
    # viravam manchas e uma borda diagonal; saem, e o js/fachada3d.js poe um patio plano de paralelepipedo na cota do
    # embarque (1,1) que desce suavemente ate a rua (usuario, 16/10/2026: 'corrija as falhas do piso')
    M[(M == 'TERREO:asfalto') & (cs[:, 0] > 51.4)] = '__rua__'
    M[t_ & up & (cs[:, 1] > 3.5) & (cs[:, 1] < 3.7)] = '__tampa_muro__'
    # muro da divisa sul e cercamentos altos (y > 3,3): 'parede' de pedra no FBX. Eram ripado de madeira (rodada anterior) — o usuario
    # (16/10/2026): 'nao temos partes de madeira na area social que envolve o prédio'; sao PLACAS DE PEDRA como o embasamento
    M[(M == 'TERREO:parede') & (np.abs(ns[:, 1]) < 0.3) & (P[:, :, 1].max(1) + DESLOCA[1] > 3.3)] = '__muro_sul__'
    # fascia da marquise (Render 6): a face LESTE e champanhe; os retornos das pontas (normal em z) sao PRETOS
    M[(M == 'TERREO:platibanda') & (np.abs(ns[:, 2]) > 0.7)] = '__plat_preta__'
    # monolito: parede 'pintura externa' do FBX (x ~44,69), fora do vao da garagem (z>37,74 e y<4,45)
    pint = np.isin(M, ['REVIT:.pintura Externa', 'REVIT:.pintura', 'REVIT:.pintura Externa.001'])
    M[pint & (ns[:, 0] > 0.7) & (cs[:, 0] > 44.5) & (cs[:, 0] < 44.7) & (cs[:, 2] > 31.82) & (cs[:, 2] < 43.19)
      & ((cs[:, 2] < 37.74) | (cs[:, 1] > 4.45))] = '__monolito__'
    # lobby: faces de parede voltadas para dentro do salao
    cp = cs + 0.3 * ns
    dentro = (cp[:, 0] > 24.8) & (cp[:, 0] < 45.5) & (cp[:, 2] > 23.9) & (cp[:, 2] < 35.7) & (cp[:, 1] > 1.1) & (cp[:, 1] < 5.1)
    M[(M == 'TERREO:Materparede terreo') & dentro] = '__parede_lobby__'
    # fechamentos: portao, tela NE e cerca SE
    M[(M == 'REVIT:.Alumínio') & (cs[:, 0] > 41.0) & (cs[:, 2] < 12.0)] = '__ne_alu__'
    M[(M == 'TERREO:tela') & ((cs[:, 0] > 44.0) | (cs[:, 2] > 44.0))] = '__grade__'
    # --- sala do canto NORDESTE (x > 30, z < 12,5; atras da tela de aletas pretas, sob a marquise grande): no render 14 o fundo e ESCURO
    # (cinza-grafite, com um fio quente de luz na borda) — sem madeira e sem o interior aceso. O FBX a trata como lounge/lobby (forro
    # de teca, paredes e piso ambar acesos, tira de madeira no fundo); aqui vira pedra/ACM escuros (usuario, 16/10/2026: 'nao temos
    # partes de madeira na area social que envolve o predio')
    ne = (cs[:, 0] > 30) & (cs[:, 2] < 12.5) & (cs[:, 1] > 0.95) & (cs[:, 1] < 5.7)
    sm = np.array([site_mat(m) for m in M], dtype=object)
    for de, para in (('interior_parede', '__ne_parede__'), ('interior_piso', '__ne_piso__'), ('interior_teto', '__ne_forro__'),
                     ('forro_marquise', '__ne_forro__'), ('madeira_sacada', '__ne_forro__'), ('madeira_painel', '__ne_parede__'),
                     ('piso_madeira', '__ne_piso__'), ('ripado_madeira', '__ne_parede__'), ('ripado_cinza', '__ne_parede__')):
        M[ne & (sm == de)] = para
    keep = np.array([site_mat(m) is not None for m in M])
    return P[keep], N[keep], M[keep]


def uv_caixa(P, N, esc=1 / 3.0):
    """projecao na caixa pelo eixo dominante da normal (como as UVs da maquete)"""
    a = np.abs(N).argmax(-1)
    u = np.where(a == 0, P[..., 2], P[..., 0])
    v = np.where(a == 1, P[..., 2], P[..., 1])
    return np.stack([u, v], -1) * esc


# ---------------------------------------------------------------------------------------------
# Encaixe das sacadas (16/10/2026, Renders 2, 3, 4, 5 e 9). Coordenadas do partes.npz, antes do
# DESLOCA (no site, y + 1,10). No FBX a placa curva (CASCA: 'brises*' + 'piso mad ripado') ficava
# 5 cm abaixo da laje reta de cada pavimento (FAIXA): o forro tinha um degrau, a borda de madeira
# acabava antes das quinas, as divisorias saiam na frente do vidro e a guarda tinha um vao de
# 14 cm em cada divisa de studio. Aqui tudo vira UMA laje por andar.
# ---------------------------------------------------------------------------------------------
# linha externa da laje reta da FAIXA (face externa da mureta) por face:
# (eixo da profundidade, sinal para fora, coordenada da linha, eixo ao longo, faixa de s)
LINHAS_SACADA = {'oeste': (0, -1, -2.275, 2, (-1.2, 38.5)), 'norte': (2, -1, -2.275, 0, (11.0, 42.9)),
                 'sul_barra': (2, +1, 15.275, 0, (18.9, 42.9)), 'leste_haste': (0, +1, 15.275, 2, (14.6, 38.5))}
RECUO_DIV = 0.12     # face externa da divisoria: 12 cm atras da linha, logo atras do vidro da guarda


def _face_sacada(c):
    """face (oeste/norte/sul_barra/leste_haste) de cada centro de triangulo da FAIXA"""
    out = np.full(len(c), '', dtype=object)
    for f, (ed, sg, lin, es, (s0, s1)) in LINHAS_SACADA.items():
        o = (c[:, ed] - lin) * sg; s = c[:, es]
        out[(o > -2.3) & (o < 2.0) & (s > s0) & (s < s1) & (out == '')] = f
    return out


def _caixa(lo, hi, mat):
    """12 triangulos de uma caixa alinhada (normais para fora)"""
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    v = np.array([[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
                  [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]], float)
    quads = [((0, 3, 2, 1), (0, 0, -1)), ((4, 5, 6, 7), (0, 0, 1)), ((0, 4, 7, 3), (-1, 0, 0)),
             ((1, 2, 6, 5), (1, 0, 0)), ((0, 1, 5, 4), (0, -1, 0)), ((3, 7, 6, 2), (0, 1, 0))]
    P, N = [], []
    for (a, b, c, d), n in quads:
        P += [[v[a], v[b], v[c]], [v[a], v[c], v[d]]]; N += [[n] * 3] * 2
    return np.array(P), np.array(N, float), [mat] * 12


def _quad(p0, p1, p2, p3, mat):
    """quad plano; normal pela ordem dos vertices"""
    p = np.array([[p0, p1, p2], [p0, p2, p3]], float)
    # normal pelas diagonais: vale tambem para o quad que degenera em triangulo (ponta da placa)
    nv = np.cross(np.subtract(p2, p0), np.subtract(p3, p1)); nv /= np.linalg.norm(nv)
    return p, np.tile(nv, (2, 3, 1)), [mat] * 2


def _quad_para(p0, p1, p2, p3, mat, quer):
    """quad plano com a normal virada para o lado 'quer'"""
    p, n, m = _quad(p0, p1, p2, p3, mat)
    if np.dot(n[0, 0], quer) < 0:
        p, n, m = _quad(p0, p3, p2, p1, mat)
    return p, n, m


def _ponto(face, s, o, y):
    ed, sg, lin, es, _ = LINHAS_SACADA[face]
    p = [0.0, y, 0.0]; p[ed] = lin + o * sg; p[es] = s
    return p


PE_SACADA = 3.06     # pe-direito do pavimento-tipo (ritmo das placas)
O_INTERNO = -0.395   # borda interna das placas curvas (escondida dentro da laje reta)
# parede de topo de cada face (fim da face, s maximo): a placa encosta nela
PAREDE_TOPO = {'oeste': 38.445, 'norte': 42.775, 'sul_barra': 42.775, 'leste_haste': 38.445}


def _dp(S, O, tol):
    """Douglas-Peucker na curva (s, o)"""
    keep = np.zeros(len(S), bool); keep[[0, -1]] = True
    pilha = [(0, len(S) - 1)]
    while pilha:
        a, b = pilha.pop()
        if b <= a + 1:
            continue
        ds, do = S[b] - S[a], O[b] - O[a]
        L = max(np.hypot(ds, do), 1e-9)
        d = np.abs((S[a + 1:b] - S[a]) * do - (O[a + 1:b] - O[a]) * ds) / L
        i = int(d.argmax())
        if d[i] > tol:
            keep[a + 1 + i] = True; pilha += [(a, a + 1 + i), (a + 1 + i, b)]
    return S[keep], O[keep]


def _curva_placa(s, o):
    """contorno externo de uma placa curva (envelope de o por s) a partir dos vertices do topo"""
    d = {}
    for a, b in zip(np.round(s, 3), o):
        d[a] = max(d.get(a, -9.0), float(b))
    S = np.array(sorted(d)); O = np.array([d[k] for k in S])
    for _ in range(4):   # tira os pontos internos (pecas soltas do FBX abaixo do contorno)
        if len(S) < 3:
            break
        t = (S[1:-1] - S[:-2]) / np.maximum(S[2:] - S[:-2], 1e-9)
        ch = O[:-2] + t * (O[2:] - O[:-2])
        keep = np.ones(len(S), bool); keep[1:-1] = O[1:-1] >= ch - 0.01
        if keep.all():
            break
        S, O = S[keep], O[keep]
    # fim da face: o FBX fecha a placa com uma tampa (o cai ate a borda interna em poucos cm);
    # a tampa sai daqui e e refeita na parede de topo
    j = len(O) - 1
    while j > 0 and O[j] <= O_INTERNO + 0.02:
        j -= 1
    if S[-1] - S[j] < 0.03:
        S, O = S[:j + 1], O[:j + 1]
    O = np.maximum(O, O_INTERNO)
    return _dp(S, O, 0.003)


def placa_limpa(P, N, M):
    """refaz as placas curvas das sacadas (topo, forro, borda de madeira e tampas), uma por face e
    por nivel. O FBX veio so com as faces 'vistas de fora': em varios niveis faltavam trechos do
    forro e da borda (serrilhado com furos na face leste_haste, Render 3) e a borda era inclinada
    (topo deslocado 3..8 cm do pe). Aqui o contorno de cada placa sai dos vertices do topo, a borda
    fica vertical, o forro inteiro e a placa vai ate a parede de topo"""
    placa = np.array([m.startswith('CASCA-NOVA:brises') or m == 'CASCA-NOVA:piso mad ripado' for m in M])
    F = _face_sacada(P.mean(1))
    k = np.round((P.mean(1)[:, 1] - 4.585) / PE_SACADA).astype(int)
    tiraP = placa & (F != '')
    add = []
    for f, (ed, sg, lin, es, _) in LINHAS_SACADA.items():
        for kk in np.unique(k[tiraP & (F == f)]):
            sel = tiraP & (F == f) & (k == kk)
            V = P[sel].reshape(-1, 3)
            ytop0 = 4.66 + PE_SACADA * kk
            top = np.abs(V[:, 1] - ytop0) < 0.003
            if top.sum() < 3:
                tiraP &= ~sel; continue
            S, O = _curva_placa(V[top, es], (V[top, ed] - lin) * sg)
            if S[-1] < PAREDE_TOPO[f]:
                S = np.append(S, PAREDE_TOPO[f]); O = np.append(O, O[-1])
            yb, yt = ytop0 - 0.10, ytop0 + 0.05      # placa 5 cm acima: 4,56..4,71 (+ 3,06 por nivel)
            pt = lambda s_, o_, y_: _ponto(f, s_, o_, y_)
            fora = np.zeros(3); fora[ed] = sg
            ao_longo = np.zeros(3); ao_longo[es] = 1.0
            cima = np.array([0.0, 1.0, 0.0])
            for i in range(len(S) - 1):
                s0, s1, o0, o1 = S[i], S[i + 1], O[i], O[i + 1]
                if max(o0, o1) - O_INTERNO < 0.005:
                    continue
                # topo (laje), forro (madeira) e borda vertical (madeira, normal suavizada no malhas)
                add.append(_quad_para(pt(s0, O_INTERNO, yt), pt(s0, o0, yt), pt(s1, o1, yt), pt(s1, O_INTERNO, yt), 'CASCA-NOVA:brises', cima))
                add.append(_quad_para(pt(s0, O_INTERNO, yb), pt(s1, O_INTERNO, yb), pt(s1, o1, yb), pt(s0, o0, yb), 'CASCA-NOVA:piso mad ripado', -cima))
                add.append(_quad_para(pt(s0, o0, yb), pt(s1, o1, yb), pt(s1, o1, yt), pt(s0, o0, yt), 'CASCA-NOVA:brises Slot #limpa', fora))
            for s_, o_, lado in ((S[0], O[0], -1.0), (S[-1], O[-1], 1.0)):   # tampas das pontas
                if o_ - O_INTERNO > 0.005:
                    add.append(_quad_para(pt(s_, O_INTERNO, yb), pt(s_, o_, yb), pt(s_, o_, yt), pt(s_, O_INTERNO, yt), 'CASCA-NOVA:piso mad ripado', lado * ao_longo))
    Pa, Na, Ma = [P[~tiraP]], [N[~tiraP]], list(M[~tiraP])
    for p, n, mm in add:
        Pa.append(p); Na.append(n); Ma += mm
    print(f'placas curvas: {int(tiraP.sum())} tri do FBX -> {sum(len(a[2]) for a in add)} tri refeitos')
    return np.concatenate(Pa), np.concatenate(Na), np.array(Ma, dtype=object)


def _pilar_fino(P, N, M):
    """pilares das divisas de studio nas sacadas: no terreo continuam inteiros (lounge do Render 9);
    acima do forro do 1o pavimento ficam com a largura da divisoria (8 cm), atras dela, e leem como
    UMA aleta (Render 2: antes saia pilar de 32 cm + divisoria de 14 cm lado a lado)"""
    pil = M == 'CASCA-NOVA:pilar'
    F = _face_sacada(P.mean(1))
    tira = np.zeros(len(P), bool); add = []
    for f, (ed, sg, lin, es, _) in LINHAS_SACADA.items():
        sel = pil & (F == f)
        if not sel.any():
            continue
        cs = P[sel].mean(1)[:, es]
        idx = np.where(sel)[0][np.argsort(cs)]; cs = np.sort(cs)
        grupos = np.split(idx, np.where(np.diff(cs) > 0.5)[0] + 1)
        for g in grupos:
            V = P[g].reshape(-1, 3)
            lo, hi = V.min(0), V.max(0)
            if hi[1] - lo[1] < 20:
                continue
            sc = 0.5 * (lo[es] + hi[es])
            a = lo.copy(); b = hi.copy(); b[1] = 4.56
            add.append(_caixa(a, b, 'CASCA-NOVA:pilar'))
            a = lo.copy(); b = hi.copy(); a[1] = 4.56; a[es] = sc - 0.04; b[es] = sc + 0.04
            add.append(_caixa(a, b, 'CASCA-NOVA:pilar'))
            tira[g] = True
    print(f'pilares das divisas: {int(tira.sum())} tri -> {12 * len(add)} tri')
    Pa, Na, Ma = [P[~tira]], [N[~tira]], list(M[~tira])
    for p, n, mm in add:
        Pa.append(p); Na.append(n); Ma += mm
    return np.concatenate(Pa), np.concatenate(Na), np.array(Ma, dtype=object)


def encaixe_sacada(nome, P, N, M):
    P = P.astype(np.float64).copy(); N = N.astype(np.float64).copy()
    M = np.array([str(m) for m in M], dtype=object)
    if nome == 'CASCA':
        # placa curva 5 cm acima (4,56..4,71): o topo fica rente ao piso da sacada (4,71) e o forro
        # no mesmo plano do forro da laje reta, que sobe junto (FAIXA, abaixo). Refeita inteira,
        # ate a parede de topo de cada face
        P, N, M = placa_limpa(P, N, M)
        P, N, M = _pilar_fino(P, N, M)
        # forro da cobertura sobre o P17 no mesmo ritmo: fecha a fresta de 5 cm
        al = np.array([m in ('CASCA-NOVA:área livre', 'CASCA-NOVA:parede lateral') for m in M])
        Q = P[al]; Q[..., 1] = np.where(np.abs(Q[..., 1] - 56.53) < 0.01, 56.58, Q[..., 1]); P[al] = Q
        return P, N, M
    if nome.startswith('S') and nome[1:].isdigit():
        # spots do forro de cada studio acompanham o forro (+10 cm)
        sp = M == '__spot__'
        Q = P[sp]; Q[..., 1] += 0.10; P[sp] = Q
        return P, N, M
    if nome != 'FAIXA':
        return P, N, M
    # forro da laje reta 4,46 -> 4,56 e topo da laje 7,52 -> 7,62 (divisorias, porta, concreto e
    # parede do corredor acompanham): mesmo plano da placa curva
    y = P[..., 1]
    P[..., 1] = np.where(np.abs(y - 4.46) < 0.005, 4.56, np.where(np.abs(y - 7.52) < 0.005, 7.62, y))
    c = P.mean(1); n = N.mean(1)
    F = _face_sacada(c)
    pl = M == 'parede lateral'
    # borda da laje reta / mureta: todos os vertices a menos de 10,6 cm da linha e abaixo de 4,965
    borda = np.zeros(len(P), bool)
    for f, (ed, sg, lin, es, _) in LINHAS_SACADA.items():
        o = (P[..., ed] - lin) * sg
        borda |= (F == f) & (o.min(1) > -0.106) & (P[..., 1].max(1) < 4.965)
    # face externa da laje reta (4,56..4,71): a mesma madeira da borda da placa curva, ate as quinas
    # (site_mat manda 'brises Slot*' para madeira_sacada, com normal suavizada). A mureta
    # 4,71..4,96 continua aleta: e a faixa escura sob o vidro (Renders 5 e 9)
    nb = 0
    for f, (ed, sg, lin, es, _) in LINHAS_SACADA.items():
        o = (P[..., ed] - lin) * sg
        m = pl & (F == f) & (np.abs(o).max(1) < 0.005) & (P[..., 1].max(1) < 4.715) & (n[:, ed] * sg > 0.7)
        M[m] = 'brises Slot #faixa'; nb += int(m.sum())
    # divisorias entre studios: retas, logo atras do vidro (a guarda e a borda passam inteiras na
    # frente); o pe desce da mureta (4,96) ao piso (4,71). As caixas de 7 cm das PONTAS de cada face
    # continuam rentes a borda: fecham a lateral da sacada
    div = pl & ~borda
    for f, (ed, sg, lin, es, _) in LINHAS_SACADA.items():
        sel = div & (F == f)
        if sel.any():
            sv = P[sel][..., es]; s0, s1 = sv.min(), sv.max()
            div &= ~(sel & ((P[..., es].max(1) <= s0 + 0.075) | (P[..., es].min(1) >= s1 - 0.075)))
    for f, (ed, sg, lin, es, _) in LINHAS_SACADA.items():
        sel = div & (F == f)
        Q = P[sel]
        o = (Q[..., ed] - lin) * sg
        Q[..., ed] = np.where(o > -0.01, lin - RECUO_DIV * sg, Q[..., ed])
        Q[..., 1] = np.where(np.abs(Q[..., 1] - 4.96) < 0.005, 4.71, Q[..., 1])
        P[sel] = Q
    # divisorias: 14 -> 8 cm de largura na frente (Renders 2 e 4: aleta fina), centradas na divisa;
    # os ultimos 45 cm junto da fachada continuam com 14 cm e fecham entre os caixilhos das portas
    # de dois studios (senao a luz do studio vaza pela fresta). O pilar da CASCA acima do terreo
    # fica com a mesma largura, atras dela (_pilar_fino)
    fina = np.zeros(len(P), bool); add = []
    for f, (ed, sg, lin, es, _) in LINHAS_SACADA.items():
        sel = np.where(div & (F == f))[0]
        if not len(sel):
            continue
        cs = P[sel].mean(1)[:, es]; ordem = np.argsort(cs)
        for g in np.split(sel[ordem], np.where(np.diff(cs[ordem]) > 0.5)[0] + 1):
            V = P[g].reshape(-1, 3); sv = V[:, es]; ov = (V[:, ed] - lin) * sg
            a, b = sv.min(), sv.max()
            if not 0.12 < b - a < 0.16:
                continue
            y0, y1 = V[:, 1].min(), V[:, 1].max(); o0 = ov.min(); om = o0 + 0.45
            for (sa, sb), (oa, ob) in (((a, b), (o0, om)), ((a + 0.03, b - 0.03), (om, -RECUO_DIV))):
                lo, hi = _ponto(f, sa, oa, y0), _ponto(f, sb, ob, y1)
                add.append(_caixa(np.minimum(lo, hi), np.maximum(lo, hi), 'parede lateral'))
            fina[g] = True
    nd = int(fina.sum())
    if add:
        P = np.concatenate([P[~fina]] + [a[0] for a in add]); N = np.concatenate([N[~fina]] + [a[1] for a in add])
        M = np.array(list(M[~fina]) + [m for a in add for m in a[2]], dtype=object)
        F = _face_sacada(P.mean(1))
    # guarda continua: vidro + travessas nos vaos de 14 cm das divisas e um perfil no topo
    add = []
    alu_all = M == 'aluminium.001'
    for f, (ed, sg, lin, es, _) in LINHAS_SACADA.items():
        alu = alu_all & (F == f)
        if not alu.any():
            continue
        Q = P[alu]
        alto = (Q[..., 1].max(1) > 6.0) & (Q[..., 1].min(1) < 5.0)   # montantes 4,961..6,031
        ivs = sorted(set((round(float(a.min()), 3), round(float(a.max()), 3)) for a in Q[alto][..., es]))
        mont = []
        for a, b in ivs:
            if mont and a <= mont[-1][1] + 1e-3:
                mont[-1][1] = max(mont[-1][1], b)
            else:
                mont.append([a, b])
        for (a0, a1), (b0, b1) in zip(mont[:-1], mont[1:]):
            if 0.10 < b0 - a1 < 0.20:
                add.append(_quad(_ponto(f, a1, -0.05, 4.961), _ponto(f, b0, -0.05, 4.961), _ponto(f, b0, -0.05, 6.031),
                                 _ponto(f, a1, -0.05, 6.031), 'Material #2100517301'))
                for y0, y1 in ((4.961, 4.99), (5.461, 5.49)):
                    lo, hi = _ponto(f, a1, -0.07, y0), _ponto(f, b0, -0.03, y1)
                    add.append(_caixa(np.minimum(lo, hi), np.maximum(lo, hi), 'aluminium.001'))
        if mont:
            # perfil escuro continuo no topo do vidro (Renders 1, 4 e 9)
            lo, hi = _ponto(f, mont[0][0], -0.08, 6.031), _ponto(f, mont[-1][1], -0.02, 6.066)
            add.append(_caixa(np.minimum(lo, hi), np.maximum(lo, hi), 'aluminium.001'))
    print(f'encaixe FAIXA: {nb} tri de borda, {nd} tri de divisoria refeitos, {len(add)} pecas na guarda')
    if add:
        P = np.concatenate([P] + [a[0] for a in add]); N = np.concatenate([N] + [a[1] for a in add])
        M = np.array(list(M) + [m for a in add for m in a[2]], dtype=object)
    return P, N, M


def uv_forro(nome, P0, N, mats, UV):
    """forro de madeira nas faces oeste e leste_haste: tabuas ao longo da fachada (P0 = coords do npz)"""
    if nome not in ('CASCA', 'FAIXA'):
        return UV
    c = P0.mean(1); hor = np.abs(N.mean(1)[:, 1]) > 0.7
    ns = ((c[:, 0] < 0.5) & (c[:, 2] > -1.5)) | ((c[:, 0] > 12.5) & (c[:, 0] < 17.5) & (c[:, 2] > 14.6))
    m = np.isin(mats, [IDX['madeira_sacada'], IDX['piso_sacada']]) & hor & ns
    UV = UV.copy(); UV[m] = UV[m][..., ::-1]
    return UV


# o site mira CENTRO = (24,5; 22) e tem o chao da rua em CHAO_Y = -2,0 (js/fachada3d.js).
# No FBX a rua (asfalto, 2.400 m2) fica 3,1 m abaixo do deque e a torre centrada em (18,9; 16,7).
DESLOCA = np.array([24.5 - 18.85, -2.0 - (-3.1), 22.0 - 16.65])


def malhas(nome, P, N, M, dy=0.0):
    """triangulos -> lista de G.Mesh (cada uma < 65k vertices por material)"""
    P, N, M = encaixe_sacada(nome, P, N, M)
    P, N, M = prepara(P, N, M)
    P = P + DESLOCA; P[..., 1] -= dy
    if nome == 'TERREO':
        # nada do terreo pode passar da laje do 1o pavimento (underside em Y = Y_1O_PAV, cota do site): as paredes
        # de ripado, o interior e o monolito do FBX subiam ate 6,7 m e tampavam a sacada do 1o andar (usuario, 16/10/2026).
        # So as pecas baixas (a torre da escada e os nucleos sobem alem: nao mexe)
        baixo = P[:, :, 1].max(1) < 8.0
        P[baixo, :, 1] = np.minimum(P[baixo, :, 1], Y_1O_PAV)
    mats = np.array([IDX[site_mat(m)] for m in M])
    UV = uv_caixa(P, N)
    UV = uv_forro(nome, P - DESLOCA, N, mats, UV)
    # --- muro e embasamento (16/10/2026): o screen/muro do FBX que flutua (embaixo em y 0,9) desce ate o embasamento; sem isso ha
    # um vao de ~0,9 m entre ele e o chao que desceu. So as pontas em y ~0,9 de faces verticais de 'muro_pedra'
    mp = (mats == IDX['muro_pedra']) & (np.abs(N.mean(1)[:, 1]) < 0.3)
    flut = mp & (P[:, :, 1].min(1) > 0.88) & (P[:, :, 1].min(1) < 0.93)
    if flut.any():
        sub = P[flut]; sub[(sub[:, :, 1] < 0.93)] = sub[(sub[:, :, 1] < 0.93)] * np.array([1, 0, 1]) + np.array([0, -1.96, 0]); P[flut] = sub
        mp = (mats == IDX['muro_pedra']) & (np.abs(N.mean(1)[:, 1]) < 0.3)
    # placas de 0,60 m em fiadas que alinham com a grelha (y 0,85 = topo da grelha; fiada em 0,25 / 0,85 / 1,45 / 2,05...)
    ax_ = np.abs(N).argmax(-1)
    if mp.any():
        UV[mp, :, 1] = ((P[:, :, 1] - 0.85) / 3.0)[mp]
    marm = mats == IDX['marmore_preto']
    UV[marm] *= 3.0                                  # veios do marmore legiveis no deque e na piscina
    # placas de madeira: tabuas VERTICAIS e estreitas (~15 cm), como nos renders — a textura
    # empilha as tabuas ao longo de v, entao v corre ao longo da parede e u ao longo da altura
    # Render 3 (16/10/2026): tabuas irregulares de ~0,3 m em media (10 por ladrilho de 3 m)
    pan = np.char.find(M.astype(str), 'madeiradoo') >= 0
    UV[pan] = UV[pan][..., ::-1]
    UV[mats == IDX['madeira_painel']] *= 0.5         # ladrilho de 6 m, 20 tabuas (texturas.madeira_painel)
    # ripado da entrada / cerca SE: tabuas em pe (u = altura, v = largura), 1,5 m por ladrilho
    ax = np.abs(N).argmax(-1); hor = np.where(ax == 0, P[..., 2], P[..., 0])
    for nm_, esc_ in (('ripado_cinza', 1.5), ('grade_ripada', 1.6)):
        rp = (mats == IDX[nm_]) & ((ax == 1).sum(1) == 0)      # faces verticais voltadas a leste/oeste OU norte/sul (antes so leste/oeste: o muro sul saia com tabuas deitadas)
        if rp.any():
            UV[rp] = np.stack([P[..., 1] / 3.0, hor / esc_], -1)[rp]
    # fenda de vidro (placas empilhadas): v = 0 no topo (fenda.png), u ao longo da largura
    fd = (mats == IDX['vidro_corredor'])
    if fd.any():
        u_ = np.where(ax == 0, (P[..., 2] - 11.07) / 1.55, (P[..., 0] - 11.37) / 2.45)
        UV[fd] = np.stack([u_, 1 - (P[..., 1] - 5.66) / 52.17], -1)[fd]
    # borda curva das placas das sacadas: normais suavizadas (a faixa de 10 cm vinha facetada,
    # cada segmento com um tom, e a curva lia 'quebrada')
    borda = np.char.find(M.astype(str), 'brises Slot') >= 0
    if borda.any():
        Pb = P[borda]
        fn = np.cross(Pb[:, 1] - Pb[:, 0], Pb[:, 2] - Pb[:, 0])
        fn /= np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-9)
        fn = fn * np.sign((fn * N[borda].mean(1)).sum(1, keepdims=True))
        chave = np.round(Pb.reshape(-1, 3), 3)
        uniq, inv = np.unique(chave, axis=0, return_inverse=True)
        soma = np.zeros((len(uniq), 3)); np.add.at(soma, inv.reshape(-1), np.repeat(fn, 3, axis=0))
        soma /= np.maximum(np.linalg.norm(soma, axis=1, keepdims=True), 1e-9)
        Nb = N.copy(); Nb[borda] = soma[inv.reshape(-1)].reshape(-1, 3, 3); N = Nb
    cort = np.array([str(m) == '__cortina__' for m in M])
    if cort.any():   # cortina: a textura inteira no vao (tri 0-1-2 e 0-2-3 de um quad)
        q = np.array([[[0, 0], [1, 0], [1, 1]], [[0, 0], [1, 1], [0, 1]]], float)
        UV[cort] = np.tile(q, (cort.sum() // 2, 1, 1))
    # frente do triangulo = lado da normal (como G.Mesh.add): o Three.js descarta o verso
    fn = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    vira = (fn * N.sum(1)).sum(1) < 0
    for A in (P, N, UV):
        A[vira, 1], A[vira, 2] = A[vira, 2].copy(), A[vira, 1].copy()
    saida = []
    for mi in np.unique(mats):
        s = mats == mi
        p, n, uv = P[s].reshape(-1, 3), N[s].reshape(-1, 3), UV[s].reshape(-1, 2)
        chave = np.concatenate([np.round(p, 4), np.round(n, 3), np.round(uv, 4)], 1)
        uniq, inv = np.unique(chave, axis=0, return_inverse=True)
        inv = inv.reshape(-1)
        idx = inv.reshape(-1, 3)
        # fatia por blocos de triangulos ate caber em 16 bits
        ini = 0
        while ini < len(idx):
            fim = len(idx)
            while True:
                bloco = idx[ini:fim]
                usados = np.unique(bloco)
                if len(usados) < 65000:
                    break
                fim = ini + (fim - ini) // 2
            remap = -np.ones(len(uniq), np.int64); remap[usados] = np.arange(len(usados))
            m = G.Mesh()
            m.prims[int(mi)] = (uniq[usados, :3].tolist(), uniq[usados, 3:6].tolist(),
                                uniq[usados, 6:8].tolist(), remap[bloco].reshape(-1).tolist())
            saida.append(m)
            ini = fim
    # junta materiais pequenos numa malha so (menos nos)
    juntas, m_cur, nv = [], G.Mesh(), 0
    for m in saida:
        (mi, pr), = m.prims.items()
        if nv + len(pr[0]) < 65000 and mi not in m_cur.prims:
            m_cur.prims[mi] = pr; nv += len(pr[0])
        else:
            if m_cur.prims: juntas.append(m_cur)
            m_cur, nv = G.Mesh(), len(pr[0]); m_cur.prims[mi] = pr
    if m_cur.prims: juntas.append(m_cur)
    return juntas


# TERRENO (16/10/2026) — do DWG do arquiteto (CINNAMON-35-email.dwg, prancha TERREO/LOCACAO, set/2026): piso do terreo = 0,00 (y 1,05 no site);
# calcada ao redor em -0,02..-0,05 nos lados LESTE (Avenida Parque), SUL e OESTE (Rua-05) — 'NAO HAVERA DESNIVEL COM A CALCADA VIZINHA' —; so o
# lado NORTE (orla) cai: -1,14 no canto NE e -1,74 no NO, com 'parede de contencao' e 'gradil de ventilacao vertical' dos subsolos (o muro de pedra
# com a grelha). Planta -> site: x_site = x_dwg - 0,5; z_site = 47,9 - y_dwg. Cotas do DWG + 1,05 = y do site. O js/fachada3d.js le estes numeros
# do .glb (extras.terreno): fonte unica. AJUSTAR: o DWG so da as cotas dos cantos e nao diz onde a queda comeca (zN1).
TERRENO = {'chaoL': 1.0, 'zN0': -0.9, 'zN1': 24.0, 'gNO': -0.69, 'gNL': -0.09, 'xO': -2.5, 'xL': 54.4}


def chao_h(x, z):
    t = min(1.0, max(0.0, (TERRENO['zN1'] - z) / (TERRENO['zN1'] - TERRENO['zN0']))); t = t * t * (3 - 2 * t)
    u = min(1.0, max(0.0, (x - TERRENO['xO']) / (TERRENO['xL'] - TERRENO['xO'])))
    gn = TERRENO['gNO'] + (TERRENO['gNL'] - TERRENO['gNO']) * u
    return TERRENO['chaoL'] + (gn - TERRENO['chaoL']) * t


Y_1O_PAV = 5.66   # underside da laje de sacada do 1o pavimento (cota do site); o terreo nao passa daqui
LOGO_ASPECTO = 2048 / 487   # logo.png (CINNAMON + STUDIO)


NICHOS = []
ALT_DEQUE = lambda x, z: 1.1


def porta_2_folhas(P, N, M):
    """a porta de correr do FBX tem 4 vidros (duas folhas de 2 vidros, com um montante a ~24% e outro a ~76% da largura, alem do
    encontro central e das laterais). O projeto/usuario (16/10/2026): 'a porta da sacada so tem uma divisao, no encontro central
    onde se fecham; do chao ao teto e vidro'. Sai o montante intermediario de cada folha e o vidro externo de cada folha cobre a folha
    inteira. Posicoes relativas a largura do vidro (u): montantes em 0,226-0,260 e 0,743-0,777; centro em 0,484-0,517."""
    M = np.array([str(m) for m in M]); P = P.copy()
    g = M == 'VIDRO '
    if not g.any():
        return P, N, M
    G_ = P[g].reshape(-1, 3)
    ext = G_.max(0) - G_.min(0)
    ax = 0 if ext[0] > ext[2] else 2
    g0, W = G_[:, ax].min(), G_[:, ax].max() - G_[:, ax].min()
    u = (P[:, :, ax] - g0) / W
    umin, umax = u.min(1), u.max(1)
    fora = np.zeros(len(P), bool)
    # montantes intermediarios (caixilho) e vidros internos de cada folha
    fora |= (M == 'aluminium.001_porta') & (umin >= 0.215) & (umax <= 0.268)
    fora |= (M == 'aluminium.001_porta') & (umin >= 0.732) & (umax <= 0.785)
    fora |= g & (umin >= 0.255) & (umax <= 0.492)          # vidro interno da folha 1
    fora |= g & (umin >= 0.508) & (umax <= 0.745)          # vidro interno da folha 2
    # vidro externo: estica ate a face do montante central
    v1 = g & ~fora & (umax <= 0.25)
    v2 = g & ~fora & (umin >= 0.75)
    for sel, alvo, perto in ((v1, 0.484, 0.226), (v2, 0.517, 0.777)):
        for i in np.where(sel)[0]:
            m_ = np.abs(u[i] - perto) < 0.012
            P[i, m_, ax] = g0 + alvo * W
    return P[~fora], N[~fora], M[~fora]


PISO = []              # triangulos de piso do terreo (site), para a altura real do chao
OBST = None            # paredes/pilares verticais solidos do terreo (segmentos em xz + faixa de y), preenchido no main()
VEG = {'ok': 0, 'movido': 0, 'reduzido': 0, 'removido': 0}


def constroi_obst(Pt, Nt, Mt):
    """segmentos (xz) das faces VERTICAIS e SOLIDAS do terreo, nas coordenadas do site: paredes, pilares, postes, muro, grelha.
    Vidro, agua, folhagem e pisos nao contam. Serve para a checagem das touceiras (usuario, 16/10/2026: 'alguns matinhos estao
    dentro da parede')."""
    global OBST
    salva = dict(FALLBACK)
    P2, N2, M2 = prepara(Pt, Nt, Mt)
    FALLBACK.clear(); FALLBACK.update(salva)
    P2 = P2 + DESLOCA
    sm = np.array([site_mat(q) for q in M2], dtype=object)
    FALLBACK.clear(); FALLBACK.update(salva)
    livres = ['vidro_terreo', 'vidro_deque', 'vidro_claro', 'vidro_guarda', 'vidro_porta', 'vidro_claraboia', 'vidro_corredor',
              'agua', 'folhagem', 'interior_piso', 'paralelepipedo', 'piso_madeira', 'vitrine_terreo', 'palma_verde', 'palma_verde2']
    vert = np.abs(N2.mean(1)[:, 1]) < 0.3
    ok = vert & ~np.isin(sm, livres) & (P2[:, :, 1].max(1) > 1.0)
    T = P2[ok]
    a = np.zeros((len(T), 2)); b = np.zeros((len(T), 2))
    for i, t in enumerate(T):
        xz = t[:, [0, 2]]
        d = [(np.linalg.norm(xz[p] - xz[q]), p, q) for p in range(3) for q in range(p + 1, 3)]
        _, p, q = max(d)
        a[i], b[i] = xz[p], xz[q]
    OBST = {'a': a, 'b': b, 'ymin': T[:, :, 1].min(1), 'ymax': T[:, :, 1].max(1), 'mat': sm[ok]}
    # pisos: faces voltadas para cima entre y 0,95 e 2,6 (deque, calcadas, canteiros); piscina (fundo a 0,5) e agua ficam de fora
    up = (N2.mean(1)[:, 1] > 0.8) & (P2[:, :, 1].mean(1) > 0.95) & (P2[:, :, 1].mean(1) < 2.6) & ~np.isin(sm, ['agua', 'folhagem', 'vidro_terreo', 'vidro_deque', 'vidro_claro'])
    PISO.clear(); PISO.append(P2[up])
    print(f'obstaculos para a vegetacao: {len(T)} faces verticais')


def chao_em(x, z):
    """altura do piso do FBX em (x, z) (maior face voltada para cima que contem o ponto); None se nao houver piso"""
    if not PISO or len(PISO[0]) == 0:
        return None
    T = PISO[0]
    bb = (T[:, :, 0].min(1) <= x) & (T[:, :, 0].max(1) >= x) & (T[:, :, 2].min(1) <= z) & (T[:, :, 2].max(1) >= z)
    melhor = None
    for t in T[bb]:
        (x0, y0, z0), (x1, y1, z1), (x2, y2, z2) = t
        den = (z1 - z2) * (x0 - x2) + (x2 - x1) * (z0 - z2)
        if abs(den) < 1e-9:
            continue
        l0 = ((z1 - z2) * (x - x2) + (x2 - x1) * (z - z2)) / den
        l1 = ((z2 - z0) * (x - x2) + (x0 - x2) * (z - z2)) / den
        if l0 >= -1e-6 and l1 >= -1e-6 and 1 - l0 - l1 >= -1e-6:
            yy = (y0 + y1 + y2) / 3
            melhor = yy if melhor is None else max(melhor, yy)
    return melhor


def _indice_folga(x, z, a, b):
    ab = b - a
    den = np.maximum((ab ** 2).sum(1), 1e-9)
    t = np.clip(((np.array([x, z]) - a) * ab).sum(1) / den, 0, 1)
    cp = a + ab * t[:, None]
    return int(np.hypot(cp[:, 0] - x, cp[:, 1] - z).argmin())


def _folga(x, z, a, b):
    ab = b - a
    den = np.maximum((ab ** 2).sum(1), 1e-9)
    t = np.clip(((np.array([x, z]) - a) * ab).sum(1) / den, 0, 1)
    cp = a + ab * t[:, None]
    dist = np.hypot(cp[:, 0] - x, cp[:, 1] - z)
    i = int(dist.argmin())
    return float(dist[i]), cp[i]


def veg(x, y, z, r, h, minimo=0.22, margem=0.06):
    """(x, y, z, r) da touceira ajustados: y = piso real do FBX em (x, z) (se nao ha piso, a touceira boiaria: removida); afasta ate 0,5 m
    de paredes/pilares e/ou reduz o raio para NAO atravessa-los; None se nao couber."""
    if OBST is None or len(OBST['a']) == 0:
        return x, y, z, r
    # piscinas (usuario: 'deixa a piscina mais vazia'): sem plantas dentro nem na borda (0,6 m)
    for (px0, pz0, px1, pz1) in ((0.47, 0.13, 11.32, 4.03), (0.47, 0.13, 3.57, 19.87)):
        if px0 - 0.6 <= x <= px1 + 0.6 and pz0 - 0.6 <= z <= pz1 + 0.6:
            VEG['removido'] += 1
            return None
    yc = chao_em(x, z)
    if yc is not None:
        y = yc + 0.01
    elif PISO:
        VEG['removido'] += 1
        if os.environ.get('VEG_DEBUG'):
            print(f'  sem piso: ({x:.2f}, {z:.2f})')
        return None
    sel = (OBST['ymax'] > y + 0.05) & (OBST['ymin'] < y + h)
    a, b = OBST['a'][sel], OBST['b'][sel]
    if len(a) == 0:
        VEG['ok'] += 1
        return x, y, z, r
    d, cp = _folga(x, z, a, b)
    if d >= r + margem:
        VEG['ok'] += 1
        return x, y, z, r
    d0 = d; x0, z0 = x, z
    for _ in range(4):
        v = np.array([x - cp[0], z - cp[1]]); n = np.linalg.norm(v)
        v = v / n if n > 1e-6 else np.array([1.0, 0.0])
        passo = min(r + margem - d + 0.02, 0.5 - float(np.hypot(x - x0, z - z0)))
        if passo <= 0.01:
            break
        xn, zn = x + v[0] * passo, z + v[1] * passo
        yn = chao_em(xn, zn)
        if yn is None or abs(yn - y) > 0.3:          # nao sai do piso (nem cai na piscina)
            break
        x, z = xn, zn
        d, cp = _folga(x, z, a, b)
        if d >= r + margem:
            break
    movido = np.hypot(x - x0, z - z0) > 0.02
    r_ef = min(r, d - margem)
    if r_ef >= minimo:
        VEG['movido' if movido and r_ef >= r - 1e-6 else 'reduzido'] += 1
        return x, y, z, r_ef
    VEG['removido'] += 1
    if os.environ.get('VEG_DEBUG'):
        j = _indice_folga(x0, z0, a, b)
        print(f'  removida: ({x0:.2f}, y {y:.2f}, {z0:.2f}) r={r} folga_inicial={d0:.2f} perto de {OBST["mat"][sel][j]} y {OBST["ymin"][sel][j]:.2f}..{OBST["ymax"][sel][j]:.2f}')
    return None


def tufo_seguro(m, x, y, z, h, r, folhas, seed):
    res = veg(x, y, z, r, h)
    if res is None:
        return
    G.tufo(m, res[0], res[1], res[2], h=h, r=res[3], folhas=folhas, seed=seed)


def interior(m):
    """caixas dos moveis (coordenadas do FBX -> site), mobiliario e palmeiras da cena Twinmotion"""
    AQUI = os.path.dirname(os.path.abspath(__file__))
    X0, Y1 = 6.175, 41.465
    def site(lo, hi):
        return ((lo[0] - X0 + DESLOCA[0], lo[2] + DESLOCA[1], Y1 - hi[1] + DESLOCA[2]),
                (hi[0] - X0 + DESLOCA[0], hi[2] + DESLOCA[1], Y1 - lo[1] + DESLOCA[2]))
    MAT_FBX = {'SOFAS': 'movel_claro', 'MDF': 'movel_escuro', 'EQUIPAMENTOS': 'moldura_metal', 'LUMINARIAS': 'luz_quente'}
    # dados fixos (nao saem do FBX da casca): ao lado do script, em dados/
    DADOS = os.path.join(AQUI, 'dados')
    cx = json.load(open(os.path.join(DADOS, 'caixas_interior.json')))
    n = 0
    for c in cx:
        lo, hi = site(c['lo'], c['hi'])
        d = [hi[i] - lo[i] for i in range(3)]
        if d[0] * d[1] * d[2] < 0.15 or d[0] > 20 or d[2] > 20 or lo[1] > 6:
            continue
        if c['fbx'] == 'LUMINARIAS' and d[0] * d[2] > 1.0:
            continue                           # a placa de luz do forro do lounge vira grade de spots (abaixo)
        if c['fbx'] == 'LUMINARIAS':          # luminarias: so o corpo aceso, fino
            lo = (lo[0], max(lo[1], hi[1] - 0.12), lo[2])
        m.box(IDX[MAT_FBX[c['fbx']]], lo, hi, uvscale=0.5); n += 1
    # mobiliario do Twinmotion: caixas genericas por tipo (posicao = pivo do objeto no chao)
    TAM = {'cadeira': (0.6, 0.85, 0.6, 'movel_escuro'), 'CADEIRA DE SOL': (0.65, 0.35, 1.9, 'movel_escuro'),
           'cadeira tela': (0.6, 0.8, 0.6, 'movel_escuro'), 'mesa': (0.8, 0.72, 0.8, 'movel_escuro'),
           'ombrelone': (0.1, 2.4, 0.1, 'moldura_metal'), 'MESINHA': (0.5, 0.45, 0.5, 'movel_escuro'),
           'jogo tram': (1.8, 0.75, 0.9, 'cesto_rattan'), 'cad tram': (0.7, 0.8, 0.7, 'cesto_rattan'),
           'mesa tram': (0.7, 0.45, 0.7, 'cesto_rattan'), 'CHAISE': (0.75, 0.5, 1.9, 'movel_claro'),
           'Cachepot': (0.5, 0.6, 0.5, 'movel_escuro'), 'costela': (0.9, 1.6, 0.9, 'folhagem')}
    mob = json.load(open(os.path.join(DADOS, 'mobiliario_tm.json')))
    palmas = 0
    for o in mob:
        x, y, z = o['site']; nome = o['nome']
        if not (-12 < x < 62 and -12 < z < 55 and y > -2.5):
            continue
        # nada dentro da agua das piscinas (as 'cadeira tela piscina' ficavam submersas)
        if (0.47 < x < 11.32 and 0.13 < z < 4.03) or (0.47 < x < 3.57 and 0.13 < z < 19.87):
            continue
        if nome in ('Canary Date Palm', 'Indian Sandalwood', 'Golden Bamboo'):
            # palmeira/arvore: tronco fino e copa cheia de folhas arqueadas, tom neutro escuro (paleta: nada de verde)
            if nome == 'Canary Date Palm':
                interna = 21.5 < z < 24.5   # patio entre as alas: copa so ate a altura do vidro da sacada do 1o andar (usuario, 16/10/2026)
                if interna:
                    G.palmeira(m, x, y, z, 4.7, seed=palmas, baixa=True)   # tronco ate y ~5,8; as folhas sobem no maximo 1,0 m (-> ~6,8 = topo do vidro da sacada do 1o andar)
                else:
                    G.palmeira(m, x, y, z, 8.5, seed=palmas)
            elif nome == 'Indian Sandalwood':
                continue   # arbusto oliva embolado: removido (usuario, 16/10/2026)
            elif nome == 'Golden Bamboo':
                continue   # idem
            else:
                G.cilindro(m, IDX['movel_escuro'], x, z, 0.08, y, y + 5.0, seg=8)
                tufo_seguro(m, x, y + 4.2, z, 0.96, 1.44, 24, palmas)
            palmas += 1
            continue
        if nome == 'Pickup':
            continue                                  # a caixa lia como bloco rosa/cinza
        if nome.startswith('costela'):
            tufo_seguro(m, x, y, z, 1.8, 1.0, 22, 300 + n); n += 1
            continue
        if nome.startswith('CHAISE'):                 # daybed redondo (Render 9)
            G.cilindro(m, IDX['cesto_rattan'], x, z, 0.95, y, y + 0.45, seg=16)
            m.box(IDX['movel_claro'], (x - 0.75, y + 0.45, z - 0.45), (x + 0.75, y + 0.57, z + 0.45)); n += 1
            continue
        for k, (w, h, d, mat) in TAM.items():
            if nome.startswith(k):
                m.box(IDX[mat], (x - w / 2, y, z - d / 2), (x + w / 2, y + h, z + d / 2)); n += 1
                break
    # renque de agaves na borda do deque, lados norte e oeste (Renders 1 e 2): touceiras escuras
    k = 0
    for x in np.arange(1.0, 47.5, 1.6):
        tufo_seguro(m, float(x), ALT_DEQUE(float(x), 0.3), -0.1, 1.35, 0.8, 14, 100 + k); k += 1
    for zz in np.arange(2.0, 43.0, 1.6):
        tufo_seguro(m, -0.1, ALT_DEQUE(0.3, float(zz)), float(zz), 1.35, 0.8, 14, 100 + k); k += 1
    # letreiro da quina noroeste: centrado no painel de madeira (X 0,9..10,9), na altura do 2o
    # pavimento, 6 m de largura, retroiluminado (Renders 1, 5, 10). logo.png tem CINNAMON + STUDIO
    # centrado na largura real da madeira na altura dele (x 3,66..10,92): CINNAMON em x 10,67..4,20
    G.logo_quad(m, (10.68, 8.49, 3.98), (0, 0, -1), 6.55, 6.55 / LOGO_ASPECTO)
    # letreiro no alto da ponta leste da barra (Renders 8-10; na cena Twinmotion: 'Cinnamon logo' em
    # (48,5; 57,4; 5,3), com luz por tras), virado para a Avenida Parque
    # Render 3 (16/10/2026): no alto da placa norte, puxado para a borda de fora (centro a ~55% da
    # largura a partir da fenda), ~1,4 m abaixo do topo, ~64% da largura da placa. Proporcao do
    # logo.png (antes saia espremido na horizontal e lia como letra grossa)
    G.logo_quad(m, (48.66, 56.7, 9.4), (1, 0, 0), 6.6, 6.6 / LOGO_ASPECTO)

    # ---------------- lote 4: fachada ----------------
    # fundo dos nichos da torre de pedra (o extrai.py descartou essas faces): rasgos pretos
    for (y0, y1) in NICHOS:
        G._q(m, IDX['janela_escada'], [(16.33, y0, 2.92), (14.37, y0, 2.92), (14.37, y1, 2.92), (16.33, y1, 2.92)], (0, 0, -1))
    # tampa de metal no alto da fenda leste
    m.box(IDX['moldura_metal'], (48.0, 58.1, 11.07), (48.45, 59.5, 12.62))
    # (os fachos de luz no pe das placas de madeira da parede leste foram TIRADOS a pedido do usuario, 16/10/2026)

    # ---------------- lote 5: terreo da entrada ----------------
    # AJUSTAR: posicoes dos spots lidas dos Renders 6, 7 e 10 (nao estao no FBX)
    LQ = IDX['luz_quente']
    spots = [(53.30, z) for z in np.arange(0.4, 35.2, 2.8)]
    spots += [(46.9, z) for z in list(np.arange(12.0, 25.0, 2.8)) + [33.3, 34.9]]
    spots += [(50.1, 25.2), (50.1, 33.0)]
    SPM = IDX['spot_marquise']
    for x, z in spots:
        m.box(SPM, (x - 0.05, 4.905, z - 0.05), (x + 0.05, 4.918, z + 0.05))
        # halo do spot na madeira do forro (nogueira lacada acende em volta do ponto) e poca suave no piso
        G._q(m, IDX['poca_luz'], [(x - 0.38, 4.9, z - 0.38), (x + 0.38, 4.9, z - 0.38), (x + 0.38, 4.9, z + 0.38), (x - 0.38, 4.9, z + 0.38)], (0, -1, 0))
        # poca de luz NO CHAO (usuario, 16/10/2026: 'chapadas e fora do chao'): altura por vertice = piso real do FBX ou terreno, +1 cm; maior e mais fraca
        def _yp(px, pz):
            yc = chao_em(px, pz)
            return (yc if yc is not None else chao_h(px, pz)) + 0.012
        R_ = 0.95
        G._q(m, IDX['poca_luz'], [(x - R_, _yp(x - R_, z - R_), z - R_), (x + R_, _yp(x + R_, z - R_), z - R_), (x + R_, _yp(x + R_, z + R_), z + R_), (x - R_, _yp(x - R_, z + R_), z + R_)], (0, 1, 0))
    for z in [zz for (xx, zz) in spots if xx == 46.9 and zz < 32.0]:
        G._q(m, IDX['lavagem_luz'], [(45.73, 4.85, z - 0.5), (45.73, 4.85, z + 0.5), (45.73, 2.45, z + 0.5), (45.73, 2.45, z - 0.5)], (1, 0, 0))
    # juntas de 2,4 cm da borda da marquise a cada 2,5 m
    AL = IDX['aleta']
    for k in range(1, 15):
        z = -0.8 + k * 2.5
        if z > 35.8: break
        G._q(m, AL, [(54.53, 4.9, z - 0.012), (54.53, 4.9, z + 0.012), (54.53, 5.7, z + 0.012), (54.53, 5.7, z - 0.012)], (1, 0, 0))
    for k in range(1, 4):
        x = 45.8 + k * 2.5
        if x > 54.5: break
        G._q(m, AL, [(x - 0.012, 4.9, 35.83), (x + 0.012, 4.9, 35.83), (x + 0.012, 5.7, 35.83), (x - 0.012, 5.7, 35.83)], (0, 0, 1))
    # claraboia: faixa preta em volta do vao e quatro paredes de poco
    AP = IDX['acm_preto']
    cx0, cx1, cz0, cz1 = 47.9, 52.3, 25.91, 32.24
    for (ax_, bx_, az_, bz_) in ((cx0 - 0.5, cx1 + 0.5, cz0 - 0.5, cz0), (cx0 - 0.5, cx1 + 0.5, cz1, cz1 + 0.5),
                                 (cx0 - 0.5, cx0, cz0, cz1), (cx1, cx1 + 0.5, cz0, cz1)):
        G._q(m, AP, [(ax_, 4.915, az_), (bx_, 4.915, az_), (bx_, 4.915, bz_), (ax_, 4.915, bz_)], (0, -1, 0))
    for (p0, p1, nn) in (((cx0, cz0), (cx1, cz0), (0, 0, 1)), ((cx1, cz0), (cx1, cz1), (-1, 0, 0)),
                         ((cx1, cz1), (cx0, cz1), (0, 0, -1)), ((cx0, cz1), (cx0, cz0), (1, 0, 0))):
        G._q(m, AP, [(p0[0], 4.92, p0[1]), (p1[0], 4.92, p1[1]), (p1[0], 5.40, p1[1]), (p0[0], 5.40, p0[1])], nn)
    # monolito (Renders 6 e 10): painel de pedra rustica de y 1,1 a 4,45 (YT) com fita de LED FINA (3 cm) no topo e na borda
    # do lado do lobby, brilho suave dela na pedra (para baixo) e nas ripas de cima (para cima); acima da fita a parede
    # e de ripado envelhecido ate a laje do 1o pavimento; letreiro oficial em prata fosca a ~38% da altura (z 32,75..36,65)
    YT = 4.45
    LED = IDX['led_fita']
    m.box(LED, (44.72, YT - 0.025, 31.95), (44.76, YT, 43.1))
    m.box(LED, (44.72, 1.1, 31.92), (44.76, YT, 31.95))
    G._q(m, IDX['lavagem_luz'], [(44.745, YT, 43.1), (44.745, YT, 31.95), (44.745, YT - 0.60, 31.95), (44.745, YT - 0.60, 43.1)], (1, 0, 0))
    G._q(m, IDX['lavagem_luz'], [(44.745, YT + 0.60, 43.1), (44.745, YT + 0.60, 31.95), (44.745, YT, 31.95), (44.745, YT, 43.1)], (1, 0, 0),
         [(0, 1), (1, 1), (1, 0), (0, 0)])
    G._q(m, IDX['ripado_cinza'], [(44.74, YT, 43.1), (44.74, YT, 31.95), (44.74, Y_1O_PAV, 31.95), (44.74, Y_1O_PAV, 43.1)], (1, 0, 0),
         [(YT / 3.0, 43.1 / 1.5), (YT / 3.0, 31.95 / 1.5), (Y_1O_PAV / 3.0, 31.95 / 1.5), (Y_1O_PAV / 3.0, 43.1 / 1.5)])
    G.logo_quad(m, (44.75, 2.70, 36.65), (1, 0, 0), 3.9, 3.9 / LOGO_ASPECTO, mat=IDX['letreiro_prata'])
    m.box(IDX['movel_escuro'], (44.72, 1.07, 32.0), (45.8, 1.40, 37.6))
    for k, zc in enumerate(np.arange(32.5, 37.4, 0.9)):
        tufo_seguro(m, 45.2, 1.40, float(zc), 1.0, 0.6, 14, 400 + k)
    for zc in np.arange(32.3, 37.5, 1.9):
        m.box(LQ, (45.76, 1.40, zc - 0.05), (45.84, 1.48, zc + 0.05))
    # lobby: reguas de luz no forro, cortinas acesas atras do vidro, plantas e parede do fundo
    for x in (30.0, 35.0, 40.0):
        m.box(LQ, (x - 0.03, 5.08, 26.0), (x + 0.03, 5.10, 34.0))
    for za, zb in ((24.7, 25.5), (28.2, 29.0)):
        G._q(m, IDX['janela_unidade'], [(44.3, 1.3, za), (44.3, 1.3, zb), (44.3, 4.5, zb), (44.3, 4.5, za)], (-1, 0, 0), [(0, 1), (1, 1), (1, 0), (0, 0)])
    tufo_seguro(m, 44.9, 1.1, 25.0, 1.6, 0.9, 18, 500); tufo_seguro(m, 44.9, 1.1, 28.6, 1.6, 0.9, 18, 501)
    m.box(IDX['interior_parede'], (37.8, 1.1, 25.5), (38.0, 5.0, 31.0))
    # portao e tela NE: fundo escuro (portao) e sala quente atras das aletas (tela NE)
    m.box(IDX['parede_escura'], (42.6, 1.6, 38.37), (42.75, 4.45, 43.35))
    m.box(IDX['parede_escura'], (41.0, 1.1, -0.5), (41.2, 5.0, 10.5))   # era ripado de madeira aceso (laranja): no render 14 o fundo da tela NE e escuro; usuario, 16/10/2026: sem madeira na area social

    # ---------------- lote 7: deque NO ----------------
    # lounge: grade de spots sob o forro (y 5,41) e no balanco sobre o vidro (forro da placa em 5,66)
    for x in np.arange(4.6, 10.7, 1.2):
        for zz in np.arange(5.0, 19.7, 1.2):
            m.box(LQ, (x - 0.07, 5.385, zz - 0.07), (x + 0.07, 5.405, zz + 0.07))
    for zz in np.arange(4.8, 19.9, 1.2):
        m.box(LQ, (3.04, 5.635, zz - 0.06), (3.16, 5.655, zz + 0.06))
    for x in np.arange(4.2, 10.8, 1.2):
        m.box(LQ, (x - 0.06, 5.635, 4.24), (x + 0.06, 5.655, 4.36))
    # luzinhas quentes nas paredes da piscina (discos de 6 cm virados para dentro da agua, y 2,075)
    def disco(x, z, nn):
        h = 0.03
        if nn[2] != 0:
            pts = [(x - h, 2.045, z), (x + h, 2.045, z), (x + h, 2.105, z), (x - h, 2.105, z)]
        else:
            pts = [(x, 2.045, z - h), (x, 2.045, z + h), (x, 2.105, z + h), (x, 2.105, z - h)]
        G._q(m, IDX['led_agua'], pts, nn)
    for x in np.arange(0.6, 11.3, 1.4): disco(float(x), 0.15, (0, 0, 1))
    for x in np.arange(3.7, 11.3, 1.4): disco(float(x), 4.01, (0, 0, -1))
    for z in np.arange(0.4, 3.9, 1.4): disco(11.30, float(z), (-1, 0, 0))
    for z in np.arange(0.4, 19.8, 1.4): disco(0.49, float(z), (1, 0, 0))
    for z in np.arange(4.3, 19.8, 0.7): disco(3.55, float(z), (-1, 0, 0))
    for x in np.arange(0.8, 3.4, 1.4): disco(float(x), 19.85, (0, 0, -1))
    # ---------------- portao de servico do canto SO (usuario, 16/10/2026: 'e tudo do mesmo material', sem lamas, grade pontilhada nem luz) ----------------
    # a parede oeste do FBX (x -0,52, y 0,9..3,6) tem vaos entre z 36,0 e 40,94 (pedestres 36,0-37,2 e veiculos 37,4-40,9) onde ficam o portao de lamas,
    # a grade 'cobogo' e a luz da sala atras. Fechados com a MESMA parede lisa, rente ao plano da parede.
    MPG = IDX['muro_pedra']
    G._q(m, MPG, [(-0.52, 0.9, 36.0), (-0.52, 0.9, 40.94), (-0.52, 3.6, 40.94), (-0.52, 3.6, 36.0)], (-1, 0, 0))
    # ---------------- muro de pedra do embasamento + grelha de ventilacao (imagens 14, 15 e 16 do usuario) ----------------
    # O FBX deixa um VAO na face de pedra entre y 0,24 e 0,85 (era a grelha, recuada: as lamas 'TERREO:venez' saem do MAPA porque serrilham).
    # Aqui o vao e fechado com a MESMA pedra e a grelha vira uma faixa lisa de lamas que ACOMPANHA O TERRENO: 0,40 m acima da rua,
    # 0,55 m de altura, so onde ainda sobra pelo menos 0,17 m de pedra acima dela (a rua sobe para leste e a base some, rente a entrada).
    MP, GR, YA, YB = IDX['muro_pedra'], IDX['lamina_ribeada'], 0.24, 0.85
    st = lambda a0, y0: (a0 / 3.0, (y0 - 0.85) / 3.0)
    def pedra_fill(p0, p1, nn):
        (xa, za), (xb, zb) = p0, p1
        ha, hb = (xa, xb) if abs(xb - xa) > abs(zb - za) else (za, zb)
        G._q(m, MP, [(xa, YA, za), (xb, YA, zb), (xb, YB, zb), (xa, YB, za)], nn, [st(ha, YA), st(hb, YA), st(hb, YB), st(ha, YB)])
    pedra_fill((-0.53, -0.87), (53.28, -0.87), (0, 0, -1))        # norte
    pedra_fill((-0.53, -0.9), (-0.53, 19.42), (-1, 0, 0))         # oeste (so onde havia grelha: z -0,9..19,4)
    pedra_fill((53.28, -0.9), (53.28, 6.49), (1, 0, 0))           # leste, junto a entrada
    YG0, HG = 0.40, 0.55
    def faixa_grelha(coords, h_de, ponto, nn, passo=2.0):
        """coords: valores ao longo da parede; h_de(c): altura do terreno ali; ponto(c, y): ponto 3D da parede. So onde a grelha cabe
        abaixo do friso de pedra de cima (y <= 0,88)."""
        cs_ = list(coords)
        for ca, cb in zip(cs_[:-1], cs_[1:]):
            ya, yb = h_de(ca) + YG0, h_de(cb) + YG0
            if max(ya, yb) + HG > YB + 0.03 or min(ya, yb) < -1.9:
                continue
            G._q(m, GR, [ponto(ca, ya), ponto(cb, yb), ponto(cb, yb + HG), ponto(ca, ya + HG)], nn,
                 [(ca / 0.3, 0.0), (cb / 0.3, 0.0), (cb / 0.3, HG / 0.3), (ca / 0.3, HG / 0.3)])
    xs_ = list(np.arange(-0.5, 53.3, 2.0)) + [53.3]
    faixa_grelha(xs_, lambda x: chao_h(x, -0.9), lambda x, y: (x, y, -0.88), (0, 0, -1))                    # norte
    zs_ = list(np.arange(-0.9, 19.42, 2.0)) + [19.42]
    faixa_grelha(zs_[::-1], lambda z: chao_h(-1.0, z), lambda z, y: (-0.54, y, z), (-1, 0, 0))              # oeste (z decrescente: normal para fora)
    zs2_ = list(np.arange(-0.9, 6.49, 2.0)) + [6.49]
    faixa_grelha(zs2_, lambda z: chao_h(54.0, z), lambda z, y: (53.20, y, z), (1, 0, 0))                    # leste, junto a entrada
    print(f'interior: {n} caixas, {palmas} arvores')


def main():
    info = json.load(open(os.path.join(PASTA, 'partes.json')))
    z = np.load(os.path.join(PASTA, 'partes.npz'))
    niveis = [y + DESLOCA[1] for y in info['niveis_pav']]; y0 = niveis[0]
    nodes, mesh_list = [], []
    add_mesh = lambda m, nome: (mesh_list.append((m, nome)) or len(mesh_list) - 1)
    add_node = lambda **kw: (nodes.append(kw) or len(nodes) - 1)
    partes = {p['nome']: p for p in info['partes']}
    pega = lambda n: (z[n + '_pos'], z[n + '_nrm'], z[n + '_mat'])

    children = []
    for nome in ('TERREO', 'CASCA'):
        P, N, M = pega(nome)
        if nome == 'CASCA':
            # letreiro da quina: no FBX fica no pe do painel e colado a esquerda; nos renders (1, 5,
            # 10) esta centrado no painel (X 0,9..10,9), na altura do 2o pavimento
            P = P.copy(); M = M.copy()
            # concreto do deque e travertino na mesma cota (y 2,12): z-fighting. O deque fica para o TERREO
            M[(M == 'CASCA-NOVA:concreto ') & (P[:, :, 1].max(1) < 1.5)] = 'TERREO:-'
            P[M == 'CASCA-NOVA:cinnamon'] += np.array([-0.85, 2.2, 0])
            st = M == 'CASCA-NOVA:Material #2147455081'
            cst = P[st].reshape(-1, 3).mean(0)
            P[st] = (P[st] - cst) * np.array([1.6, 1.6, 1.0]) + cst + np.array([1.0, 2.15, 0])
        if nome == 'TERREO':
            # fora: linhas do lote a mais de 8 m da torre e o asfalto da rua, que caia
            # em cima do chao do proprio site (CHAO_Y) e tremia
            C = pega('CASCA')[0].reshape(-1, 3)
            x0, z0 = C[:, 0].min() - 8, C[:, 2].min() - 8
            # leste/sul: o terreno do arquiteto vai ate x 67,8 (pracas e patio), z 60,6 (site)
            x1, z1 = C[:, 0].max() + 20, C[:, 2].max() + 17
            c = P.mean(1)
            ok = (c[:, 0] > x0) & (c[:, 0] < x1) & (c[:, 2] > z0) & (c[:, 2] < z1) & (c[:, 1] > -2.9)
            P, N, M = P[ok], N[ok], M[ok]
        ms = malhas(nome, P, N, M)
        filhos = [add_node(name=f'{nome}-{i}', mesh=add_mesh(m, f'{nome.lower()}{i}')) for i, m in enumerate(ms)]
        children.append(add_node(name=nome if nome == 'TERREO' else 'COBERTURA', children=filhos))

    # interior do terreo e entorno (o FBX da casca nao traz): caixas no lugar dos moveis dos FBX
    # de interior (MDF, SOFAS, EQUIPAMENTOS, LUMINARIAS: 2,3 milhoes de triangulos, inviavel no
    # celular), mobiliario e vegetacao nas posicoes da cena do Twinmotion
    global NICHOS
    Pc, Nc, Mc = pega('CASCA')
    nb = np.array(['2100517296' in str(q) for q in Mc]) & (Nc.mean(1)[:, 0] > 0.9)
    Qc = Pc[nb] + DESLOCA
    nb2 = (np.abs(Qc[:, :, 0] - 14.37).max(1) < 0.01) & (Qc[:, :, 2].min(1) > 2.7) & (Qc[:, :, 2].max(1) < 2.95)
    NICHOS = sorted({(round(float(q[:, 1].min()), 2), round(float(q[:, 1].max()), 2)) for q in Qc[nb2]})
    print(f'nichos da torre: {len(NICHOS)}')
    global ALT_DEQUE
    Pt, Nt, Mt = pega('TERREO'); Mt = np.array([str(q) for q in Mt])
    S_ = np.isin(Mt, ['TERREO:travertino porcelanato', 'TERREO:Porcelanato BEJE', 'TERREO:granito sao gabriel.001',
                      'TERREO:área livre.001', 'TERREO:Material #2147455579']) & (Nt.mean(1)[:, 1] > 0.8)
    Q_ = Pt[S_] + DESLOCA
    Pc2 = Pc[np.array([str(q) == 'CASCA-NOVA:concreto ' for q in Mc]) & (Pc[:, :, 1].max(1) < 1.5)] + DESLOCA
    Q_ = np.concatenate([Q_, Pc2])
    def ALT_DEQUE(x, z):
        h = [q[:, 1].mean() for q in Q_ if q[:, 0].min() <= x <= q[:, 0].max() and q[:, 2].min() <= z <= q[:, 2].max()]
        return max(h) if h else 1.1
    constroi_obst(Pt, Nt, Mt)
    m = G.Mesh(); interior(m)
    print('vegetacao x paredes:', VEG)
    children.append(add_node(name='INTERIOR', mesh=add_mesh(m, 'interior'), extras={'origem': 'caixas dos FBX de interior + cena Twinmotion'}))

    faixa = [add_mesh(m, f'faixa{i}') for i, m in enumerate(malhas('FAIXA', *pega('FAIXA'), dy=y0))]
    unid = {}
    for k in range(1, 31):
        ms = malhas(f'S{k:02d}', *porta_2_folhas(*pega(f'S{k:02d}')), dy=y0)
        assert len(ms) == 1
        unid[k] = (add_mesh(ms[0], f'unidade-S{k:02d}'), partes[f'S{k:02d}']['fachada'])
    for i, y in enumerate(niveis):
        filhos = [add_node(name=f'PAV-{i + 1:02d}-{j}', mesh=mi) for j, mi in enumerate(faixa)]
        for k in range(1, 31):
            filhos.append(add_node(name=f'P{i + 1:02d}-S{k:02d}', mesh=unid[k][0],
                                   extras={'pavimentoTipo': i + 1, 'studio': k, 'fachada': unid[k][1]}))
        children.append(add_node(name=f'PAV-{i + 1:02d}', translation=[0, round(y, 3), 0], children=filhos,
                                 extras={'pavimentoTipo': i + 1, 'nivel_m': round(y, 2)}))

    root = add_node(name='CINNAMON_FACHADA_PROVISORIO', children=children, extras={
        'status': 'MODELO DO ARQUITETO (FBX 3ds Max, 09/2026), so faces vistas de fora; materiais da maquete',
        'pavimentosTipo': len(niveis), 'pavimentosTipo_origem': 'FBX (17 grupos) + DWG 09/2026',
        'studiosPorPavimento': 30, 'peDireito_m': round(info['pe'], 3),
        'terreo_m': round(info['piso0'] + DESLOCA[1], 3), 'laje_cobertura_m': round(niveis[-1] + info['pe'], 2),
        'numeracao': 'P<pav>-S<studio da planta>; numeracao comercial das unidades NAO conhecida',
        'terreno': TERRENO,
    })
    glb = G.pack(nodes, mesh_list, root)
    open(SAIDA, 'wb').write(glb)
    tri_arq = sum(len(p[3]) // 3 for m, _ in mesh_list for p in m.prims.values())
    if FALLBACK:
        print('AVISO: materiais do FBX sem regra no MAPA (viram interior_parede, aceso em ambar) — confira se e isso mesmo: ' + ', '.join(f'{k} (x{v})' for k, v in sorted(FALLBACK.items(), key=lambda t: -t[1])))
    print(f'{SAIDA}: {len(glb) / 1e6:.2f} MB, {len(nodes)} nos, {len(mesh_list)} malhas, {tri_arq} triangulos no arquivo')


if __name__ == '__main__':
    main()
