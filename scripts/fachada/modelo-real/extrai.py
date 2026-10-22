"""Blender: le CASCA-NOVA + TERREO + REVIT, mantem so as faces visiveis de fora
(visivel.json), separa o 1o pavimento-tipo em studios (P..-Snn) e faixa, e grava
triangulos em .npz para o empacotador (gen_fachada_real.py).

Saida (coordenadas do site: X leste, Y cima, Z sul, metros):
  partes.npz  -> para cada parte: pos (n,3), nrm (n,3), mat (n_tri,) nomes FBX
  partes.json -> lista de partes {nome, tipo: unidade|faixa|fixo, studio, fachada}, niveis
"""
import bpy, sys, os, json, math, collections, mathutils
import numpy as np
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:]
SRC, VIS, OUT = argv[0], argv[1], argv[2]
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
for f in ["CASCA-NOVA", "TERREO", "REVIT"]:
    antes = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=os.path.join(SRC, f + ".fbx"))
    for o in set(bpy.data.objects) - antes:
        o["origem"] = f
for o in list(bpy.data.objects):
    if o.type == "MESH" and o.name.startswith(("PivotDoor", "porta multiplas")):
        bpy.data.objects.remove(o)

# O Blender importa o conteudo dos grupos de pavimento do CASCA-NOVA.fbx 2,08 m ACIMA de onde a
# cena do Twinmotion (e a propria casca) os tem: portas/lajes ficavam acima da guarda, que
# parecia pendurada abaixo do piso ("sacadas de ponta cabeca"). dados/deltas_tm.json traz, por
# objeto do 1o pavimento e das placas (brises), o deslocamento mundo Twinmotion - Blender (eixos
# do Blender). Guardas e demais pecas do 1o pavimento sem par no Twinmotion seguem a regra geral:
# guarda -0,80 (origem 5,76 -> 4,96 no TM) e o resto -2,083
_DELTAS = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados", "deltas_tm.json")))
_grupos0 = sorted([o for o in bpy.data.objects if o.name.startswith("Group") and o.parent is None
                   and o.get("origem") == "CASCA-NOVA"], key=lambda o: o.matrix_world.translation.z)
# todos os pavimentos (nao so o 1o): o raio que acha o forro da sacada bate na laje do andar de cima
_pav1 = {c.name for g in _grupos0 for c in g.children_recursive}
_n = 0
for o in list(bpy.data.objects):
    if o.type != "MESH" or o.get("origem") != "CASCA-NOVA":
        continue
    if o.name in _DELTAS:
        d = _DELTAS[o.name]
    elif o.name in _pav1:
        d = [0, 0, -0.80] if o.name.startswith("Railing") else [0, 0, -2.083]
    else:
        continue
    o["delta_tm"] = d; _n += 1          # aplicado logo abaixo, depois de guardar as chaves de visibilidade
print("deslocados pelo Twinmotion:", _n)

def base(n):
    return n.rstrip("0123456789.").rstrip("_ -")

grupos = sorted([o for o in bpy.data.objects if o.name.startswith("Group") and o.parent is None
                 and o.get("origem") == "CASCA-NOVA"], key=lambda o: o.matrix_world.translation.z)
pav_de = {}
for i, g in enumerate(grupos):
    for c in g.children_recursive:
        pav_de[c.name] = (i, g)

def chave(o):
    if o.name in pav_de:
        i, g = pav_de[o.name]
        rel = g.matrix_world.inverted() @ o.matrix_world.translation
        return json.dumps(["PAV", o.data.name, round(rel.x, 2), round(rel.y, 2), round(rel.z, 2)])
    return json.dumps(["SOLTO", o.name])

vis = json.load(open(VIS))["faces"]
# a chave de visibilidade usa a posicao ORIGINAL (visivel.json foi calculado antes do deslocamento)
_CHAVE = {o.name: chave(o) for o in bpy.data.objects if o.type == "MESH"}
chave = lambda o: _CHAVE[o.name]
for o in bpy.data.objects:
    if o.type == "MESH" and o.get("delta_tm") is not None:
        o.matrix_world = mathutils.Matrix.Translation(mathutils.Vector(list(o["delta_tm"]))) @ o.matrix_world

# as quatro placas das PONTAS das alas (leste da barra: Line3246/3247; sul da haste: Line3248/3249)
# sao madeira (Chestnut) na cena do Twinmotion de 09/2026, mas nos renders de 08/2026 sao paineis
# escuros com moldura clara, e o letreiro fica no alto da ponta leste. Ganham sufixo para o
# empacotador tratar diferente da placa noroeste (Line1052), que e madeira nos dois.
PONTAS = {"Line3246", "Line3247", "Line3248", "Line3249"}
# o nucleo escuro do canto interno (Line070, 'elevadores') e os pilares do terreo entram inteiros:
# o teste de visibilidade so pegava 149 das 1216 faces e o centro do predio ficava oco
INTEIROS = {"Line070", "Block:*U317"}

