# -*- coding: utf-8 -*-
"""p14 right-edge fine probe: exact rightmost content edge + y-range per x-band."""
import pymupdf as fitz

QP = r"C:/Users/weo/Desktop/api/cie-location-batch/tmp/0472/2025-Jun-21/0472_s25_qp_21.pdf"
Z = 4
TH = 235

doc = fitz.open(QP)
page = doc[13]  # p14
clip = fitz.Rect(490, 0, 612, 792)
pm = page.get_pixmap(clip=clip, matrix=fitz.Matrix(Z, Z), colorspace=fitz.csGRAY)
w, h, s = pm.width, pm.height, pm.samples

# column ink presence (x in clip coords px)
cols = []
for c in range(w):
    has = False
    for r in range(h):
        if s[r * w + c] < TH:
            has = True
            break
    cols.append(has)

# find runs of ink columns
runs = []
in_run = False
start = 0
for i, v in enumerate(cols):
    if v and not in_run:
        in_run = True; start = i
    elif not v and in_run:
        in_run = False
        runs.append((start, i - 1))
if in_run:
    runs.append((start, w - 1))

print("=== p14 ink column runs in x[490,612] (pt coords) ===")
for a, b in runs:
    xa = 490 + a / Z
    xb = 490 + b / Z
    # y-range of ink in this run
    ys = []
    for c in range(a, b + 1):
        for r in range(h):
            if s[r * w + c] < TH:
                ys.append(r)
                break
    y0 = min(ys) / Z
    y1 = max(ys) / Z
    print(f"x[{xa:.1f},{xb:.1f}] width={xb-xa:.1f}pt  ink y-range=[{y0:.1f},{y1:.1f}] (height {y1-y0:.1f})")

doc.close()
print("DONE")
