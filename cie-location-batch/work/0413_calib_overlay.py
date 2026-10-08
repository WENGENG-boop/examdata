"""Calibration: render MS p18/p19 full display pages with the new region bboxes overlaid in red.

Also dumps text words (display coords) near the region boundaries so edge cuts can be judged.
"""
from __future__ import annotations

from pathlib import Path

import pymupdf

TMP = Path(__file__).resolve().parents[1] / "tmp/0413/2026-Jun-11"
MS = TMP / "0413_s26_ms_11.pdf"
OUT = TMP / "probe"

P18 = [
    ("Q10", [95.0, 84.8, 166.5, 735.2]),
    ("Q11ai", [200.0, 84.8, 318.5, 735.2]),
    ("Q11aii", [318.5, 84.8, 476.0, 735.2]),
    ("zoom160-240", [160.0, 63.6, 240.0, 735.2]),
]
P19 = [
    ("Q11bi", [96.0, 68.8, 250.5, 729.2]),
    ("Q11bii", [250.5, 68.8, 309.0, 729.2]),
    ("zoom235-275", [235.0, 63.6, 275.0, 729.2]),
]

doc = pymupdf.open(MS)
for pno, regions in ((18, P18), (19, P19)):
    page = doc[pno - 1]
    print(f"=== page {pno} rect={page.rect} rotation={page.rotation}")
    # full display page
    pix = page.get_pixmap(matrix=pymupdf.Matrix(1.0, 1.0), alpha=False)
    print("   full pixmap", pix.width, "x", pix.height)
    out = pymupdf.open()
    pg = out.new_page(width=pix.width, height=pix.height)
    pg.insert_image(pg.rect, pixmap=pix)
    for label, bbox in regions:
        r = pymupdf.Rect(bbox) * page.rotation_matrix
        pg.draw_rect(r, color=(1, 0, 0), width=1.2)
        pg.insert_text((r.x0 + 3, r.y0 + 11), label, fontsize=10, color=(1, 0, 0))
        print(f"   {label}: bbox={bbox} -> display {r}")
    pg.get_pixmap(matrix=pymupdf.Matrix(1.0, 1.0), alpha=False).save(str(OUT / f"calib-p{pno}.png"))
    out.close()
    # word dump near boundaries
    words = page.get_text("words")
    print(f"   words={len(words)}")
    for w in words:
        x0, y0, x1, y1, text = w[0], w[1], w[2], w[3], w[4]
        r = pymupdf.Rect(x0, y0, x1, y1) * page.rotation_matrix
        dy = r.y0
        if pno == 18 and 60 <= dy <= 500:
            print(f"   y_d={dy:7.1f} x_d=[{r.x0:6.1f},{r.x1:6.1f}] {text!r}")
        if pno == 19 and 60 <= dy <= 330:
            print(f"   y_d={dy:7.1f} x_d=[{r.x0:6.1f},{r.x1:6.1f}] {text!r}")
doc.close()