def tris_de(o, so_visiveis=True):
    """triangulos (mundo) de o: pos (k,3,3), nrm (k,3,3), material FBX por triangulo"""
    me = o.data
    me.calc_loop_triangles()
    fs = set(vis.get(chave(o), [])) if so_visiveis else None
    n = len(me.vertices)
    co = np.empty(n * 3); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
    M = np.array(o.matrix_world); R3 = M[:3, :3]
    w = co @ R3.T + M[:3, 3]
    lt = me.loop_triangles; k = len(lt)
    tv = np.empty(k * 3, np.int64); lt.foreach_get("vertices", tv); tv = tv.reshape(-1, 3)
    tl = np.empty(k * 3, np.int64); lt.foreach_get("loops", tl); tl = tl.reshape(-1, 3)
    tp = np.empty(k, np.int64); lt.foreach_get("polygon_index", tp)
    tm = np.empty(k, np.int64); lt.foreach_get("material_index", tm)
    cn = np.empty(len(me.loops) * 3); me.corner_normals.foreach_get("vector", cn); cn = cn.reshape(-1, 3)
    nm = np.linalg.inv(R3).T
    cn = cn @ nm.T; cn /= np.maximum(np.linalg.norm(cn, axis=1, keepdims=True), 1e-9)
    if fs is not None:
        sel = np.array([p in fs for p in tp], bool)
        tv, tl, tm = tv[sel], tl[sel], tm[sel]
    nomes = [s.material.name if s.material else "-" for s in o.material_slots] or ["-"]
    if o.name in PONTAS:
        nomes = [n + "_ponta" for n in nomes]
    # caixilho das portas e janelas dos studios: escuro nos renders (a guarda fica em aluminio claro)
    if o.name.startswith(("SlidingDoor", "AwningWindow")):
        nomes = [n + "_porta" if n == "aluminium.001" else n for n in nomes]
    mats = [nomes[m] if m < len(nomes) else "-" for m in tm]
    return w[tv], cn[tl], mats

# ---- referencia de alinhamento: vidros das portas de correr e guardas no 1o pavimento
g0 = grupos[0]
p0 = [c for c in g0.children_recursive if c.type == "MESH"]
def centro(o):
    return sum((o.matrix_world @ mathutils.Vector(v) for v in o.bound_box), mathutils.Vector()) / 8
guardas = [(centro(c), c) for c in p0 if base(c.name) == "Railing"]
portas = [(centro(c), c) for c in p0 if base(c.name) == "SlidingDoor"]

# faces pela posicao das guardas (ver planta tipo): x~3.95 oeste, x~21.4 leste_haste,
# y~43.7 norte, y~26.2 sul_barra. Numeracao igual a gen_fachada.unit_meshes()
def face_da_guarda(c):
    if abs(c.x - 3.95) < 1: return "oeste"
    if abs(c.x - 21.4) < 1: return "leste_haste"
    if abs(c.y - 43.69) < 1: return "norte"
    if abs(c.y - 26.24) < 1: return "sul_barra"
    return None
ancoras = collections.defaultdict(list)
for c, o in guardas:
    ancoras[face_da_guarda(c)].append(c)
num = {}
for face, cs in ancoras.items():
    if face == "oeste":        cs.sort(key=lambda c: -c.y); ks = range(1, 11)     # 01 ao norte
    elif face == "leste_haste": cs.sort(key=lambda c: c.y); ks = range(11, 17)    # 11 ao sul
    elif face == "norte":      cs.sort(key=lambda c: c.x); ks = range(17, 25)     # 17 a oeste
    else:                      cs.sort(key=lambda c: -c.x); ks = range(25, 31)    # 25 a leste
    for k, c in zip(ks, cs):
        num[k] = (face, c)
assert len(num) == 30, sorted(num)
NORMAL = {"oeste": (-1, 0), "leste_haste": (1, 0), "norte": (0, 1), "sul_barra": (0, -1)}

def studio_de(c):
    """studio cuja faixa de fachada contem o ponto c (ate 7 m para dentro), ou None"""
    melhor = None
    for k, (face, a) in num.items():
        nx, ny = NORMAL[face]
        prof = (a.x - c.x) * nx + (a.y - c.y) * ny          # >0 = para dentro do predio
        ao_longo = abs((c.x - a.x) * ny - (c.y - a.y) * nx)
        if -1.0 < prof < 7.0 and ao_longo < 1.97:
            if melhor is None or prof < melhor[1]:
                melhor = (k, prof)
    return melhor[0] if melhor else None

