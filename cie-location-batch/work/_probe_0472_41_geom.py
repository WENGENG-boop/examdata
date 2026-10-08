# -*- coding: utf-8 -*-
import pymupdf
QP = r'C:/Users/weo/Desktop/api/cie-location-batch/tmp/0472/2026-Jun-41/0472_s26_qp_41.pdf'
MS = r'C:/Users/weo/Desktop/api/cie-location-batch/tmp/0472/2026-Jun-41/0472_s26_ms_41.pdf'
for name, path in (('QP', QP), ('MS', MS)):
    doc = pymupdf.open(path)
    print(f'=== {name} pages={len(doc)} ===')
    for i, page in enumerate(doc):
        r = page.rect
        mb = page.mediabox
        print(f'{name} p{i+1}: rect=({r.width:.1f}x{r.height:.1f}) rot={page.rotation} mediabox=({mb.width:.1f}x{mb.height:.1f})')
