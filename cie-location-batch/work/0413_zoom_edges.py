"""Zoom the two open edge questions for 0413 MS: p18 y_d=200 boundary, p19 y_d=250.5 split."""
from __future__ import annotations

from pathlib import Path

import pymupdf

TMP = Path(__file__).resolve().parents[1] / "tmp/0413/2026-Jun-11"
MS = TMP / "0413_s26_ms_11.pdf"
OUT = TMP / "probe"

JOBS = [
    ("zoom-p18-160-240", 18, [160.0, 63.6, 240.0, 735.2], 4.0),
    ("zoom-p19-235-275", 19, [235.0, 63.6, 275.0, 729.2], 5.0),
]

doc = pymupdf.open(MS)
for name, pno, bbox, scale in JOBS:
    page = doc[pno - 1]
    visible = pymupdf.Rect(bbox) * page.rotation_matrix
    pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), clip=visible, alpha=False)
    pix.save(str(OUT / f"{name}.png"))
    print(name, pix.width, "x", pix.height)
doc.close()
