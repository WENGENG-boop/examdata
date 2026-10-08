import re, zlib
import pymupdf as fitz

pdf = r"C:/Users/weo/Desktop/api/tmp_audit_ielts/downloads/book_10.pdf"
doc = fitz.open(pdf)

def get_cs_text(page):
    parts = []
    for xref in page.get_contents():
        d = doc.xref_stream(xref)
        parts.append(d)
    return b"\n".join(parts)

def tokenize(bs):
    # crude but effective PDF content tokenizer for our needs
    toks = []
    i = 0
    n = len(bs)
    while i < n:
        c = bs[i:i+1]
        if c in b" \t\r\n":
            i += 1; continue
        if c == b"%":
            j = bs.find(b"\n", i)
            i = n if j < 0 else j+1
            continue
        if c == b"(":
            j = i+1; depth = 1; buf = b""
            while j < n and depth > 0:
                ch = bs[j:j+1]
                if ch == b"\\":
                    buf += bs[j:j+2]; j += 2; continue
                if ch == b"(": depth += 1
                elif ch == b")":
                    depth -= 1
                    if depth == 0: break
                buf += ch; j += 1
            toks.append(("str", buf))
            i = j+1; continue
        if c == b"<" and bs[i+1:i+2] != b"<":
            j = bs.find(b">", i)
            toks.append(("hex", bs[i+1:j]))
            i = j+1; continue
        if c == b"[":
            toks.append(("arr", None)); i += 1; continue
        if c == b"]":
            toks.append(("arr_end", None)); i += 1; continue
        m = re.match(rb"[^\s\(\)\[\]<>/]+", bs[i:])
        if m:
            t = m.group(0)
            toks.append(("tok", t)); i += len(t); continue
        if c == b"/":
            m = re.match(rb"/[^\s\(\)\[\]<>/]*", bs[i:])
            t = m.group(0)
            toks.append(("name", t[1:])); i += len(t); continue
        i += 1
    return toks

for pno, label in [(151, 'p152'), (152, 'p153')]:
    page = doc[pno]
    cs = get_cs_text(page)
    toks = tokenize(cs)
    print("=====", label, "content bytes:", len(cs))
    # walk tokens, track Tf and Tm/Td, collect text ops
    fontmap = {}
    for f in page.get_fonts(full=True):
        fontmap[f[4]] = (f[0], f[3])  # res name -> (xref, name)
    cur_font = None
    x = y = 0.0
    out = []
    i = 0
    stack = []
    while i < len(toks):
        t, v = toks[i]
        if t == "name" and v in (b"Tf",): pass
        if t == "tok" and v == b"Tf":
            # previous two: size name
            if i >= 2 and toks[i-1][0] == "tok":
                size = float(toks[i-1][1])
                if toks[i-2][0] == "name":
                    cur_font = (toks[i-2][1].decode(), size)
        elif t == "tok" and v in (b"Tm",):
            if i >= 6:
                vals = []
                ok = True
                for k in range(i-6, i):
                    if toks[k][0] != "tok": ok = False; break
                    vals.append(float(toks[k][1]))
                if ok:
                    x, y = vals[4], vals[5]
        elif t == "tok" and v in (b"Td", b"TD"):
            if i >= 2 and toks[i-1][0] == "tok" and toks[i-2][0] == "tok":
                try:
                    dx, dy = float(toks[i-2][1]), float(toks[i-1][1])
                    x += dx; y += dy
                except: pass
        elif t == "str" and cur_font and cur_font[0].startswith("TT"):
            out.append((cur_font[0], cur_font[1], x, y, v))
        elif t == "hex" and cur_font and cur_font[0].startswith("TT"):
            try:
                hx = v.decode()
                if len(hx) % 2 == 1: hx = hx + "0"
                out.append((cur_font[0], cur_font[1], x, y, bytes.fromhex(hx)))
            except Exception as e:
                pass
        i += 1
    # filter Batang regions: print all ops with font TT2/TT3/TT4 and y in [90, 210] or all
    for (fn, size, xx, yy, b) in out:
        xr, name = fontmap.get(fn, (None, '?'))
        if 'Batang' in (name or ''):
            print(f"{label} font={fn}({name},xref={xr}) size={size} x={xx:.1f} y={yy:.1f} bytes={b!r} hex={b.hex()}")
