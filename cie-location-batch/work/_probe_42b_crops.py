# -*- coding: utf-8 -*-
"""Render zoom crops for 0472/42 QP marks & footer verification -> work/sheets/probe42b/ + view.html"""
import fitz, os, html

PDF = r'C:\Users\weo\Desktop\api\cie-location-batch\tmp\0472\2025-Jun-42\0472_s25_qp_42.pdf'
OUT = r'C:\Users\weo\Desktop\api\cie-location-batch\work\sheets\probe42b'
os.makedirs(OUT, exist_ok=True)
doc = fitz.open(PDF)

jobs = [
    # (name, page_index(0based), rect, scale, label)
    ('p2_mark',   1, (440, 520, 570, 612), 6, 'P2 y520-612 x440-570 @6x  [expect [5] at y570-581 x527-539]'),
    ('p3_mark',   2, (440, 495, 570, 625), 6, 'P3 y495-625 x440-570 @6x  [find [12]?]'),
    ('p3_wide',   2, (60, 500, 575, 700), 4, 'P3 y500-700 x60-575 @4x  [empty zone below dotted lines?]'),
    ('p4_amark',  3, (440, 180, 570, 262), 6, 'P4 y180-262 x440-570 @6x  [expect [28] at y219-230]'),
    ('p4_bmark',  3, (440, 450, 570, 532), 6, 'P4 y450-532 x440-570 @6x  [expect [28] at y488-499]'),
    ('p2_footer', 1, (55, 698, 575, 792), 4, 'P2 footer y698-792 x55-575 @4x'),
    ('p3_footer', 2, (55, 698, 575, 792), 4, 'P3 footer y698-792 x55-575 @4x'),
    ('p4_footer', 3, (55, 698, 575, 792), 4, 'P4 footer y698-792 x55-575 @4x'),
]

files = []
for name, pno, rect, scale, label in jobs:
    page = doc[pno]
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=fitz.Rect(*rect))
    fn = f'{name}.png'
    pix.save(os.path.join(OUT, fn))
    files.append((fn, label, pix.width, pix.height))
    print(f'{fn}  {pix.width}x{pix.height}')

rows = '\n'.join(
    f'<div style="margin:14px 0"><div style="font:13px monospace;background:#eee;padding:4px">{html.escape(lab)}</div>'
    f'<img src="{fn}" style="display:block;max-width:1400px;border:1px solid #999"></div>'
    for fn, lab, w, h in files)
open(os.path.join(OUT, 'view.html'), 'w', encoding='utf-8').write(
    f'<!doctype html><meta charset="utf-8"><body style="margin:10px">'
    f'<h3>0472/2025/Jun/42 QP marks & footer probes</h3>{rows}</body>')
print('view.html written')
