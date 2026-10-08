"""Measure ink extents for 0413 MS p18 row bands vs the mapped region edges (x_d=707.2 etc).

Also locates full-width border lines (rows with high ink coverage) to verify row boundaries.
"""
from __future__ import annotations

from pathlib import Path

import pymupdf

TMP = Path(__file__).resolve().parents[1] / "tmp/0413/2026-Jun-11"
MS = TMP / "0413_s26_ms_11.pdf"

BANDS = {
    18: [("Q10", 95.0, 166.5), ("Q11ai", 200.0, 318.5), ("Q11aii", 318.5, 476.0)],
    19: [("Q11bi", 96.0, 250.5)],
}
SCALE = 2.0
YU0, YU1 = 50.0, 745.0  # unrotated y range -> display x in [47, 742]

doc = pymupdf.open(MS)
for pno, bands in BANDS.items():
    page = doc[pno - 1]
    for label, yd0, yd1 in bands:
        bbox = [yd0, YU0, yd1, YU1]
        r = pymupdf.Rect(bbox) * page.rotation_matrix
        pix = page.get_pixmap(matrix=pymupdf.Matrix(SCALE, SCALE), clip=r, alpha=False)
        w, h, n = pix.width, pix.height, pix.n
        s = pix.samples
        ink_cols = [0] * w
        line_rows = []
        for i in range(h):
            row_ink = 0
            for j in range(w):
                o = (i * w + j) * n
                if s[o] < 160 and s[o + 1] < 160 and s[o + 2] < 160:
                    row_ink += 1
                    ink_cols[j] += 1
            if row_ink > w * 0.6:
                line_rows.append(r.y0 + i / SCALE)
        xs = [r.x0 + j / SCALE for j in range(w)]
        ink = [xs[j] for j in range(w) if ink_cols[j] > 0]
        print(f"p{pno} {label} y_d[{yd0},{yd1}]: ink x_d [{min(ink):.1f} .. {max(ink):.1f}]  (region right edge 707.2 / p19 723.2)")
        print(f"   full-width lines y_d: {[round(v,1) for v in line_rows]}")
        # per-column ink near the right edge
        for j in range(w):
            xd = xs[j]
            if xd >= 700.0 and ink_cols[j] > 0:
                print(f"   col x_d={xd:.1f} ink={ink_cols[j]}")
doc.close()
