# -*- coding: utf-8 -*-
"""Per-page scan: ink outside the [70.4,542.4] content box (bands/brackets expected)."""
import pymupdf as fitz

QP = r"C:/Users/weo/Desktop/api/cie-location-batch/tmp/0472/2025-Jun-21/0472_s25_qp_21.pdf"
Z = 2
TH = 235

doc = fitz.open(QP)
for pi in range(len(doc)):
    page = doc[pi]
    pm = page.get_pixmap(matrix=fitz.Matrix(Z, Z), colorspace=fitz.csGRAY)
    w, h, s = pm.width, pm.height, pm.samples
    def band_stats(x0, x1):
        c0, c1 = int(x0*Z), min(int(x1*Z), w)
        n = 0; ymin=None; ymax=None
        rows = set()
        for c in range(c0, c1):
            for r in range(h):
                if s[r*w + c] < TH:
                    n += 1; rows.add(r)
                    if ymin is None or r<ymin: ymin=r
                    if ymax is None or r>ymax: ymax=r
        if n == 0: return "EMPTY"
        return f"{n}px y[{ymin/Z:.0f},{ymax/Z:.0f}] rows={len(rows)}"
    left = band_stats(46.0, 70.4)
    right = band_stats(542.4, 565.7)
    far_right = band_stats(585.7, 612.0)
    # also: full ink extent
    print(f"p{pi+1:2d}  x[46,70.4): {left:30s} | x[542.4,565.7): {right:30s} | x[585.7,612): {far_right}")
doc.close()
print("DONE")
