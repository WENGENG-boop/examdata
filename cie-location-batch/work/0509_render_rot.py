# -*- coding: utf-8 -*-
"""0509: render ms pages 8,12,14,15 fresh + dir histogram for all pages."""
import pymupdf

BASE = r"C:/Users/weo/Desktop/api/cie-location-batch"
TMP = BASE + "/tmp/0509/2026-Jun-11"
PROBE = TMP + "/probe"
MS = TMP + "/0509_s26_ms_11.pdf"
QP = TMP + "/0509_s26_qp_11.pdf"

doc = pymupdf.open(MS)
print("=== MS all-page dir histogram ===")
for pno in range(doc.page_count):
    page = doc[pno]
    d = page.get_text("dict")
    hist = {}
    for b in d["blocks"]:
        if b["type"] != 0:
            continue
        for l in b["lines"]:
            key = tuple(round(x, 1) for x in l.get("dir", (1, 0)))
            hist[key] = hist.get(key, 0) + 1
    print(f"p{pno+1}: {hist}")

print("\n=== QP all-page dir histogram ===")
qd = pymupdf.open(QP)
for pno in range(qd.page_count):
    page = qd[pno]
    d = page.get_text("dict")
    hist = {}
    for b in d["blocks"]:
        if b["type"] != 0:
            continue
        for l in b["lines"]:
            key = tuple(round(x, 1) for x in l.get("dir", (1, 0)))
            hist[key] = hist.get(key, 0) + 1
    print(f"p{pno+1}: {hist}")

for pno in [7, 11, 13, 14]:
    page = doc[pno]
    pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2))
    name = f"{PROBE}/ms-{pno+1:02d}-z2.png"
    pix.save(name)
    print("saved", name, pix.width, pix.height)
