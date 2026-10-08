import sys, struct
import pymupdf as fitz

pdf = r"C:/Users/weo/Desktop/api/tmp_audit_ielts/downloads/book_10.pdf"
doc = fitz.open(pdf)

def get_tables(buf):
    numTables = struct.unpack(">H", buf[4:6])[0]
    tables = {}
    for i in range(numTables):
        off = 12 + 16*i
        tag = buf[off:off+4].decode('latin1')
        checksum, offset, length = struct.unpack(">III", buf[off+4:off+16])
        tables[tag] = (offset, length)
    return tables

def parse_cmap(buf, tables):
    off, ln = tables['cmap']
    b = buf[off:off+ln]
    numTables = struct.unpack(">H", b[2:4])[0]
    maps = {}
    for i in range(numTables):
        pid, eid, suboff = struct.unpack(">HHI", b[4+8*i:12+8*i])
        sub = b[suboff:]
        fmt = struct.unpack(">H", sub[0:2])[0]
        m = {}
        if fmt == 6:
            firstCode, entryCount = struct.unpack(">HH", sub[6:10])
            arr = struct.unpack(">%dH" % entryCount, sub[10:10+2*entryCount])
            for j, g in enumerate(arr):
                if g: m[firstCode + j] = g
        elif fmt == 4:
            segX2 = struct.unpack(">H", sub[6:8])[0]
            seg = segX2 // 2
            ends = struct.unpack(">%dH" % seg, sub[14:14+segX2])
            starts = struct.unpack(">%dH" % seg, sub[16+segX2:16+2*segX2])
            deltas = struct.unpack(">%dh" % seg, sub[16+2*segX2:16+3*segX2])
            roPos = 16+3*segX2
            rangeOffs = struct.unpack(">%dH" % seg, sub[roPos:roPos+segX2])
            for i2 in range(seg):
                if starts[i2] == 0xFFFF: continue
                for c in range(starts[i2], ends[i2]+1):
                    if rangeOffs[i2] == 0:
                        g = (c + deltas[i2]) & 0xFFFF
                    else:
                        gp = roPos + 2*i2 + rangeOffs[i2] + 2*(c - starts[i2])
                        if gp+2 > len(sub): continue
                        g = struct.unpack(">H", sub[gp:gp+2])[0]
                        if g: g = (g + deltas[i2]) & 0xFFFF
                    if g: m[c] = g
        maps[(pid, eid, fmt)] = m
    return maps

for xref, label in [(1383, 'TT2-11.1pt'), (1378, 'TT3-7.1pt')]:
    name, ext, ftype, buf = doc.extract_font(xref)
    tables = get_tables(buf)
    maps = parse_cmap(buf, tables)
    print("=====", xref, label, name)
    for k, m in maps.items():
        rev = {g: c for c, g in m.items()}
        items = sorted(m.items())
        print("  cmap", k, "size", len(m))
        print("   code->gid:", [(hex(c), g) for c, g in items])
        print("   gid->code:", {g: hex(c) for c, g in items})

# texttrace on p153
page = doc[152]
tr = page.get_texttrace()
print("== texttrace spans (p153) ==")
for span in tr:
    font = span.get('font', '')
    if 'Batang' in font:
        chars = span.get('chars', [])
        out = []
        for ch in chars:
            out.append(ch)
        print("font=", font, "size=", span.get('size'), "chars=", out[:20])
