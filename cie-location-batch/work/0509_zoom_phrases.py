# -*- coding: utf-8 -*-
"""High-zoom renders of the 3(e)(iii)/(iv) phrase lines on p9/p15 (text fidelity check)."""
import os
import pymupdf

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QP = os.path.join(BASE, 'tmp', '0509', '2026-Jun-11', '0509_s26_qp_11.pdf')
PROBE = os.path.join(BASE, 'tmp', '0509', '2026-Jun-11', 'probe')
Z = 8
doc = pymupdf.open(QP)
jobs = [
    ('phrase-iii-p15.png', 15, (92.4, 52.0, 330.0, 80.0)),
    ('phrase-iii-p09.png', 9, (92.4, 52.0, 330.0, 80.0)),
    ('phrase-iv-p15.png', 15, (92.4, 128.0, 330.0, 156.0)),
    ('phrase-iv-p09.png', 9, (92.4, 128.0, 330.0, 156.0)),
]
os.makedirs(PROBE, exist_ok=True)
for name, pg, clip in jobs:
    page = doc[pg - 1]
    pix = page.get_pixmap(matrix=pymupdf.Matrix(Z, Z), clip=pymupdf.Rect(*clip), alpha=False)
    pix.save(os.path.join(PROBE, name))
    print(name, pix.width, pix.height)
