#!/usr/bin/env python3
"""Confere se um .glb (por exemplo, exportado do Blender) serve para a secao #fachada.

Uso:  python3 scripts/fachada/check_glb.py caminho/do/modelo.glb

O que js/fachada3d.js exige do arquivo:
  - um no por studio com nome P<pav>-S<studio> (dois digitos cada, ex. P09-S12).
    E por esse nome que o clique acha a unidade e o painel mostra pavimento/studio;
  - dentro de cada no de studio, malhas com material EMISSIVO (cor de emissao
    diferente de preto). E a emissao que "acende"; sem ela o clique nao muda nada.
    Material chamado 'luz_quente' faz o papel de teto da sacada, o resto de janela;
  - extras.fachada em cada no de studio (no Blender: Custom Property 'fachada'
    e exportar com Include > Custom Properties): norte | sul_barra | leste_haste | oeste.
    Opcional, mas sem ele o painel nao diz a face e a camera nao gira ate ela;
  - metros, Y para cima, torre perto da origem: a camera mira (24.5, 28, 22) e
    orbita entre 70 e 340 m. Fora disso os limites em fachada3d.js precisam mudar.
Orcamento de peso para o celular: ate 6 MB e 150 mil triangulos.
Le so o JSON do glTF; nao precisa de biblioteca.
"""
import json
import re
import struct
import sys

RX = re.compile(r'^P(\d\d)-S(\d\d)$')
FACES = {'norte', 'sul_barra', 'leste_haste', 'oeste'}
MAX_MB, MAX_TRI = 6.0, 150_000
CENTRO, RAIO_ORBITA = (24.5, 28, 22), 70


