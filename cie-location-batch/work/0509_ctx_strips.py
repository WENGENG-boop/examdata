# -*- coding: utf-8 -*-
"""Render context + control edge strips for the 0509 ambiguous boundaries."""
import os
import pymupdf

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QP = os.path.join(BASE, 'tmp', '0509', '2026-Jun-11', '0509_s26_qp_11.pdf')
PROBE = os.path.join(BASE, 'tmp', '0509', '2026-Jun-11', 'probe')
Z = 4
doc = pymupdf.open(QP)
jobs = [
    # control edge windows (y1 +/- 15)
    ('ctl-3e_i-p08.png', 8, (72.4, 657.7, 539.0, 687.7)),
    ('ctl-3e_ii-p08.png', 8, (72.4, 731.08, 539.0, 761.08)),
    ('ctl-3e_iii-p09.png', 9, (92.4, 118.17, 541.2, 148.17)),
    # context strips to identify the straddling line
    ('ctx-3ei-p08.png', 8, (72.4, 630.0, 539.0, 700.0)),
    ('ctx-3eiii-p09.png', 9, (92.4, 100.0, 541.2, 170.0)),
    ('ctx-3eii-end-p08.png', 8, (72.4, 720.0, 539.0, 775.0)),
]
os.makedirs(PROBE, exist_ok=True)
for name, pg, clip in jobs:
    page = doc[pg - 1]
    pix = page.get_pixmap(matrix=pymupdf.Matrix(Z, Z), clip=pymupdf.Rect(*clip), alpha=False)
    pix.save(os.path.join(PROBE, name))
    print(name, pix.width, pix.height)
