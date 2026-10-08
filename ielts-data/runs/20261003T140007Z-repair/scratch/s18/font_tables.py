import sys, struct, json
import pymupdf as fitz

pdf = r"C:/Users/weo/Desktop/api/tmp_audit_ielts/downloads/book_10.pdf"
doc = fitz.open(pdf)

def get_tables(buf):
    if len(buf) < 12: return None
    numTables = struct.unpack(">H", buf[4:6])[0]
    tables = {}
    for i in range(numTables):
        off = 12 + 16*i
        if off+16 > len(buf): break
        tag = buf[off:off+4].decode('latin1')
        checksum, offset, length = struct.unpack(">III", buf[off+4:off+16])
        tables[tag] = (offset, length)
    return tables

def parse_post(buf, tables):
    if 'post' not in tables: return None
    off, ln = tables['post']
    b = buf[off:off+ln]
    ver = struct.unpack(">I", b[0:4])[0]
    if ver != 0x00020000:
        return {'version': hex(ver)}
    numGlyphs = struct.unpack(">H", b[32:34])[0]
    idx = struct.unpack(">%dH" % numGlyphs, b[34:34+2*numGlyphs])
    # custom names start after index array
    pos = 34 + 2*numGlyphs
    names = []
    while pos < len(b):
        l = b[pos]
        if l == 0: break
        names.append(b[pos+1:pos+1+l].decode('latin1'))
        pos += 1 + l
    result = []
    for i, ix in enumerate(idx):
        if ix < 258:
            result.append(ix)  # standard mac name index
        else:
            j = ix - 258
            result.append(names[j] if j < len(names) else '?%d' % ix)
    return {'version': '2.0', 'numGlyphs': numGlyphs, 'glyphNames': result}

def parse_cmap(buf, tables):
    if 'cmap' not in tables: return None
    off, ln = tables['cmap']
    b = buf[off:off+ln]
    numTables = struct.unpack(">H", b[2:4])[0]
    out = []
    for i in range(numTables):
        pid, eid, suboff = struct.unpack(">HHI", b[4+8*i:12+8*i])
        fmt = struct.unpack(">H", b[suboff:suboff+2])[0]
        out.append({'platform': pid, 'encoding': eid, 'format': fmt, 'suboff': suboff})
    # parse format 4 and 12 maps
    maps = {}
    for t in out:
        sub = b[t['suboff']:]
        fmt = t['format']
        m = {}
        if fmt == 4:
            segX2 = struct.unpack(">H", sub[6:8])[0]
            seg = segX2 // 2
            ends = struct.unpack(">%dH" % seg, sub[14:14+segX2])
            starts = struct.unpack(">%dH" % seg, sub[16+segX2:16+2*segX2])
            deltas = struct.unpack(">%dh" % seg, sub[16+2*segX2:16+3*segX2])
            rangeOffPos = 16+3*segX2
            rangeOffs = struct.unpack(">%dH" % seg, sub[rangeOffPos:rangeOffPos+segX2])
            for i in range(seg):
                if starts[i] == 0xFFFF: continue
                for c in range(starts[i], ends[i]+1):
                    if rangeOffs[i] == 0:
                        g = (c + deltas[i]) & 0xFFFF
                    else:
                        gpos = rangeOffPos + 2*i + rangeOffs[i] + 2*(c - starts[i])
                        if gpos+2 > len(sub): continue
                        g = struct.unpack(">H", sub[gpos:gpos+2])[0]
                        if g: g = (g + deltas[i]) & 0xFFFF
                    if g: m[c] = g
        elif fmt == 12:
            nGroups = struct.unpack(">I", sub[12:16])[0]
            for i in range(nGroups):
                s, e, g0 = struct.unpack(">III", sub[16+12*i:28+12*i])
                for c in range(s, min(e, s+2000)+1):
                    m[c] = g0 + (c - s)
        t['mapSize'] = len(m)
        if m: maps[(t['platform'], t['encoding'], fmt)] = m
    return {'tables': out, 'maps': maps}

for xref, label in [(1383, 'Batang-11.1 TT2'), (1378, 'Batang-7.1 TT3')]:
    name, ext, ftype, buf = doc.extract_font(xref)
    print("=====", xref, name, ext, ftype, "len=", len(buf) if buf else 0)
    if not buf: continue
    tables = get_tables(buf)
    print("tables:", sorted(tables.keys()) if tables else None)
    post = parse_post(buf, tables) if tables else None
    if post and post.get('glyphNames'):
        gn = post['glyphNames']
        print("post v2 numGlyphs=", post['numGlyphs'])
        print("glyphNames[0:80]=", gn[:80])
    else:
        print("post:", post)
    cm = parse_cmap(buf, tables) if tables else None
    if cm:
        print("cmap tables:", cm['tables'])
        for k, m in cm['maps'].items():
            # print mapping for ASCII letters/digits
            interesting = {c: g for c, g in m.items() if 0x20 <= c < 0x7F}
            print("cmap", k, "ascii sample:", dict(sorted(interesting.items())[:60]))
