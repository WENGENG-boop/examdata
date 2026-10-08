# -*- coding: utf-8 -*-
import json, fitz

BR = r"C:/Users/weo/Desktop/api/cie-location-batch"

print("=== A. Jun/21 final index: Q5 subs + Q6 ===")
d = json.load(open(BR + "/indexes/0472/2025-Jun-21/cie-index.json", encoding="utf-8"))
for q in d["questions"]:
    n = q["question"]
    if n == "5" or n.startswith("5(") or n.startswith("6"):
        print(n, "| marks=", q["marks"])
        print("   qp:", [(r["page"], r["bbox"]) for r in q["qp"]])
        print("   ms:", [(r["page"], r["bbox"]) for r in q["ms"]])
        print("   notes:", (q.get("notes") or "")[:130])

print()
print("=== B. Jun/22 PDF measurements ===")
qp = fitz.open(BR + "/tmp/0472/2025-Jun-22/0472_s25_qp_22.pdf")
ms = fitz.open(BR + "/tmp/0472/2025-Jun-22/0472_s25_ms_22.pdf")
print("QP pages:", len(qp), "MS pages:", len(ms))


def char_items(page):
    for b in page.get_text("rawdict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                for c in s["chars"]:
                    yield c


def union_bbox(page, xmax=560.0, want_draw=True, want_text=True):
    x0 = y0 = 1e9
    x1 = y1 = -1e9
    if want_text:
        for c in char_items(page):
            bx0, by0, bx1, by1 = c["bbox"]
            if bx0 >= xmax:
                continue
            x0 = min(x0, bx0); y0 = min(y0, by0); x1 = max(x1, bx1); y1 = max(y1, by1)
    if want_draw:
        for dr in page.get_drawings():
            r = dr["rect"]
            if r.x0 >= xmax:
                continue
            x0 = min(x0, r.x0); y0 = min(y0, r.y0); x1 = max(x1, r.x1); y1 = max(y1, r.y1)
    if x1 < 0:
        return None
    return [round(v, 1) for v in (x0, y0, x1, y1)]


def over_right(page, limit=542.4, xmax=560.0):
    n = 0
    ex = []
    for c in char_items(page):
        bx0, by0, bx1, by1 = c["bbox"]
        if bx1 > limit and bx0 < xmax and c["c"].strip():
            n += 1
            if len(ex) < 6:
                ex.append(("char", c["c"], [round(v, 1) for v in c["bbox"]]))
    for dr in page.get_drawings():
        r = dr["rect"]
        if r.x1 > limit and r.x0 < xmax:
            n += 1
            if len(ex) < 6:
                ex.append(("draw", None, [round(r.x0, 1), round(r.y0, 1), round(r.x1, 1), round(r.y1, 1)]))
    return n, ex


print("--- QP per page ---")
for i, page in enumerate(qp):
    cb = union_bbox(page)
    n, ex = over_right(page)
    print(f"QP p{i+1}: rect={page.rect} rot={page.rotation} chars={len(page.get_text('text'))} content={cb} over542={n} {ex}")

print("--- MS per page ---")
for i, page in enumerate(ms):
    cb = union_bbox(page)
    tb = union_bbox(page, want_draw=False)
    db = union_bbox(page, want_text=False)
    n, ex = over_right(page)
    print(f"MS p{i+1}: rect={page.rect} rot={page.rotation} chars={len(page.get_text('text'))} content={cb} text={tb} draw={db} over542={n} {ex}")

print()
print("--- QP p2 detail: rightmost in Q1 y-range 59..762 ---")
page = qp[1]
rmax = -1
rmax_item = None
for c in char_items(page):
    bx0, by0, bx1, by1 = c["bbox"]
    if 59 <= by0 and by1 <= 762 and bx0 < 560 and bx1 > rmax:
        rmax = bx1; rmax_item = ("char", c["c"], [round(v, 1) for v in c["bbox"]])
for dr in page.get_drawings():
    r = dr["rect"]
    if 59 <= r.y0 and r.y1 <= 762 and r.x0 < 560 and r.x1 > rmax:
        rmax = r.x1; rmax_item = ("draw", None, [round(r.x0, 1), round(r.y0, 1), round(r.x1, 1), round(r.y1, 1)])
print("rightmost:", round(rmax, 1), rmax_item)

print()
print("--- QP p11: items with x0<75 ---")
page = qp[10]
for c in char_items(page):
    bx0, by0, bx1, by1 = c["bbox"]
    if bx1 < 75 and c["c"].strip():
        print("char:", repr(c["c"]), [round(v, 1) for v in c["bbox"]])
for dr in page.get_drawings():
    r = dr["rect"]
    if r.x0 < 70:
        print("draw:", [round(r.x0, 1), round(r.y0, 1), round(r.x1, 1), round(r.y1, 1)])

print()
print("--- QP p11: bottom-most content in y 755..792 ---")
for c in char_items(page):
    bx0, by0, bx1, by1 = c["bbox"]
    if by0 > 750 and bx0 < 560 and c["c"].strip():
        print("char:", repr(c["c"]), [round(v, 1) for v in c["bbox"]])

print()
print("--- QP p12: drawings with x1>542 ---")
page = qp[11]
for dr in page.get_drawings():
    r = dr["rect"]
    if r.x1 > 542:
        print("draw:", [round(r.x0, 1), round(r.y0, 1), round(r.x1, 1), round(r.y1, 1)])

print()
print("--- QP p14..p16 content ---")
for i in range(13, len(qp)):
    page = qp[i]
    t = page.get_text("text").strip()
    print(f"p{i+1}: chars={len(t)}; head={t[:150]!r}")
