"""Texturas procedurais da maquete da fachada (scripts/fachada/gen_fachada.py).

Nada vem de arquivo: madeira, pedra, ripado, metal ribeado e o interior da
unidade sao gerados aqui com numpy e embutidos no .glb. So o letreiro vem
de logo.png — o SVG oficial (img/logo-cinnamon-studio.svg) rasterizado uma
vez com qlmanage (macOS), letterbox e luminancia invertida como alfa.
"""
import io
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))


def fbm(h, w, oct=5, seed=0):
    r = np.random.default_rng(seed); out = np.zeros((h, w))
    for o in range(oct):
        cells = 4 * 2 ** o
        n = r.random((max(2, h * cells // max(h, w)), max(2, w * cells // max(h, w))))
        im = Image.fromarray((n * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
        out += np.array(im) / 255 / (1.7 ** o)
    out -= out.min(); out /= out.max(); return out

def normal_from_height(hm, strength=2.0):
    gy, gx = np.gradient(hm)
    nx = -gx * strength; ny = gy * strength; nz = np.ones_like(hm)
    l = np.sqrt(nx * nx + ny * ny + nz * nz)
    n = np.dstack([nx / l, ny / l, nz / l])
    return Image.fromarray(((n * 0.5 + 0.5) * 255).astype(np.uint8))



def _jpg(col, q=92):
    b = io.BytesIO(); Image.fromarray((np.clip(col, 0, 1) * 255).astype(np.uint8)).save(b, 'JPEG', quality=q); return b.getvalue()

def _png(im):
    b = io.BytesIO(); im.save(b, 'PNG', optimize=True); return b.getvalue()


def madeira():
    H, W = 256, 1024
    x = np.linspace(0, 1, W, endpoint=False)[None, :]; y = np.linspace(0, 1, H)[:, None]
    grain = np.sin((y * 22 + fbm(H, W, 4, 1) * 3.5 + np.sin(x * 2 * np.pi * 3) * 0.6) * 2 * np.pi)
    grain = (grain * 0.5 + 0.5) ** 1.6
    fine = fbm(H, W, 6, 2)
    dark = np.array([0.26, 0.14, 0.07]); light = np.array([0.62, 0.40, 0.22])
    col = dark * grain[..., None] + light * (1 - grain[..., None])
    col = col * (0.85 + 0.3 * fine[..., None])
    col[np.repeat(((y * 8) % 1 < 0.06), W, 1)] *= 0.55
    rough = 0.55 + 0.25 * (1 - grain) + 0.1 * fine
    return {'madeira.jpg': _jpg(col), 'madeira_n.png': _png(normal_from_height(grain * 0.6 + fine * 0.4, 1.2)),
            'madeira_mr.jpg': _jpg(np.dstack([np.zeros_like(rough), rough, np.zeros_like(rough)]), 90)}

def ruido_fft(h, w, beta=2.0, seed=0, esticar=(1.0, 1.0)):
    """ruido 1/f^beta feito no espectro: repete sem emenda nos dois eixos (ladrilho perfeito).
    esticar=(ey, ex) alonga os veios: ex > 1 deixa as ondas longas ao longo de x."""
    r = np.random.default_rng(seed)
    fy = np.fft.fftfreq(h)[:, None] * h * esticar[0]; fx = np.fft.fftfreq(w)[None, :] * w * esticar[1]
    f = np.sqrt(fy * fy + fx * fx); f[0, 0] = 1
    spec = (r.normal(size=(h, w)) + 1j * r.normal(size=(h, w))) / f ** (beta / 2)
    spec[0, 0] = 0
    n = np.real(np.fft.ifft2(spec)); n -= n.min(); return n / n.max()


def madeira_painel(nome='madeira_painel', contraste=1.0, escala=1.0):
    """tabuas das placas de madeira (quina NO, paredes de topo) e, acesas, do forro das sacadas.
    Render 3 de perto (16/10/2026): tabuas verticais de LARGURA IRREGULAR (~0,17 a 0,45 m, media
    ~0,3 m), cada uma com tom e veio proprios, algumas mais claras, nos visiveis, junta escura
    fina e discreta; cor cafe-acinzentado neutro (no render #2c2327 ja com o ceu azul por cima),
    nada de vermelho. Ladrilho = 3 x 3 m, 10 tabuas (forro); painel: 6 m, 20 tabuas (UV x0,5).
    Imagem: linhas (y) correm ao longo da parede, colunas (x) ao longo da altura."""
    H = W = 1024
    fino = (nome == 'madeira_painel')    # painel: tabuas finas e irregulares (Renders 2 e 3); forro: igual a antes
    r = np.random.default_rng(21)
    larg = r.uniform(0.55, 1.5, 20 if fino else 10); bordas = np.concatenate([[0], np.cumsum(larg) / larg.sum()])
    N = len(larg)
    y = np.linspace(0, 1, H, endpoint=False)[:, None]; x = np.linspace(0, 1, W, endpoint=False)[None, :]
    k = np.clip(np.searchsorted(bordas, y[:, 0], side='right') - 1, 0, N - 1)[:, None]
    t = (y - bordas[k]) / (bordas[k + 1] - bordas[k])                 # posicao dentro da tabua
    fase, freq = r.uniform(0, 1, N), r.uniform(2.5, 5.5, N) * larg / larg.mean()
    tom = r.uniform(0.86, 1.08, N)
    if not fino:
        tom[r.choice(N, 2, replace=False)] *= 1.14   # duas tabuas mais claras
    tom = 1 + (tom - tom.mean()) * (0.4 if fino else contraste)
    calor = r.uniform(-0.025, 0.025, N)
    torce = ruido_fft(H, W, 2.2, 22, (1.0, 6.0)) * (0.5 if fino else 1.0)   # ondas longas ao longo da altura
    veio = np.sin(2 * np.pi * (t * freq[k] + fase[k] + torce * 0.75 + 0.06 * np.sin(2 * np.pi * x * 2 + fase[k] * 6)))
    for (cy, cx, rr) in r.uniform([0, 0, 0.010], [1, 1, 0.02], (9, 3)):   # nos
        dy = (y - cy + 0.5) % 1 - 0.5; dx = ((x - cx + 0.5) % 1 - 0.5) * 0.35
        d = np.sqrt(dy * dy + dx * dx)
        veio += 1.5 * np.exp(-(d / rr) ** 2) * np.cos(d / rr * 9)
    veio = np.clip(veio * 0.5 + 0.5, 0, 1) ** 1.3
    fibra = ruido_fft(H, W, 1.2, 23, (1.0, 12.0))                  # fibra fina
    mancha = ruido_fft(H, W, 2.6, 24, (1.0, 3.0))
    escuro = np.array([0.232, 0.186, 0.172]); claro = np.array([0.305, 0.250, 0.229])
    col = escuro * veio[..., None] + claro * (1 - veio[..., None])
    col = col * (0.88 + 0.2 * fibra[..., None]) * ((0.97 + 0.06 * mancha[..., None]) if fino else (0.92 + 0.16 * mancha[..., None]))
    col = (col * tom[k][..., None] + np.stack([calor[k], calor[k] * 0.5, -calor[k] * 0.2], -1) * contraste) * escala
    meia = (0.015 if fino else 0.006) / (larg[k] / larg.mean())                           # junta de ~1 cm em qualquer largura
    junta = ((t < meia) | (t > 1 - meia))
    col[np.repeat(junta, W, 1)] *= 1 - 0.55 * contraste
    hm = np.where(np.repeat(junta, W, 1), 0.0, 1.0) * 0.7 + veio * 0.18 + fibra * 0.12
    nb = io.BytesIO(); normal_from_height(hm, 2.4).resize((512, 512), Image.BILINEAR).save(nb, 'JPEG', quality=84)
    return {nome + '.jpg': _jpg(col, 88), nome + '_n.jpg': nb.getvalue()}


def madeira_forro():
    """forro e borda das sacadas (Render 3): a mesma madeira, mais lisa (tabuas quase do mesmo
    tom, junta apagada) e um pouco mais escura — acesa pelo emissivo vira nogueira aquecida,
    sem as listras claras/escuras que a textura das placas fazia no forro"""
    return madeira_painel('madeira_forro', contraste=0.3, escala=0.9)


def cortina():
    """o que se ve pela porta de vidro do studio (usuario, 16/10/2026: 'a janela esta com um efeito claro ondulado, deve ser toda de
    vidro sem esse efeito'): SEM voil, SEM pregas, SEM abas — so o ambiente interno ao fundo como uma luz quente difusa e lisa, mais
    clara no alto e mais escura no pe, e o brilho suave de um spot no forro. Vai como emissivo da janela (o 'acende' do js escala
    tudo); apagada, a porta fica vidro escuro."""
    H = W = 128
    y = np.linspace(0, 1, H)[:, None]; x = np.linspace(0, 1, W, endpoint=False)[None, :]
    amb = (0.50 + 0.30 * np.exp(-((y - 0.28) ** 2) * 6.0)) * (0.88 + 0.12 * np.exp(-((x - 0.5) ** 2) * 3.0))
    amb = amb + 0.18 * np.exp(-(((x - 0.5) / 0.30) ** 2 + ((y - 0.08) / 0.10) ** 2))
    amb = amb * (1.0 - 0.35 * y ** 1.6)
    col = np.array([0.90, 0.68, 0.44])[None, None, :] * amb[..., None]
    return {'cortina.jpg': _jpg(np.clip(col, 0, 1), 90)}


def pedra_preta():
    """pedra preta em filetes da torre da escada e do nucleo (render do terreo de perto,
    14/10/2026): fiadas horizontais finas e irregulares, cada pedra com tom e relevo proprios,
    face rachada, juntas fundas. Ladrilho 2 x 2 m sem emenda (u = horizontal, v = vertical)."""
    H = W = 1024
    r = np.random.default_rng(31)
    alt = []
    while sum(alt) < H:
        alt.append(int(r.integers(10, 30)))
    alt[-1] -= sum(alt) - H
    if alt[-1] < 12:
        alt[-2] += alt.pop()
    tom = np.zeros((H, W)); rel = np.zeros((H, W)); junta = np.zeros((H, W), bool); crista = np.zeros((H, W), bool)
    y = 0
    for h in alt:
        cortes = np.sort(r.choice(W, size=max(2, W // int(r.integers(300, 700))), replace=False))
        for c0, c1 in zip(cortes, np.roll(cortes, -1)):
            xs = np.arange(c0, c1 if c1 > c0 else c1 + W) % W
            tom[y:y + h, xs] = 0.19 * r.uniform(0.97, 1.03)    # COR UNIFORME (correcao do usuario): so o relevo muda
            rel[y:y + h, xs] = r.uniform(0.35, 1.0)
            junta[y:y + h, xs[:1]] = True
        junta[y:y + 2, :] = True
        crista[y + 2:y + 4, :] = True
        y += h
    racha = ruido_fft(H, W, 1.6, 32, (2.5, 1.0))      # face rachada, veios na horizontal
    grao = ruido_fft(H, W, 0.6, 33)
    col = tom[..., None] * (0.9 + 0.2 * racha[..., None]) * (0.94 + 0.12 * grao[..., None])
    col = col * np.array([1.0, 1.0, 1.04])             # preto neutro, quase sem cor
    col[crista] *= 1.6
    col[junta] *= 0.7
    hm = np.where(junta, 0.0, rel * 0.8 + racha * 0.3)
    nb = io.BytesIO(); normal_from_height(hm, 3.0).resize((512, 512), Image.BILINEAR).save(nb, 'JPEG', quality=82)
    return {'pedra_preta.jpg': _jpg(col, 88), 'pedra_preta_n.jpg': nb.getvalue()}


def paralelepipedo():
    """praca de paralelepipedo molhado em volta do embasamento (render da quina noroeste no
    nivel da rua, 14/10/2026): pedras de ~14 x 10 cm em fiadas desencontradas, cinza-escuro
    puxando ao marrom, juntas escuras. Ladrilho 2 x 2 m sem emenda."""
    H = W = 1024
    r = np.random.default_rng(41)
    nl, nc = 20, 14
    y = np.arange(H)[:, None]; x = np.arange(W)[None, :]
    lin = (y * nl // H)
    desl = r.integers(0, W // nc, nl)[lin]
    xx = (x + desl) % W
    col_ = xx * nc // W
    tl = (y * nl % H) / H; tc = (xx * nc % W) / W                  # 0..1 dentro da pedra
    tom = r.uniform(0.16, 0.30, (nl, nc))[lin, col_]
    calor = r.uniform(0.0, 0.03, (nl, nc))[lin, col_]
    borda = np.minimum(np.minimum(tl, 1 - tl), np.minimum(tc, 1 - tc))
    junta = borda < 0.07
    abaul = np.clip(borda / 0.25, 0, 1) ** 0.6                       # pedra abaulada
    f = ruido_fft(H, W, 1.4, 42)
    col = np.stack([tom + calor, tom + calor * 0.5, tom - calor * 0.2], -1) * (0.8 + 0.4 * f[..., None])
    col[junta] *= 0.35
    hm = np.where(junta, 0.0, 0.5 + 0.5 * abaul) * 0.85 + f * 0.15
    nb = io.BytesIO(); normal_from_height(hm, 3.0).resize((256, 256)).save(nb, 'JPEG', quality=82)
    cb = io.BytesIO(); Image.fromarray((np.clip(col, 0, 1) * 255).astype(np.uint8)).resize((512, 512), Image.LANCZOS).save(cb, 'JPEG', quality=82)
    return {'paralelepipedo.jpg': cb.getvalue(), 'paralelepipedo_n.jpg': nb.getvalue()}


def placa_pedra():
    """placas grandes de pedra cinza do embasamento (mesmo render): 1,2 x 0,65 m, tom
    mosqueado de cada placa, junta fina escura. Ladrilho 2,4 x 1,3 m (2 placas x 2 fiadas)."""
    H, W = 512, 1024
    r = np.random.default_rng(43)
    y = np.arange(H)[:, None]; x = np.arange(W)[None, :]
    lin, col_ = y * 2 // H, x * 2 // W
    tom = np.full((2, 2), 0.34)[lin, col_]                             # uma cor so
    f = ruido_fft(H, W, 1.8, 44) * 0.6 + ruido_fft(H, W, 0.8, 45) * 0.4
    col = (tom * (0.93 + 0.14 * f))[..., None] * np.array([1.0, 1.0, 1.02])
    junta = ((y * 2) % H < 3) | ((x * 2) % W < 3)
    col[np.broadcast_to(junta, (H, W))] *= 0.45
    return {'placa_pedra.jpg': _jpg(col, 85)}


def marmore_preto():
    """marmore preto molhado do deque e das piscinas (render da quina, 14/10/2026): fundo
    quase preto de tom UNIFORME, veios finos e claros e irregulares, juntas de placas de
    ~0,9 m. Ladrilho 3,6 x 3,6 m = 4 x 4 placas, sem emenda."""
    H = W = 1024
    base = ruido_fft(H, W, 2.2, 51)
    v1 = 1 - np.abs(ruido_fft(H, W, 4.2, 52) * 2 - 1)           # campo suave: 1 sobre as linhas do veio
    v2 = 1 - np.abs(ruido_fft(H, W, 3.6, 53) * 2 - 1)
    veio = np.clip((v1 - 0.968) / 0.032, 0, 1) ** 1.2 * 1.5 + np.clip((v2 - 0.985) / 0.015, 0, 1) * 0.5
    col = (0.085 * (0.93 + 0.14 * base))[..., None] * np.array([1.0, 1.0, 1.03])
    col = col + veio[..., None] * np.array([0.30, 0.285, 0.265]) * 0.85
    y = np.arange(H)[:, None]; x = np.arange(W)[None, :]
    junta = np.broadcast_to(((y % 256) < 2) | ((x % 256) < 2), (H, W))
    col[junta] *= 0.35
    return {'marmore_preto.jpg': _jpg(col, 86)}


def lounge_parede():
    """parede do lounge em pedra de filete (Render 5 de perto, 15/10/2026): filetes finos de
    pedra cinza-escuro amarronzado, de 4 a 9 cm de altura e 15 a 60 cm de comprimento, uns mais
    salientes que pegam a luz quente de cima e brilham — o conjunto fica escuro com pontos
    acesos, nao uma parede laranja. Ladrilho 2 x 1 m. Usada como cor e como emissivo."""
    H, W = 512, 1024
    r = np.random.default_rng(61)
    img = np.zeros((H, W, 3))
    y = 0
    while y < H:
        h = int(r.integers(10, 24)); h = min(h, H - y)
        x = int(r.integers(0, 60))
        while x < W + 60:
            L = int(r.integers(40, 150))
            tom = r.uniform(0.10, 0.20)
            aceso = r.random() < 0.22                       # filete saliente que pega a luz
            xs = np.arange(x, x + L) % W
            c = np.array([tom * 1.05, tom * 0.92, tom * 0.78])
            if aceso:
                c = c + np.array([0.30, 0.18, 0.08]) * r.uniform(0.5, 1.0)
            img[y + 1:y + h - 1, xs[2:-2]] = c
            x += L
        y += h
    luz = 0.75 + 0.45 * np.exp(-((np.arange(H)[:, None, None] / H) * 2.2) ** 2)      # luz de cima
    f = ruido_fft(H, W, 1.5, 62)[..., None]
    img = img * luz * (0.85 + 0.3 * f)
    return {'lounge_parede.jpg': _jpg(np.clip(img, 0, 1), 86)}


def ripado_cinza():
    """revestimento da entrada (Render 6, 16/10/2026): tabuas verticais de madeira ENVELHECIDA cinza-amarronzada
    (termotratada/demolicao), ~12 cm, cada uma com tom proprio do cinza frio ao castanho quente, veio longo e
    riscos finos, manchas verticais de intemperie, nos raros e friso escuro fino entre elas.
    Ladrilho 1,5 x 3 m (u = altura, v = largura: as tabuas ficam em pe quando u corre na vertical)."""
    H, W = 512, 1024                                   # linhas = largura (v), colunas = altura (u)
    r = np.random.default_rng(71)
    nb = 12
    vv = np.arange(H)[:, None]
    tab = ((vv * nb) // H)[:, 0]
    tv = ((vv * nb % H) / H)
    friso = np.repeat((tv < 0.045) | (tv > 0.97), W, 1)
    tom = r.uniform(0.86, 1.12, nb)
    quente = r.uniform(0.15, 0.75, nb)[:, None]
    cor_tab = np.array([0.395, 0.360, 0.325])[None, :] * (1 - quente) + np.array([0.470, 0.375, 0.285])[None, :] * quente   # cinza frio -> castanho
    veio = ruido_fft(H, W, 1.2, 72, esticar=(1.0, 14.0))
    fibra = ruido_fft(H, W, 0.8, 73, esticar=(1.0, 34.0))
    mancha = ruido_fft(H, W, 2.6, 74, esticar=(1.0, 3.0))
    base = (cor_tab * tom[:, None])[tab][:, None, :]            # (H,1,3)
    col = np.broadcast_to(base, (H, W, 3)) * (0.74 + 0.48 * veio[..., None]) * (0.86 + 0.28 * fibra[..., None]) * (0.84 + 0.32 * mancha[..., None])
    col = col.copy()
    yy = np.arange(H)[:, None]; xx = np.arange(W)[None, :]
    for _ in range(14):                                         # nos
        cy, cx = r.uniform(0, H), r.uniform(0, W)
        d = ((yy - cy) / (H * 0.010)) ** 2 + ((xx - cx) / (W * 0.016)) ** 2
        col *= (1 - 0.42 * np.exp(-d))[..., None]
    col[friso] = np.array([0.05, 0.045, 0.04])
    hm = np.where(friso, 0.0, 1.0) * 0.8 + veio * 0.2
    nrm = normal_from_height(hm, 2.2).resize((512, 256))
    cb = io.BytesIO(); Image.fromarray((np.clip(col, 0, 1) * 255).astype(np.uint8)).save(cb, 'JPEG', quality=84)
    return {'ripado_cinza.jpg': cb.getvalue(), 'ripado_cinza_n.jpg': _jpg(np.asarray(nrm) / 255.0, 85)}


def monolito():
    """monolito do letreiro (Renders 6 e 10, 16/10/2026): pedra rustica CINZA-CHUMBO, quase azulada na sombra,
    de relevo irregular de massa trabalhada a colher / pedra apicoada (granulos de 1-4 cm, ondulacao de 10-25 cm
    e cristas sinuosas), sem as placas poligonais de antes. O relevo vai tambem no albedo (sombreado por uma luz
    alta a esquerda e cavidades escuras): a luz do site e quase toda difusa e o normal map sozinho nao aparece.
    Manchas mais claras e quentes onde a pedra 'seca'. Ladrilho de 3 m."""
    N = 768
    macro = ruido_fft(N, N, 2.6, 81)
    meso = ruido_fft(N, N, 1.7, 82)
    fino = ruido_fft(N, N, 0.8, 83)
    # cristas em curva: ruido medio deformado por outro ruido (sem scipy: deslocamento inteiro por pixel)
    wx = ((ruido_fft(N, N, 2.6, 85) - 0.5) * 52).astype(int); wy = ((ruido_fft(N, N, 2.6, 86) - 0.5) * 52).astype(int)
    yy, xx = np.mgrid[0:N, 0:N]
    base_r = ruido_fft(N, N, 1.4, 84)
    rw = base_r[(yy + wy) % N, (xx + wx) % N]
    cr = 1 - np.abs(2 * rw - 1)                                         # cristas sinuosas
    h = 0.50 * cr ** 1.6 + 0.22 * meso + 0.28 * fino
    h = (h - h.min()) / (h.max() - h.min())
    gy, gx = np.gradient(h)
    s_ = -(gx + gy)
    s_ = np.clip(s_ / (2.2 * s_.std() + 1e-9), -1, 1)                  # luz alta a esquerda
    base = np.array([0.222, 0.200, 0.180])                              # cinza-chumbo QUENTE (Render 6: media #4e443d lit, #473e3a); na sombra o ceu esfria
    seco = np.array([0.345, 0.300, 0.255])                              # pedra seca: cinza-areia quente
    t = np.clip((macro - 0.50) * 2.4, 0, 1)[..., None] * 0.55
    col = base * (1 - t) + seco * t
    col = col * (0.55 + 0.80 * h[..., None] ** 1.3) * (1 + 0.65 * s_[..., None]) * (0.86 + 0.28 * macro[..., None])
    nrm = normal_from_height(h * 0.8 + fino * 0.2, 5.0).resize((512, 512), Image.BILINEAR)
    return {'monolito.jpg': _jpg(np.clip(col, 0, 1), 74), 'monolito_n.jpg': _jpg(np.asarray(nrm) / 255.0, 72)}


def lavagem():
    """lavagem de luz da fita de LED no topo do monolito: branco-quente com alfa que some de
    cima para baixo (v = 0 no alto)."""
    H, W = 256, 16
    a = np.exp(-((np.arange(H) / H) * 3.2) ** 1.6)[:, None] * np.ones((1, W))
    a[:3] *= np.array([0.0, 0.5, 0.85])[:, None]; a[-3:] = 0     # bordas sem alfa: o wrap do sampler misturava a 1a linha (clara) com a ultima (pontilhado no fim do quad)
    rgba = np.zeros((H, W, 4), np.uint8)
    rgba[..., 0] = 255; rgba[..., 1] = 200; rgba[..., 2] = 135; rgba[..., 3] = (a * 120).astype(np.uint8)   # 16/10: era 210 (faixa branca estourada)
    b = io.BytesIO(); Image.fromarray(rgba, 'RGBA').save(b, 'PNG'); return {'lavagem.png': b.getvalue()}


def muro_pedra():
    """muro/embasamento de pedra (imagens 14, 15 e 16 do usuario, 16/10/2026): PLACAS GRANDES de pedra cinza-chumbo, em fiadas
    de 0,60 m (ladrilho de 3 m = 5 fiadas), largura 0,9-1,5 m com juntas desencontradas, tom proprio de cada placa (frio/quente
    levemente), mosqueado largo e grao fino, junta continua de ~1 cm. Pedra serrada/apicoada: fosca, sem brilho."""
    N, rows = 1020, 5
    hrow = N // rows
    r = np.random.default_rng(141)
    tom = np.zeros((N, N)); quente = np.zeros((N, N)); junta = np.zeros((N, N), bool)
    for k in range(rows):
        larg = []
        while sum(larg) < N - 460:
            larg.append(r.uniform(0.9, 1.5) * N / 3.0)
        larg.append(N - sum(larg)); larg = np.array(larg) * (N / sum(larg))
        x0 = int(r.uniform(0, N)); xs = (np.cumsum(np.concatenate([[0], larg])) + x0).astype(int)
        for a_, b_ in zip(xs[:-1], xs[1:]):
            t = r.uniform(0.95, 1.06); q = r.uniform(-1, 1)
            cols = np.arange(a_, b_) % N
            tom[k * hrow:(k + 1) * hrow, cols] = t; quente[k * hrow:(k + 1) * hrow, cols] = q
            junta[k * hrow:(k + 1) * hrow, a_ % N: a_ % N + 3] = True
            if a_ % N + 3 > N: junta[k * hrow:(k + 1) * hrow, : a_ % N + 3 - N] = True
        junta[k * hrow: k * hrow + 3, :] = True
    macro = ruido_fft(N, N, 2.4, 142); fino = ruido_fft(N, N, 0.7, 143); veio = ruido_fft(N, N, 1.6, 144, esticar=(1.0, 3.0))
    base = np.array([0.205, 0.210, 0.222])   # alvo na tela ~#4b4d52 (render 14); antes 0,30 lia lilas-claro #6f6c75
    col = base[None, None, :] * (tom * (0.84 + 0.32 * macro) * (0.90 + 0.20 * fino) * (0.92 + 0.16 * veio))[..., None]
    col = col * (1 + 0.02 * quente[..., None] * np.array([1.0, 0.2, -1.0])[None, None, :])
    col[junta] *= 0.55
    hm = np.where(junta, 0.0, 0.75 + 0.15 * fino + 0.10 * macro)
    nrm = normal_from_height(hm, 2.2).resize((512, 512), Image.BILINEAR)
    return {'muro_pedra.jpg': _jpg(np.clip(col, 0, 1), 86), 'muro_pedra_n.jpg': _jpg(np.asarray(nrm) / 255.0, 80)}


def painel_escuro():
    """muro de divisa SUL (Render 3, a esquerda do portao de lamas): painel de revestimento GRAFITE quente, em tiras verticais de
    0,60 m com junta fina escura e leves riscos verticais; fosco. Ladrilho 3 x 3 m = 5 tiras (u = horizontal, v = altura)."""
    N = 512; r = np.random.default_rng(161)
    x = np.arange(N)[None, :]; k = (x * 5) // N; t = ((x * 5) % N) / N
    tom = r.uniform(0.94, 1.06, 5)[k] + np.zeros((N, 1))
    streak = ruido_fft(N, N, 1.4, 162, esticar=(8.0, 1.0)); fino = ruido_fft(N, N, 0.8, 163)
    base = np.array([0.175, 0.162, 0.157])
    col = base[None, None, :] * (tom * (0.90 + 0.20 * streak) * (0.95 + 0.10 * fino))[..., None]
    junta = np.broadcast_to((t < 0.018) | (t > 0.985), (N, N))
    col = col.copy(); col[junta] *= 0.40
    hm = np.where(junta, 0.0, 0.8 + 0.1 * fino + 0.1 * streak)
    nrm = normal_from_height(hm, 2.0).resize((256, 256), Image.BILINEAR)
    return {'painel_escuro.jpg': _jpg(np.clip(col, 0, 1), 86), 'painel_escuro_n.jpg': _jpg(np.asarray(nrm) / 255.0, 80)}


def pedra():
    H = W = 1024
    h = fbm(H, W, 6, 3) * 0.7 + fbm(H, W, 3, 4) * 0.3
    return {'pedra.jpg': _jpg(np.array([0.17, 0.165, 0.15]) * (0.6 + 0.8 * h[..., None]), 90),
            'pedra_n.jpg': _jpg(np.asarray(normal_from_height(h, 3.0)) / 255.0, 88)}

def ripado():
    H, W = 512, 512
    y = np.linspace(0, 1, H)[:, None]
    gap = np.repeat(((y * 16) % 1) < 0.14, W, 1)
    f = fbm(H, W, 5, 5)
    col = np.array([0.52, 0.33, 0.18]) * (0.75 + 0.5 * f[..., None])
    col[gap] = np.array([0.06, 0.06, 0.055])
    return {'ripado.jpg': _jpg(col), 'ripado_n.png': _png(normal_from_height(np.where(gap, 0.0, 1.0) * 0.8 + f * 0.2, 2.5))}

def lamina():
    """grelha de ventilacao do embasamento (imagens 14 e 16 do usuario, 16/10/2026): lamas horizontais PRETAS de 5 cm de passo,
    cada uma inclinada (aresta de cima com um fio de luz, face escura, sombra funda no vao). Ladrilho de 0,30 m = 6 lamas, em faixa
    LISA (as lamas modeladas do FBX serrilhavam e viravam pontilhado a distancia; a textura desfoca bem nos mipmaps).
    Convencao: a imagem esta invertida em relacao ao mundo (v cresce com y) — a aresta de cima da lama fica no FIM de cada passo."""
    H = W = 240
    y = (np.arange(H)[:, None] % 40) / 40.0 + np.zeros((1, W))
    cor = np.where(y < 0.20, 0.020,                                   # vao entre lamas: quase preto
          np.where(y > 0.88, 0.075,                                   # aresta de cima: fio de luz (16/10: era 0,150, brilhava em zebra a distancia)
                   0.050 + 0.045 * (np.clip((y - 0.20) / 0.68, 0, 1)) ** 1.5))   # face da lama: preto, mais claro para cima
    f = fbm(H, W, 3, 6) * 0.25 + 0.88
    col = np.stack([cor * f, cor * f, cor * f * 1.05], -1)
    hm = np.where(y < 0.20, 0.0, 0.25 + 0.75 * ((y - 0.20) / 0.80))   # perfil em dente de serra (lama inclinada)
    return {'lamina.jpg': _jpg(np.clip(col * 1.5, 0, 1), 90), 'lamina_n.png': _png(normal_from_height(hm, 2.0))}

def interior():
    H = W = 256
    y = np.linspace(0, 1, H)[:, None]; x = np.linspace(0, 1, W)[None, :]
    g = np.exp(-((x - 0.5) ** 2) * 6) * np.exp(-((y - 0.35) ** 2) * 4)
    col = np.array([1.0, 0.74, 0.42]) * (0.35 + 0.65 * g[..., None])
    col *= (1 - ((x * 5 % 1 < 0.5) * 0.12)[..., None])
    return {'interior.jpg': _jpg(col, 90)}

def forro_marquise():
    """forro da marquise da entrada (Render 10): reguas estreitas de teca/nogueira saturada,
    32 por ladrilho de 3 m, contraste leve, junta fina escura. Reguas correm ao longo de v
    (N-S na marquise)."""
    H = W = 1024
    r = np.random.default_rng(91)
    n = 32
    y = np.arange(H)[:, None]
    k = (y * n) // H
    t = (y * n % H) / H
    tom = r.uniform(0.0, 1.0, n); tom = 0.5 + (tom - 0.5) * 0.9
    veio = ruido_fft(H, W, 1.2, 92, (1.0, 14.0))
    esc = np.array([0.22, 0.115, 0.050]); cla = np.array([0.40, 0.220, 0.100])   # 16/10: nogueira (Render 6: media #4e3622), nao laranja
    base = esc[None, None, :] * (1 - tom[k][..., None]) + cla[None, None, :] * tom[k][..., None]
    col = np.broadcast_to(base, (H, W, 3)) * (0.88 + 0.24 * veio[..., None])
    junta = np.repeat((t < 0.06) | (t > 0.94), W, 1)
    col = col.copy(); col[junta] *= 0.5
    hm = np.where(junta, 0.0, 1.0) * 0.7 + veio * 0.3
    nb = io.BytesIO(); normal_from_height(hm, 2.0).resize((512, 512), Image.BILINEAR).save(nb, 'JPEG', quality=84)
    return {'forro_marquise.jpg': _jpg(np.clip(col, 0, 1), 88), 'forro_marquise_n.jpg': nb.getvalue()}


def poca_luz():
    """poca de luz quente do spot no piso: radial creme-quente, alfa 0,35 -> 0"""
    N = 128
    yy, xx = np.mgrid[0:N, 0:N]; d = np.hypot(xx - N / 2 + 0.5, yy - N / 2 + 0.5) / (N / 2)
    a = np.clip(1 - d, 0, 1) ** 2.4 * 0.24
    rgba = np.zeros((N, N, 4), np.uint8)
    rgba[..., 0] = 255; rgba[..., 1] = 214; rgba[..., 2] = 160; rgba[..., 3] = (a * 255).astype(np.uint8)
    b = io.BytesIO(); Image.fromarray(rgba, 'RGBA').save(b, 'PNG'); return {'poca_luz.png': b.getvalue()}


def fenda():
    """fenda de vidro (Render 3): 36 placas empilhadas, montante escuro de 3-4 px entre elas;
    algumas placas acesas (quente), as demais neutras escuras. v=0 no pe"""
    H, W = 1152, 64
    img = np.zeros((H, W, 3), np.float32)
    acesas = {5, 6, 9, 17, 21, 22, 29, 30, 31, 34, 35}      # contadas de cima
    ph = H // 36
    for i in range(36):
        y0 = i * ph
        cor = (0.58, 0.47, 0.42) if i in acesas else (0.25, 0.25, 0.26)
        img[y0:y0 + ph, :] = cor
        img[y0:y0 + 4, :] = 0.03          # montante
    img[:, :3] = 0.03; img[:, -3:] = 0.03
    # linha 0 da imagem = topo do vao (v=0 no topo)
    return {'fenda.png': _png(Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)))}


def facho():
    """lavagem de parede por luminarias de piso (Render 3): um leque estreito e brilhante junto ao chao que
    abre e se dissolve com a altura (a cada 1,05 m, os leques vizinhos se somam em manchas suaves), com o veio
    vertical da madeira modulando a luz. Sem borda dura. v=0 no pe (linha de baixo da imagem)."""
    H, W = 768, 256
    v = (1 - np.linspace(0, 1, H))[:, None]; u = np.linspace(0, 1, W, endpoint=False)[None, :]
    a = np.zeros((H, W))
    for k, off in enumerate((0.0, 0.5)):                       # 2 leques por periodo de 2,1 m
        du = ((u - off + 0.5) % 1) - 0.5
        larg = 0.035 + 0.30 * v ** 0.8
        a += np.exp(-(du / larg) ** 2) * np.exp(-3.1 * v ** 0.9)
    r = np.random.default_rng(5)
    fibra = np.repeat(np.convolve(r.random(W * 2), np.ones(3) / 3, 'same')[:W][None, :], H, 0)
    a = a * (0.72 + 0.5 * fibra) * (1 - v) ** 0.5
    a = np.clip(a * 0.62, 0, 1)
    rgba = np.zeros((H, W, 4), np.uint8)
    rgba[..., 0] = 255; rgba[..., 1] = 176; rgba[..., 2] = 104; rgba[..., 3] = (a * 255).astype(np.uint8)
    b = io.BytesIO(); Image.fromarray(rgba, 'RGBA').save(b, 'PNG'); return {'facho.png': b.getvalue()}


def logo():
    return {'logo.png': open(os.path.join(HERE, 'logo.png'), 'rb').read()}


_CACHE = {}

def render(nome):
    """bytes da textura pelo nome de arquivo usado em gen_fachada.py."""
    if not _CACHE:
        for fn in (madeira, madeira_painel, madeira_forro, muro_pedra, painel_escuro, cortina, pedra_preta, paralelepipedo, placa_pedra, marmore_preto, lounge_parede,
                   ripado_cinza, monolito, lavagem, forro_marquise, poca_luz, fenda, facho, pedra, ripado, lamina, interior, logo):
            _CACHE.update(fn())
    return _CACHE[nome]
