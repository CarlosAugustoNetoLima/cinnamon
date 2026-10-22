"""Le mapa.pkl/blobs.pkl (ObjectBlobs do .tm salvos com pickle) e lista: material de cada peca, viewpoints.
Uso: python3 mapa.py   (na pasta com blobs.pkl, gerado de sqlite3 CINNAMON-certo-10_000.tm: select guid,data from ObjectBlobs)"""
import pickle, sys, collections, json, re
sys.path.insert(0,'.')
from pb import *
blobs=pickle.load(open('blobs.pkl','rb'))
objs={}
for g,b in blobs.items():
    try: r=top(b)
    except Exception: r=None
    if r: objs[g]=r
def txt(v): return is_text(v) if isinstance(v,bytes) else None
def sub(v): return {f:x for f,w,x in (decode(v) or [])} if isinstance(v,bytes) else {}
def vec(v):
    d=sub(v); out=[]
    for i in (1,2,3,4):
        if i in d and isinstance(d[i],float): out.append(round(d[i],4))
    return out or None
hexg=lambda g: g.replace('-','')
mats={}
for g,(tipo,base,esp,campos) in objs.items():
    if tipo in (1037,1145,1038,1048,1050,1144,1151,1036,1180,1092,1102):
        nome=txt(base.get(4,[b''])[0]); path=txt(base.get(1,[b''])[0]) or ''
        p=sub(esp.get(tipo,[b''])[0]) if tipo in esp else {}
        cor=vec(p.get(2)) if isinstance(p.get(2),bytes) else None
        texs=[txt(x).split('/')[-1][:50] for f,x in p.items() if isinstance(x,bytes) and txt(x) and '/Game/' in txt(x)]
        mats[hexg(g)]=dict(tipo=tipo,nome=nome,path=path.split('/')[-1][:60],cor=cor,texs=[t for t in texs if 'Generic' not in t],params={k:v for k,v in p.items() if isinstance(v,(int,float))})
nodes={}
for g,(tipo,base,esp,campos) in objs.items():
    if tipo!=1071: continue
    nome=txt(base.get(4,[b''])[0]); mesh=(txt(base.get(1,[b''])[0]) or '').split('/')[-1][:40]
    slots={}
    if 1127 in esp:
        for f,w,x in decode(esp[1127][0]) or []:
            if f==4:
                d=sub(x); gid=guid_of(d.get(2,b'')) if isinstance(d.get(2),bytes) else None
                slots[d.get(1,0)]=gid
    tr=None
    if 1001 in esp:
        d=sub(esp[1001][0])
        if 2 in d:
            t=sub(d[2]); pos=vec(t.get(2,b'')); tr=[round(x/100,2) for x in pos] if pos else None
    nodes.setdefault(nome,[]).append(dict(guid=g,mesh=mesh,slots=slots,pos=tr))
vistas=[]
for g,(tipo,base,esp,campos) in objs.items():
    if tipo==1011:
        d=sub(esp[1011][0]); vistas.append(dict(guid=g,modo=d.get(1),pos=vec(d.get(2)),rot=vec(d.get(3)),f4=d.get(4),f5=d.get(5)))
pickle.dump(dict(mats=mats,nodes=nodes,vistas=vistas), open('mapa.pkl','wb'))
if __name__=='__main__':
    print("nos de malha:", sum(len(v) for v in nodes.values()), "nomes distintos:", len(nodes), "materiais:", len(mats), "vistas:", len(vistas))
    fbxn=re.compile(r'^(Box|Line|SlidingDoor|PivotDoor|Railing|AwningWindow|FixedWindow|Shape|Text|Object|terreo|Rectangle|Plane|forro|venezianas|Layer)')
    uso=collections.Counter()
    for n,lst in nodes.items():
        if not n or not fbxn.match(n): continue
        for nd in lst:
            for s,gid in nd['slots'].items():
                m=mats.get(gid); uso[(m['nome'],m['path'],tuple(m['cor'] or []),m['tipo'],tuple(m['texs'][:2])) if m else (gid,'?','',0,())]+=1
    print("\nmateriais nos objetos da casca/terreo: n slots | nome | base | cor linear | tipo | texturas")
    for k,c in uso.most_common(80): print(f"  {c:5d}  {k}")
    print("\nvistas (m, graus):")
    for v in sorted(vistas, key=lambda v: v['pos'] or [0]): print("  ", v)
