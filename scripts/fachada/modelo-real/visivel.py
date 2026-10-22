"""Quais faces do modelo (CASCA-NOVA + TERREO + REVIT) aparecem de fora?
Uma BVH unica com todos os triangulos (scene.ray_cast com 6.700 objetos e lento demais).
Raios paralelos de varias direcoes; atravessa vidro (alpha < .5) ate 2 camadas.
Raios que sobem (olhar de baixo para os forros) partem do plano do chao, fora da torre.
Visibilidade dos pavimentos-tipo agregada por (malha, posicao relativa ao pavimento)."""
import bpy, sys, os, json, math, collections, mathutils, time
import numpy as np
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:]
SRC, out = argv[0], argv[1]
PASSO = float(argv[2]) if len(argv) > 2 else 0.3
bpy.ops.wm.read_factory_settings(use_empty=True)
for f in ["CASCA-NOVA", "TERREO", "REVIT"]:
    antes = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=os.path.join(SRC, f + ".fbx"))
    for o in set(bpy.data.objects) - antes:
        o["origem"] = f
for o in list(bpy.data.objects):
    if o.type == "MESH" and o.name.startswith(("PivotDoor", "porta multiplas")):
        bpy.data.objects.remove(o)

def base(n):
    return n.rstrip("0123456789.").rstrip("_ -")

def alpha_mat(m):
    if not m or not m.use_nodes:
        return 1.0
    b = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    return b.inputs["Alpha"].default_value if b else 1.0

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

# triangulos em coordenadas de mundo
V_all, T_all, dono = [], [], []          # dono[tri] = (obj idx, poligono)
objs = [o for o in bpy.data.objects if o.type == "MESH"]
vidro_tri = []
nv = 0
for oi, o in enumerate(objs):
    me = o.data
    me.calc_loop_triangles()
    n = len(me.vertices)
    co = np.empty(n * 3, np.float64); me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    M = np.array(o.matrix_world)
    w = co @ M[:3, :3].T + M[:3, 3]
    lt = me.loop_triangles
    k = len(lt)
    tv = np.empty(k * 3, np.int64); lt.foreach_get("vertices", tv)
    tp = np.empty(k, np.int64); lt.foreach_get("polygon_index", tp)
    tm = np.empty(k, np.int64); lt.foreach_get("material_index", tm)
    vid = [alpha_mat(s.material) < 0.5 for s in o.material_slots] or [False]
    V_all.append(w); T_all.append(tv.reshape(-1, 3) + nv); nv += n
    dono.append(np.stack([np.full(k, oi), tp], 1))
    vidro_tri.append(np.array([vid[m] if m < len(vid) else False for m in tm], bool))
V = np.concatenate(V_all); T = np.concatenate(T_all); D = np.concatenate(dono); G = np.concatenate(vidro_tri)
t0 = time.time()
bvh = BVHTree.FromPolygons(V.tolist(), T.tolist(), all_triangles=True)
print("BVH", len(T), "tri", round(time.time() - t0, 1), "s")

lo, hi = V.min(0), V.max(0)
ctr = mathutils.Vector(((lo + hi) / 2).tolist())
R = float(np.linalg.norm(hi - lo)) / 2 + 2
torre_lo, torre_hi = np.array([0.5, 2.5]), np.array([49.5, 47.0])   # pegada da torre (CASCA)

vis_tri = np.zeros(len(T), bool)
raios = 0; t0 = time.time()

def lanca(orig, d):
    global raios
    for camada in range(3):
        loc, nrm, idx, dist = bvh.ray_cast(orig, d, 4 * R)
        raios += 1
        if idx is None:
            return
        vis_tri[idx] = True
        if not G[idx] or camada >= 2:
            return
        orig = loc + d * 0.004

for el in (-60, -35, -15, 5, 25, 50, 80):
    for az in range(0, 360, 15 if abs(el) < 70 else 90):
        a, e = math.radians(az), math.radians(el)
        d = mathutils.Vector((-math.cos(a) * math.cos(e), -math.sin(a) * math.cos(e), -math.sin(e)))
        if el < 0:
            # olhar de baixo: raios saem do chao (z = 0.5) ao redor da torre
            ext = 60.0
            for x in np.arange(lo[0] - ext, hi[0] + ext, PASSO * 1.5):
                for y in np.arange(lo[1] - ext, hi[1] + ext, PASSO * 1.5):
                    if torre_lo[0] < x < torre_hi[0] and torre_lo[1] < y < torre_hi[1]:
                        continue
                    lanca(mathutils.Vector((x, y, 0.5)), d)
        else:
            u = d.orthogonal().normalized(); v = d.cross(u).normalized()
            n = int(2 * R / PASSO)
            for i in range(n):
                base_i = ctr - d * (R + 5) + u * (-R + i * PASSO)
                for j in range(n):
                    lanca(base_i + v * (-R + j * PASSO), d)
    print("el", el, raios, round(time.time() - t0), "s", flush=True)

# agrega por chave (pavimentos iguais -> uniao)
vis = collections.defaultdict(set)
for t in np.nonzero(vis_tri)[0]:
    oi, p = D[t]
    vis[chave(objs[oi])].add(int(p))

tri_vis = collections.Counter(); tri_tot = collections.Counter()
pref_vis = collections.Counter(); pref_tot = collections.Counter()
for o in objs:
    fs = vis.get(chave(o), set())
    for p in o.data.polygons:
        t = len(p.vertices) - 2
        s = o.material_slots[p.material_index].material if p.material_index < len(o.material_slots) else None
        m = s.name if s else "-"
        k = o["origem"] + ":" + m
        tri_tot[k] += t; pref_tot[o["origem"] + ":" + base(o.name)] += t
        if p.index in fs:
            tri_vis[k] += t; pref_vis[o["origem"] + ":" + base(o.name)] += t
json.dump({"raios": raios, "seg": time.time() - t0,
           "vis_total": sum(tri_vis.values()), "tot": sum(tri_tot.values()),
           "por_mat": [(m, tri_vis[m], tri_tot[m]) for m, _ in tri_tot.most_common()],
           "por_pref": [(p, pref_vis[p], pref_tot[p]) for p, _ in pref_tot.most_common()],
           "faces": {k: sorted(v) for k, v in vis.items()}}, open(out, "w"))
print("OK", raios, round(time.time() - t0), sum(tri_vis.values()))
