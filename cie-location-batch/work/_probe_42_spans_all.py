# -*- coding: utf-8 -*-
"""Dump ALL spans of pages 2-4 of 0472/2025/Jun/42 QP (content area) to locate [5]/[12]/[28] marks."""
import fitz

PDF = r'C:\Users\weo\Desktop\api\cie-location-batch\tmp\0472\2025-Jun-42\0472_s25_qp_42.pdf'
doc = fitz.open(PDF)
for pno in [1, 2, 3]:
    page = doc[pno]
    print(f'===== page {pno+1}  size={page.rect} rot={page.rotation} =====')
    d = page.get_text('dict')
    rows = []
    for block in d['blocks']:
        for line in block.get('lines', []):
            for span in line['spans']:
                b = span['bbox']
                t = span['text'].replace('\n', '\\n')
                rows.append((round(b[1], 1), round(b[0], 1), round(b[3], 1), round(b[2], 1), span['size'], t))
    rows.sort()
    for y0, x0, y1, x1, sz, t in rows:
        flag = ''
        if '4' in t:
            flag = '  <<< contains-4'
        print(f'  y{y0:7.1f}-{y1:7.1f} x{x0:7.1f}-{x1:7.1f} sz{sz:4.1f} {t[:70]!r}{flag}')
print('done')
