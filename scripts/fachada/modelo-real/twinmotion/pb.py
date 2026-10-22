"""Decodificador dos ObjectBlobs (TMBL) do Twinmotion 2026 (.tm = SQLite; cada objeto e protobuf).
Blob = 'TMBL' + hdr(len,6) + varint + 0x00 + varint + msg {1: {<tipo>: {1000: base{1 path, 2 guid, 4 nome},
1001: {2: transform(quat, pos cm, escala), 5: filhos}, 1127: {4: {1 slot, 2 guid do material}}}}}.
Tipos: 1071 malha, 1013 grupo, 1037 material, 1145 vidro, 1050 piscina, 1069 arvore, 1011 viewpoint,
1110 midia (render) -> 1137.2 aponta o objeto 1112 com a camera. TM (x, y) = Blender (y, x), z igual."""
import struct, re

def varint(b, i):
    r = 0; s = 0
    while True:
        c = b[i]; i += 1
        r |= (c & 0x7f) << s; s += 7
        if not c & 0x80: return r, i

def decode(b, depth=0, maxdepth=6):
    """lista de (campo, wire, valor); valor de len-delimited: tenta sub-mensagem, senao bytes"""
    out = []; i = 0; n = len(b)
    try:
        while i < n:
            tag, i = varint(b, i)
            f, w = tag >> 3, tag & 7
            if w == 0:
                v, i = varint(b, i); out.append((f, 0, v))
            elif w == 1:
                v = struct.unpack_from('<d', b, i)[0]; i += 8; out.append((f, 1, v))
            elif w == 5:
                v = struct.unpack_from('<f', b, i)[0]; i += 4; out.append((f, 5, v))
            elif w == 2:
                ln, i = varint(b, i); chunk = b[i:i + ln]; i += ln
                out.append((f, 2, chunk))
            else:
                return None
    except Exception:
        return None
    return out if i == n else None

def is_text(chunk):
    try:
        s = chunk.decode('utf-8')
    except UnicodeDecodeError:
        return None
    return s if s and all(32 <= ord(c) < 127 or c in '\n\t' or ord(c) > 127 for c in s) else None

def tree(b, depth=0, maxdepth=5, lim=40):
    msg = decode(b)
    lines = []
    if msg is None: return lines
    for k, (f, w, v) in enumerate(msg[:lim]):
        pad = '  ' * depth
        if w == 2:
            t = is_text(v)
            if t is not None and len(t) >= 2:
                lines.append(f"{pad}{f}: \"{t[:110]}\"")
            elif len(v) == 16 and depth < maxdepth and not (decode(v) and len(decode(v)) <= 2 and all(x[1] != 2 for x in decode(v))):
                lines.append(f"{pad}{f}: guid? {v.hex()}")
            else:
                sub = decode(v) if depth < maxdepth else None
                if sub and len(v) > 2:
                    lines.append(f"{pad}{f}: {{  ({len(v)} B)")
                    lines += tree(v, depth + 1, maxdepth, lim)
                    lines.append(f"{pad}}}")
                else:
                    lines.append(f"{pad}{f}: bytes[{len(v)}] {v[:24].hex()}")
        else:
            lines.append(f"{pad}{f}: {v!r}")
    if len(msg) > lim: lines.append('  ' * depth + f"... +{len(msg) - lim}")
    return lines

def guid_of(chunk):
    """campo tipo {1: 16 bytes} -> hex do guid"""
    m = decode(chunk)
    if m and len(m) == 1 and m[0][1] == 2 and len(m[0][2]) == 16:
        return m[0][2].hex()
    return None

def strip_header(blob):
    # TMBL + 8 bytes? o protobuf comeca no '0a' do 1o campo
    i = blob.find(b'\x0a', 4)
    return blob[i:]

def body(blob):
    """TMBL + hdr(len,6) + varint(len) + 0x00 + varint(len2) + protobuf"""
    i = 4
    hl = blob[i]; i += 1 + hl
    _, i = varint(blob, i)
    flag = blob[i]; i += 1
    _, i = varint(blob, i)
    return blob[i:], flag

def top(blob):
    """-> (tipo, campos da base {2:guid,4:nome,...}, campos especificos, msg completa)"""
    b, flag = body(blob)
    m = decode(b)
    if not m or m[0][0] != 1 or m[0][1] != 2: return None
    inner = decode(m[0][2])
    if not inner or inner[0][1] != 2: return None
    tipo = inner[0][0]
    campos = decode(inner[0][2]) or []
    base = {}; esp = {}
    for f, w, v in campos:
        if f == 1000 and w == 2:
            for f2, w2, v2 in decode(v) or []:
                base.setdefault(f2, []).append(v2)
        else:
            esp.setdefault(f, []).append(v)
    return tipo, base, esp, campos