def le_glb(caminho):
    dados = open(caminho, 'rb').read()
    magia, versao, _ = struct.unpack('<4sII', dados[:12])
    if magia != b'glTF':
        sys.exit(f'ERRO: {caminho} nao e um .glb (glTF binario). No Blender: Export > glTF 2.0 > Format: glTF Binary (.glb).')
    tam, tipo = struct.unpack('<I4s', dados[12:20])
    if tipo != b'JSON':
        sys.exit('ERRO: primeiro bloco do .glb nao e JSON.')
    return json.loads(dados[20:20 + tam]), len(dados)


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    g, tamanho = le_glb(sys.argv[1])
    nodes, meshes, mats, acc = g.get('nodes', []), g.get('meshes', []), g.get('materials', []), g.get('accessors', [])
    erros, avisos = [], []

    # triangulos e caixa envolvente (pelos min/max das posicoes, sem transformar)
    tri = 0
    lo, hi = [1e9] * 3, [-1e9] * 3
    for m in meshes:
        for p in m.get('primitives', []):
            if 'indices' in p:
                tri += acc[p['indices']]['count'] // 3
            else:
                tri += acc[p['attributes']['POSITION']]['count'] // 3
            a = acc[p['attributes']['POSITION']]
            if 'min' in a:
                lo = [min(x, y) for x, y in zip(lo, a['min'])]
                hi = [max(x, y) for x, y in zip(hi, a['max'])]

    def emissivo(mi):
        m = mats[mi] if mi is not None and mi < len(mats) else {}
        return any(v > 0 for v in m.get('emissiveFactor', [0, 0, 0])) or 'emissiveTexture' in m

    def malhas_do(i, acum):
        n = nodes[i]
        if 'mesh' in n:
            acum.append(n['mesh'])
        for c in n.get('children', []):
            malhas_do(c, acum)
        return acum

    unidades, sem_emissao, sem_face, face_ruim = {}, [], [], []
    for i, n in enumerate(nodes):
        m = RX.match(n.get('name', ''))
        if not m:
            continue
        nome = n['name']
        if nome in unidades:
            erros.append(f'nome repetido: {nome}')
        unidades[nome] = (int(m.group(1)), int(m.group(2)))
        prims = [p for mi in malhas_do(i, []) for p in meshes[mi].get('primitives', [])]
        if not prims:
            erros.append(f'{nome} nao tem malha: nada para acender nem para clicar')
        elif not any(emissivo(p.get('material')) for p in prims):
            sem_emissao.append(nome)
        face = (n.get('extras') or {}).get('fachada')
        if face is None:
            sem_face.append(nome)
        elif face not in FACES:
            face_ruim.append(f'{nome}={face}')

    print(f'arquivo: {sys.argv[1]}')
    print(f'peso: {tamanho / 1e6:.2f} MB (limite {MAX_MB:.0f}) | triangulos: {tri:,} (limite {MAX_TRI:,})'.replace(',', '.'))
    if lo[0] < 1e9:
        print(f'caixa (malhas, sem transformacoes): x {lo[0]:.1f}..{hi[0]:.1f}  y {lo[1]:.1f}..{hi[1]:.1f}  z {lo[2]:.1f}..{hi[2]:.1f} m')
        cx, cy, cz = [(a + b) / 2 for a, b in zip(lo, hi)]
        if max(abs(cx - CENTRO[0]), abs(cz - CENTRO[2])) > RAIO_ORBITA or hi[1] < 20 or hi[1] > 200:
            avisos.append(f'a torre esta longe do alvo da camera {CENTRO} ou fora de escala (altura ate {hi[1]:.0f} m). '
                          'Confira unidade = metros e Y para cima no export, ou ajuste CENTRO/DIST_* em js/fachada3d.js.')
    pavs = sorted({p for p, _ in unidades.values()})
    print(f'studios nomeados: {len(unidades)} em {len(pavs)} pavimentos' + (f' (P{pavs[0]:02d} a P{pavs[-1]:02d})' if pavs else ''))

    if not unidades:
        erros.append('nenhum no chamado P<pav>-S<studio> (ex. P09-S12): o clique nao vai achar nenhuma unidade')
    else:
        por_pav = {}
        for p, s in unidades.values():
            por_pav.setdefault(p, set()).add(s)
        tamanhos = {len(v) for v in por_pav.values()}
        if len(tamanhos) > 1:
            avisos.append('pavimentos com quantidades diferentes de studios: ' +
                          ', '.join(f'P{p:02d}={len(v)}' for p, v in sorted(por_pav.items()) if len(v) != max(tamanhos)))
    if sem_emissao:
        erros.append(f'{len(sem_emissao)} studios sem material emissivo (nao acendem), ex.: {", ".join(sem_emissao[:5])}. '
                     'No Blender: Principled BSDF > Emission com cor diferente de preto.')
    if sem_face:
        avisos.append(f'{len(sem_face)} studios sem extras.fachada (painel sem a face, camera nao gira ate ela), ex.: {", ".join(sem_face[:3])}. '
                      'Blender: Custom Property "fachada" no objeto + export com Include > Custom Properties.')
    if face_ruim:
        avisos.append('valor de fachada desconhecido: ' + ', '.join(face_ruim[:5]) + f' (aceitos: {", ".join(sorted(FACES))})')
    if tamanho / 1e6 > MAX_MB:
        avisos.append(f'acima de {MAX_MB:.0f} MB: pesado para 4G. Exporte com compressao Draco ou reduza texturas.')
    if tri > MAX_TRI:
        avisos.append(f'acima de {MAX_TRI:,} triangulos: o celular vai engasgar. Use o modificador Decimate.'.replace(',', '.'))
    if 'KHR_draco_mesh_compression' in g.get('extensionsUsed', []):
        avisos.append('usa Draco: js/fachada3d.js ainda nao carrega o DRACOLoader. Me avise para ligar, ou exporte sem Draco.')

    for a in avisos:
        print('AVISO:', a)
    for e in erros:
        print('ERRO:', e)
    print('RESULTADO:', 'NAO SERVE ainda' if erros else ('serve, com avisos' if avisos else 'serve'))
    sys.exit(1 if erros else 0)


if __name__ == '__main__':
    main()