# ---- nivel do piso acabado (topo da laje) do 1o pavimento e pe-direito
piso0 = min((c.matrix_world @ mathutils.Vector(v)).z for _, c in portas for v in c.bound_box)
PE = grupos[1].matrix_world.translation.z - grupos[0].matrix_world.translation.z

# ---- transformacao FBX -> site. Alinha os vidros das portas de correr com a maquete atual
# (gen_fachada: vidro a 0,30 m para fora do contorno, contorno oeste em X=0 e norte em Z=0)
def face_da_porta(c):
    k = studio_de(c)
    return num[k][0] if k else None
x_vidro_oeste = float(np.median([c.x for c, o in portas if face_da_porta(c) == "oeste"]))
y_vidro_norte = float(np.median([c.y for c, o in portas if face_da_porta(c) == "norte"]))
X0 = x_vidro_oeste + 0.30
Y1 = y_vidro_norte - 0.30
def para_site(p):        # p (...,3) FBX -> site
    q = np.empty_like(p)
    q[..., 0] = p[..., 0] - X0
    q[..., 1] = p[..., 2]
    q[..., 2] = Y1 - p[..., 1]
    return q
def nrm_site(n):
    q = np.empty_like(n)
    q[..., 0] = n[..., 0]; q[..., 1] = n[..., 2]; q[..., 2] = -n[..., 1]
    return q

# ---- forro da sacada (para o spot): raio para cima a partir do meio da sacada
todos_v, todos_t = [], []; nv = 0
for o in p0 + [c for c in grupos[1].children_recursive if c.type == "MESH"]:
    me = o.data; me.calc_loop_triangles()
    co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
    M = np.array(o.matrix_world); w = co @ M[:3, :3].T + M[:3, 3]
    tv = np.empty(len(me.loop_triangles) * 3, np.int64); me.loop_triangles.foreach_get("vertices", tv)
    todos_v.append(w); todos_t.append(tv.reshape(-1, 3) + nv); nv += len(w)
bvh = BVHTree.FromPolygons(np.concatenate(todos_v).tolist(), np.concatenate(todos_t).tolist(), all_triangles=True)

partes, arrays = [], {}
def guarda_parte(nome, tipo, pos, nrm, mats, **extra):
    if not len(pos):
        return
    arrays[nome + "_pos"] = para_site(np.asarray(pos)).astype(np.float32)
    arrays[nome + "_nrm"] = nrm_site(np.asarray(nrm)).astype(np.float32)
    arrays[nome + "_mat"] = np.array(mats)
    partes.append(dict(nome=nome, tipo=tipo, tri=len(pos), **extra))

# ---- o que fica atras da cortina acesa (ou dentro do predio) nao vai para o site
INTERNOS = {"parede intrerna", "porcelanato bianco marfil30 90", "portal",
            "Porcelanato Calacata", "gesso", "cromo aluminio", "BRE50_aço_escovado",
            "Material", "mdf lterrino", "crema", "VIDRO elev", "luz elevador", "luz elevador2",
            "preto visor", "ventilocao"}
AREA_MIN = 1e-4          # m2: bisel e tampa de perfil menores que 1 cm2 somem a 20 m
ANC = np.array([[num[k][1].x, num[k][1].y] for k in range(1, 31)])
NRM = np.array([NORMAL[num[k][0]] for k in range(1, 31)], float)
def prof_studio(xy):
    """(studio 1..30 ou 0, profundidade para dentro a partir da guarda) por ponto"""
    d = ANC[None, :, :] - xy[:, None, :]
    prof = (d * NRM[None]).sum(-1)
    along = np.abs(d[..., 0] * NRM[None, :, 1] - d[..., 1] * NRM[None, :, 0])
    ok = (prof > -1.0) & (prof < 7.0) & (along < 1.97)
    p = np.where(ok, prof, np.inf)
    k = p.argmin(1)
    tem = np.isfinite(p.min(1))
    return np.where(tem, k + 1, 0), p[np.arange(len(xy)), k]
prof_porta = {}
for k in range(1, 31):
    cs = np.array([[c.x, c.y] for c, o in portas if studio_de(c) == k])
    prof_porta[k] = float(prof_studio(cs)[1].mean())

def filtra(P, N, Mt, pavimento):
    if not len(P):
        return P, N, Mt
    Mt = np.array(Mt)
    area = 0.5 * np.linalg.norm(np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]), axis=1)
    vidro = np.char.find(np.char.lower(Mt.astype(str)), "vidro") >= 0
    manter = (area >= AREA_MIN) | vidro
    interno = np.isin(Mt, list(INTERNOS))
    if pavimento:
        k, prof = prof_studio(P.mean(1)[:, :2])
        pp = np.array([prof_porta.get(int(x), 0.0) for x in k])
        na_sacada = (k > 0) & (prof < pp - 0.15)
        manter &= ~interno | na_sacada
    else:
        manter &= ~interno
    return P[manter], N[manter], list(Mt[manter])

