# -*- coding: utf-8 -*-
"""p14 right-edge: true y-extent of ink per x-band (fix: scan all rows per column)."""
import pymupdf as fitz

QP = r"C:/Users/weo/Desktop/api/cie-location-batch/tmp/0472/2025-Jun-21/0472_s25_qp_21.pdf"
Z = 4
TH = 235

doc = fitz.open(QP)
page = doc[13]  # p14
clip = fitz.Rect(490, 0, 612, 792)
pm = page.get_pixmap(clip=clip, matrix=fitz.Matrix(Z, Z), colorspace=fitz.csGRAY)
w, h, s = pm.width, pm.height, pm.samples

bands = [(500,510),(510,520),(520,528),(528,536),(536,544),(544,552),(552,560),(560,566),(566,574),(574,582),(582,592)]
print("=== p14 true ink y-extent per x-band ===")
for x0, x1 in bands:
    c0, c1 = int((x0 - 490) * Z), int((x1 - 490) * Z)
    ymin, ymax, count = None, None, 0
    row_has = set()
    for c in range(c0, min(c1, w)):
        for r in range(h):
            if s[r * w + c] < TH:
                count += 1
                row_has.add(r)
                if ymin is None or r < ymin: ymin = r
                if ymax is None or r > ymax: ymax = r
    if count:
        print(f"x[{x0},{x1}): ink pixels={count}  y-extent=[{ymin/Z:.1f},{ymax/Z:.1f}]  rows_touched={len(row_has)}/{h}")
    else:
        print(f"x[{x0},{x1}): EMPTY")

# also: for band x[528,552.2], print histogram of ink rows in coarse buckets of 20pt
print()
print("=== x[528,553] ink row histogram (20pt buckets) ===")
c0, c1 = int((528 - 490) * Z), int((553 - 490) * Z)
buckets = {}
for c in range(c0, min(c1, w)):
    for r in range(h):
        if s[r * w + c] < TH:
            b = int(r / Z / 20) * 20
            buckets[b] = buckets.get(b, 0) + 1
for b in sorted(buckets):
    print(f"  y[{b},{b+20}): {buckets[b]} px")
doc.close()
print("DONE")
