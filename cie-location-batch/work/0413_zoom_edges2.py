"""Right-edge and top-edge zooms for 0413 MS p18 regions (no text layer on p18)."""
from __future__ import annotations

from pathlib import Path

import pymupdf

TMP = Path(__file__).resolve().parents[1] / "tmp/0413/2026-Jun-11"
MS = TMP / "0413_s26_ms_11.pdf"
OUT = TMP / "probe"

# (name, page, display_rect(x0,y0,x1,y1), scale)
JOBS = [
    ("zoom-p18-right", 18, (620.0, 80.0, 792.0, 490.0), 3.0),
    ("zoom-p18-q11ai-top", 18, (40.0, 180.0, 330.0, 260.0), 4.0),
    ("zoom-p18-q10-top", 18, (40.0, 80.0, 330.0, 175.0), 4.0),
]

doc = pymupdf.open(MS)
for name, pno, dr, scale in JOBS:
    page = doc[pno - 1]
    inv = page.derotation_matrix
    bbox_unrot = pymupdf.Rect(dr) * inv  # display rect -> unrotated bbox
    visible = pymupdf.Rect(bbox_unrot) * page.rotation_matrix
    pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), clip=visible, alpha=False)
    pix.save(str(OUT / f"{name}.png"))
    print(name, "display", dr, "-> unrot", tuple(round(v, 2) for v in bbox_unrot), pix.width, "x", pix.height)
doc.close()