# ---- 1o pavimento: studios e faixa
por_studio = collections.defaultdict(lambda: ([], [], []))
faixa = ([], [], [])
for o in p0:
    P, N, Mt = filtra(*tris_de(o), pavimento=True)
    if not len(P):
        continue
    k = studio_de(centro(o)) if base(o.name) == "SlidingDoor" else None
    alvo = por_studio[k] if k else faixa
    alvo[0].append(P); alvo[1].append(N); alvo[2].extend(Mt)
y_g0 = grupos[0].matrix_world.translation.z
spots = {}
for k, (face, a) in num.items():
    ps = [(c, o) for c, o in portas if studio_de(c) == k]
    pos, nrm, mats = por_studio[k]
    # cortina acesa 0,25 m atras do vidro das portas, do tamanho do vao
    lo = mathutils.Vector((1e9,) * 3); hi = -lo
    for c, o in ps:
        for v in o.bound_box:
            w = o.matrix_world @ mathutils.Vector(v)
            lo = mathutils.Vector(map(min, lo, w)); hi = mathutils.Vector(map(max, hi, w))
    nx, ny = NORMAL[face]
    if nx:   # face perpendicular a x
        xc = (lo.x + hi.x) / 2 - nx * 0.25
        q = [(xc, lo.y, lo.z + 0.05), (xc, hi.y, lo.z + 0.05), (xc, hi.y, hi.z - 0.05), (xc, lo.y, hi.z - 0.05)]
    else:
        yc = (lo.y + hi.y) / 2 - ny * 0.25
        q = [(lo.x, yc, lo.z + 0.05), (hi.x, yc, lo.z + 0.05), (hi.x, yc, hi.z - 0.05), (lo.x, yc, hi.z - 0.05)]
    q = np.array(q); nn = np.array([nx, ny, 0.0])
    tri = np.array([[q[0], q[1], q[2]], [q[0], q[2], q[3]]])
    pos.append(tri); nrm.append(np.tile(nn, (2, 3, 1))); mats.extend(["__cortina__"] * 2)
    # spot no forro da sacada: meio do vao, 1 m para fora do vidro
    meio = mathutils.Vector(((lo.x + hi.x) / 2 + nx * 1.0, (lo.y + hi.y) / 2 + ny * 1.0, piso0 + 1.5))
    hit = bvh.ray_cast(meio, mathutils.Vector((0, 0, 1)), 4.0)
    zf = (hit[0].z if hit[0] else piso0 + PE - 0.3) - 0.01
    r = 0.09
    disco = [mathutils.Vector((meio.x + r * math.cos(t), meio.y + r * math.sin(t), zf)) for t in np.linspace(0, 2 * math.pi, 9)[:-1]]
    for i in range(8):
        a_, b_ = disco[i], disco[(i + 1) % 8]
        pos.append(np.array([[ (meio.x, meio.y, zf), tuple(b_), tuple(a_)]]))
        nrm.append(np.tile([0, 0, -1.0], (1, 3, 1))); mats.append("__spot__")
    spots[k] = zf
    guarda_parte(f"S{k:02d}", "unidade", np.concatenate(pos), np.concatenate(nrm), mats, studio=k, fachada=face)
guarda_parte("FAIXA", "faixa", np.concatenate(faixa[0]), np.concatenate(faixa[1]), faixa[2])

# ---- o que nao e pavimento-tipo: casca/cobertura (CASCA) e terreo (TERREO + REVIT)
fixos = collections.defaultdict(lambda: ([], [], []))
for o in bpy.data.objects:
    if o.type != "MESH" or o.name in pav_de:
        continue
    P, N, Mt = filtra(*tris_de(o, so_visiveis=o.name not in INTEIROS), pavimento=False)
    if not len(P):
        continue
    grupo = "CASCA" if o.get("origem") == "CASCA-NOVA" else "TERREO"
    fixos[grupo][0].append(P); fixos[grupo][1].append(N); fixos[grupo][2].extend([o["origem"] + ":" + m for m in Mt])
for g, (P, N, Mt) in fixos.items():
    guarda_parte(g, "fixo", np.concatenate(P), np.concatenate(N), Mt)

np.savez_compressed(os.path.join(OUT, "partes.npz"), **arrays)
json.dump({"partes": partes, "y_pav0": y_g0, "piso0": piso0, "pe": PE, "n_pav": len(grupos),
           "niveis_pav": [g.matrix_world.translation.z for g in grupos],
           "X0": X0, "Y1": Y1}, open(os.path.join(OUT, "partes.json"), "w"), indent=1)
print("OK", len(partes), sum(p["tri"] for p in partes), "piso0", round(piso0, 3), "PE", round(PE, 3), "X0", round(X0, 2), "Y1", round(Y1, 2))
