# -*- coding: utf-8 -*-
import json, fitz

BR = r"C:/Users/weo/Desktop/api/cie-location-batch"
qp = fitz.open(BR + "/tmp/0472/2025-Jun-22/0472_s25_qp_22.pdf")
ms = fitz.open(BR + "/tmp/0472/2025-Jun-22/0472_s25_ms_22.pdf")


def chars(page):
    for b in page.get_text("rawdict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                for c in s["chars"]:
                    yield c


print("=== a) QP p2: items with x0>470 in y 59..762 ===")
page = qp[1]
rows = []
for c in chars(page):
    bx0, by0, bx1, by1 = c["bbox"]
    if bx0 > 470 and 59 <= by0 <= 762:
        rows.append(("char", c["c"], [round(v, 1) for v in c["bbox"]]))
for dr in page.get_drawings():
    r = dr["rect"]
    if r.x0 > 470 and r.x1 < 560 and 59 <= r.y0 <= 762:
        rows.append(("draw", None, [round(r.x0, 1), round(r.y0, 1), round(r.x1, 1), round(r.y1, 1)]))
for t in rows[:40]:
    print(t)
print("count:", len(rows))

print()
print("=== b) QP p14/p15/p16 text head ===")
for i in (13, 14, 15):
    t = qp[i].get_text("text")
    print(f"p{i+1} chars={len(t)}")
    print(t[:400].replace("\n", " | "))
    print("---")

print()
print("=== c) QP p12: drawings 540<x1<600 ===")
page = qp[11]
for dr in page.get_drawings():
    r = dr["rect"]
    if r.x1 > 540 and r.x0 < 600:
        print([round(r.x0, 1), round(r.y0, 1), round(r.x1, 1), round(r.y1, 1)])

print()
print("=== d) QP p11: x<75 items full list (count + y range) ===")
page = qp[10]
n = 0
ymin, ymax = 1e9, -1e9
for c in chars(page):
    bx0, by0, bx1, by1 = c["bbox"]
    if bx1 < 75 and c["c"].strip():
        n += 1
        ymin = min(ymin, by0); ymax = max(ymax, by1)
print("count:", n, "y-range:", round(ymin, 1), "-", round(ymax, 1))
print("--- p11 chars y>748 (x<560) ---")
for c in chars(page):
    bx0, by0, bx1, by1 = c["bbox"]
    if by0 > 748 and bx0 < 560 and c["c"].strip():
        print(repr(c["c"]), [round(v, 1) for v in c["bbox"]])

print()
print("=== e) MS per-region text/draw extent (from index) ===")
idx = json.load(open(BR + "/indexes/0472/2025-Jun-22/cie-index.json", encoding="utf-8"))
def union_in_range(page, y0, y1, want_draw, want_text, xmax=560.0):
    x0 = y0b = 1e9; x1 = y1b = -1e9
    if want_text:
        for c in chars(page):
            bx0, by0, bx1, by1 = c["bbox"]
            if bx0 >= xmax or by1 < y0 or by0 > y1:
                continue
            x0 = min(x0, bx0); y0b = min(y0b, by0); x1 = max(x1, bx1); y1b = max(y1b, by1)
    if want_draw:
        for dr in page.get_drawings():
            r = dr["rect"]
            if r.x0 >= xmax or r.y1 < y0 or r.y0 > y1:
                continue
            x0 = min(x0, r.x0); y0b = min(y0b, r.y0); x1 = max(x1, r.x1); y1b = max(y1b, r.y1)
    if x1 < 0:
        return None
    return [round(v, 1) for v in (x0, y0b, x1, y1b)]

seen = set()
for q in idx["questions"]:
    for r in q["ms"]:
        key = (r["page"], tuple(r["bbox"]))
        if key in seen:
            continue
        seen.add(key)
        pg = ms[r["page"] - 1]
        bb = r["bbox"]
        t = union_in_range(pg, bb[1], bb[3], False, True)
        d = union_in_range(pg, bb[1], bb[3], True, False)
        flag = " <<< text beyond 540.3" if (t and t[2] > 540.3) else ""
        print(q["question"], "p", r["page"], bb, "text:", t, "draw:", d, flag)

print()
print("=== f) MS p6/p7 text in y 32.4..87.6 ===")
for i in (5, 6):
    pg = ms[i]
    t = pg.get_text("text", clip=fitz.Rect(60, 32.4, 560, 87.6)).strip()
    print(f"MS p{i+1}: {t[:300]!r}")
    t2 = pg.get_text("text", clip=fitz.Rect(60, 25, 560, 100)).strip()
    print("  wider:", repr(t2[:300]))

print()
print("=== g) QP p10 text blocks (people area) ===")
page = qp[9]
for b in page.get_text("dict")["blocks"]:
    if b["type"] != 0:
        continue
    x0, y0, x1, y1 = [round(v, 1) for v in b["bbox"]]
    txt = "".join(s["text"] for l in b["lines"] for s in l["spans"])[:70]
    print([x0, y0, x1, y1], repr(txt))

print()
print("=== g2) QP p11 text blocks (beaches area, first 30) ===")
page = qp[10]
for b in page.get_text("dict")["blocks"][:30]:
    if b["type"] != 0:
        continue
    x0, y0, x1, y1 = [round(v, 1) for v in b["bbox"]]
    txt = "".join(s["text"] for l in b["lines"] for s in l["spans"])[:70]
    print([x0, y0, x1, y1], repr(txt))
