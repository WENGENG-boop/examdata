# -*- coding: utf-8 -*-
import fitz

BR = r"C:/Users/weo/Desktop/api/cie-location-batch"
qp = fitz.open(BR + "/tmp/0472/2025-Jun-22/0472_s25_qp_22.pdf")
ms = fitz.open(BR + "/tmp/0472/2025-Jun-22/0472_s25_ms_22.pdf")

print("=== a) QP p10: five person-block extents (text+draw+image, x 60..545) ===")
page = qp[9]
bands = [(150, 245), (245, 340), (340, 440), (440, 535), (535, 640)]
items = []
for b in page.get_text("dict")["blocks"]:
    x0, y0, x1, y1 = b["bbox"]
    if x1 > 545 or x0 < 60 or y1 < 150 or y0 > 645:
        continue
    items.append(("img" if b["type"] == 1 else "txt", [round(v, 1) for v in b["bbox"]]))
for dr in page.get_drawings():
    r = dr["rect"]
    if r.x1 > 545 or r.x0 < 60 or r.y1 < 150 or r.y0 > 645:
        continue
    items.append(("drw", [round(r.x0, 1), round(r.y0, 1), round(r.x1, 1), round(r.y1, 1)]))
for name, (y0, y1) in zip("abcde", bands):
    sel = [it for it in items if it[1][1] >= y0 and it[1][3] <= y1]
    if not sel:
        print(name, "none")
        continue
    bx0 = min(it[1][0] for it in sel); by0 = min(it[1][1] for it in sel)
    bx1 = max(it[1][2] for it in sel); by1 = max(it[1][3] for it in sel)
    kinds = sorted(set(it[0] for it in sel))
    print(name, "extent:", [bx0, by0, bx1, by1], "kinds:", kinds, "n:", len(sel))
    for it in sel:
        print("    ", it)

print()
print("=== b) QP p11: content in y 40..75 (x 60..545) ===")
page = qp[10]
for b in page.get_text("dict")["blocks"]:
    x0, y0, x1, y1 = b["bbox"]
    if y1 >= 40 and y0 <= 75 and x1 > 60 and x0 < 545:
        print("  blk", b["type"], [round(v, 1) for v in (x0, y0, x1, y1)])
for dr in page.get_drawings():
    r = dr["rect"]
    if r.y1 >= 40 and r.y0 <= 75 and r.x1 > 60 and r.x0 < 545:
        print("  drw", [round(r.x0, 1), round(r.y0, 1), round(r.x1, 1), round(r.y1, 1)])

print()
print("=== c) MS p6: text lines in y 400..515 (Q5 rows) ===")
page = ms[5]
d = page.get_text("dict")
for b in d["blocks"]:
    if b["type"] != 0:
        continue
    for l in b["lines"]:
        x0, y0, x1, y1 = l["bbox"]
        if y0 >= 395 and y1 <= 520:
            txt = "".join(s["text"] for s in l["spans"])
            print([round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)], repr(txt[:80]))

print()
print("=== d) QP p13/p14/p15/p16 first/last text lines ===")
for i in (12, 13, 14, 15):
    page = qp[i]
    lines = []
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        for l in b["lines"]:
            txt = "".join(s["text"] for s in l["spans"]).strip()
            if txt:
                lines.append((round(l["bbox"][1], 1), txt[:60]))
    lines.sort()
    print(f"--- p{i+1}: {len(lines)} text lines")
    for y, t in lines[:6]:
        print("   top:", y, repr(t))
    for y, t in lines[-4:]:
        print("   bot:", y, repr(t))

print()
print("=== e) QP p16 drawings (count, extent) ===")
page = qp[15]
drs = page.get_drawings()
print("drawings:", len(drs))
if drs:
    xs = [r for dr in drs for r in (dr["rect"].x0, dr["rect"].x1)]
    ys = [r for dr in drs for r in (dr["rect"].y0, dr["rect"].y1)]
    print("x range:", round(min(xs), 1), round(max(xs), 1), "y range:", round(min(ys), 1), round(max(ys), 1))
