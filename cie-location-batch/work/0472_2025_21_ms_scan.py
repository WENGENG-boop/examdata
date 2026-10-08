# -*- coding: utf-8 -*-
"""MS pages scan: ink outside [76,474] content box + row profile to check right edge."""
import pymupdf as fitz

MS = r"C:/Users/weo/Desktop/api/cie-location-batch/tmp/0472/2025-Jun-21/0472_s25_ms_21.pdf"
Z = 2
TH = 235

doc = fitz.open(MS)
for pi in range(len(doc)):
    page = doc[pi]
    pm = page.get_pixmap(matrix=fitz.Matrix(Z, Z), colorspace=fitz.csGRAY)
    w, h, s = pm.width, pm.height, pm.samples
    def band_stats(x0, x1):
        c0, c1 = int(x0*Z), min(int(x1*Z), w)
        n = 0; ymin=None; ymax=None; rows=set()
        for c in range(c0, c1):
            for r in range(h):
                if s[r*w + c] < TH:
                    n += 1; rows.add(r)
                    if ymin is None or r<ymin: ymin=r
                    if ymax is None or r>ymax: ymax=r
        if n == 0: return "EMPTY"
        return f"{n}px y[{ymin/Z:.0f},{ymax/Z:.0f}] rows={len(rows)}"
    # ms page rect? check
    print(f"ms p{pi+1} rect={page.rect.width:.0f}x{page.rect.height:.0f}")
    print(f"   x[40,76):   {band_stats(40, 76)}")
    print(f"   x[474,510): {band_stats(474, 510)}")
    print(f"   x[510,612): {band_stats(510, 612)}")
doc.close()
print("DONE")
