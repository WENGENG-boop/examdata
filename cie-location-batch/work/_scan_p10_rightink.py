# -*- coding: utf-8 -*-
"""p10 右缘墨迹判定: 文本转储 + 逐 pt 密度剖面。只读本地 PDF。"""
import pymupdf

BR = "C:/Users/weo/Desktop/api/cie-location-batch"
qp = pymupdf.open(f"{BR}/tmp/0472/2026-Jun-22/0472_s26_qp_22.pdf")
p = qp[9]
print("fonts:", p.get_fonts())

print("== words with x1>480 (whole page) ==")
for w in p.get_text("words"):
    r = w[:4]
    if r[2] > 480:
        print(f"  [{r[0]:.1f},{r[1]:.1f},{r[2]:.1f},{r[3]:.1f}] {w[4]!r}")

print("== dict spans with x1>480 (whole page) ==")
for b in p.get_text("dict")["blocks"]:
    if b.get("type") != 0:
        continue
    for ln in b["lines"]:
        for sp in ln["spans"]:
            sb = sp["bbox"]
            if sb[2] > 480:
                print(f"  span [{sb[0]:.1f},{sb[1]:.1f},{sb[2]:.1f},{sb[3]:.1f}] {sp['font']!r} sz{sp['size']:.1f} {sp['text'][:100]!r}")


def profile(y0, y1, x0=440, x1=545, z=8, th=200, label=""):
    pix = p.get_pixmap(matrix=pymupdf.Matrix(z, z), clip=pymupdf.Rect(x0, y0, x1, y1), alpha=False)
    s = pix.samples
    W, H, n = pix.width, pix.height, pix.n
    colc = [0] * W
    for yy in range(H):
        b = yy * W * n
        for xx in range(W):
            i = b + xx * n
            r, g, bl = s[i], s[i + 1], s[i + 2]
            if r < th or g < th or bl < th:
                colc[xx] += 1
    vals = [sum(colc[k:k + z]) for k in range(0, W, z)]
    dens = "".join("." if v == 0 else str(min(9, v // 8 + 1)) for v in vals)
    print(f"[{label}] y{y0}-{y1} x{x0}..{x0 + len(vals) - 1} density(1-9 per pt, .=0):")
    print("   ", dens)


profile(125, 218, label="box a row")
profile(222, 315, label="box b row")
profile(319, 412, label="box c row")
profile(416, 509, label="box d row")
profile(512, 605, label="box e row")
print("done")
