import pymupdf

doc = pymupdf.open("tmp_audit_ielts/downloads/book_10.pdf")

def lineview(fp):
    page = doc[fp-1]
    chars = []
    for b in page.get_text("rawdict")["blocks"]:
        if b.get("type") != 0: continue
        for l in b.get("lines", []):
            for s in l.get("spans", []):
                for c in s.get("chars", []):
                    chars.append((round(c["origin"][1],1), round(c["origin"][0],1), c["c"], s["font"], round(s["size"],1)))
    chars.sort()
    lines = []
    for y, x, ch, font, size in chars:
        if lines and abs(lines[-1][0] - y) < 4.5:
            lines[-1][1].append((x, ch, font, size))
        else:
            lines.append((y, [(x, ch, font, size)]))
    print(f"===== fp{fp} (doc[{fp-1}]) lineview, {len(lines)} lines =====")
    for y, items in lines:
        items.sort()
        txt = "".join(i[1] for i in items)
        fonts = sorted(set(i[2] for i in items))
        x0 = items[0][0]
        print(f"y={y:6.1f} x0={x0:6.1f} fonts={','.join(fonts)[:60]:60s} | {txt[:110]}")

for fp in (152, 153):
    lineview(fp)

print()
print("===== Batang chars with span font =====")
for fp in (152, 153):
    page = doc[fp-1]
    tt = page.get_texttrace()
    rows = []
    for sp in tt:
        fname = sp.get('font','')
        if 'Batang' in fname:
            for ch in sp['chars']:
                rows.append((round(ch[2][1],1), round(ch[2][0],1), ch[0], ch[1], fname))
    rows.sort()
    print(f"--- fp{fp}: {len(rows)} batang chars ---")
    for y, x, u, gid, fname in rows:
        print(f"  y={y:7.1f} x={x:6.1f} uni={u:3d} {chr(u)!r:5s} gid={gid:3d} font={fname}")
