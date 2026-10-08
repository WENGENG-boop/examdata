"""0478 核验辅助 2：MS 标签列（y0>640）逐页清单 + QP 标签/分值列。"""
import re
import sys
from pathlib import Path

sys.path.insert(0, 'C:/Users/weo/Desktop/api/cie-location-batch/tools')
import paperlib as P  # noqa: E402
import pymupdf  # noqa: E402

KEY = '0478/2026/Jun/11'
tmp = P.paper_tmp(KEY)
pdfs = sorted(tmp.glob('*.pdf'))
ms = [p for p in pdfs if '_ms_' in p.name][0]
qp = [p for p in pdfs if '_qp_' in p.name][0]

LABFULL = re.compile(r'^\d{1,3}\([a-z]\)$')
with pymupdf.open(ms) as doc:
    for i in range(doc.page_count):
        page = doc[i]
        words = page.get_text('words')
        lab = [w for w in words
               if (w[1] > 640 and w[4] not in ('x', 'X') and len(w[4]) < 14)
               or LABFULL.match(w[4])]
        marks = [w for w in words if w[0] > 250 and w[0] < 340 and len(w[4]) < 8]
        print(f'--- MS p{i+1} words={len(words)} labels={len(lab)}')
        print('   LBL:', ' | '.join(f'{w[4]}@x{w[0]:.0f},y{w[1]:.0f}' for w in lab))
        print('   MRK:', ' | '.join(f'{w[4]}@x{w[0]:.0f}' for w in marks[:40]))

QP_LAB = re.compile(r'^(?:\(?[a-z]\)?|\(?[ivx]+\)?|\d{1,2}\([a-z]\)|\d{1,2})$')
with pymupdf.open(qp) as doc:
    for i in range(doc.page_count):
        page = doc[i]
        words = page.get_text('words')
        lab = [w for w in words if QP_LAB.match(w[4]) and w[0] < 300 and len(w[4]) < 10]
        marks = [w for w in words if 500 < w[0] < 560 and len(w[4]) < 8]
        print(f'=== QP p{i+1} words={len(words)}')
        print('   LBL:', ' | '.join(f'{w[4]}@x{w[0]:.0f},y{w[1]:.0f}' for w in lab[:30]))
        print('   MRK:', ' | '.join(f'{w[4]}@y{w[1]:.0f}' for w in marks[:30]))
