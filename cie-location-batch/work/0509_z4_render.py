# -*- coding: utf-8 -*-
"""0509 part1 (venv): render ms pages 8,12,13,15 at z=4 unrotated."""
import pymupdf

BASE = r"C:/Users/weo/Desktop/api/cie-location-batch"
TMP = BASE + "/tmp/0509/2026-Jun-11"
PROBE = TMP + "/probe"
MS = TMP + "/0509_s26_ms_11.pdf"

doc = pymupdf.open(MS)
for pno in (8, 12, 13, 15):
    page = doc[pno - 1]
    pix = page.get_pixmap(matrix=pymupdf.Matrix(4, 4))
    out = f"{PROBE}/ms-{pno:02d}-z4.png"
    pix.save(out)
    print("saved", out, pix.width, pix.height)
