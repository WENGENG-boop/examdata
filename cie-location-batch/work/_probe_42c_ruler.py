# -*- coding: utf-8 -*-
"""Ruler-overlay renders of pages 2-4 lower halves for 0472/42 -> probe42c/view.html
Overlays: 20pt ticks, footer band line (742.75), current region bottoms, known mark boxes."""
import fitz, os, html

PDF = r'C:\Users\weo\Desktop\api\cie-location-batch\tmp\0472\2025-Jun-42\0472_s25_qp_42.pdf'
OUT = r'C:\Users\weo\Desktop\api\cie-location-batch\work\sheets\probe42c'
os.makedirs(OUT, exist_ok=True)
doc = fitz.open(PDF)

jobs = [
    # (name, page(0-based), rect, scale, markers[(y0,y1,color,label)], boxes[(x0,y0,x1,y1,color,label)])
    ('p2_lower', 1, (55, 460, 575, 792), 3,
     [(742.75, 744.75, '#00a0ff', 'footer top 742.75'), (759.6, 760.6, '#00c000', 'Q1 bottom 759.6')],
     [(527.5, 570.5, 539.0, 581.1, '#ff0000', '[5]')]),
    ('p3_lower', 2, (55, 460, 575, 792), 3,
     [(742.75, 744.75, '#00a0ff', 'footer top 742.75'), (761.6, 762.6, '#00c000', 'Q2 bottom 761.6')],
     []),
    ('p4_lower', 3, (55, 440, 575, 792), 3,
     [(742.75, 744.75, '#00a0ff', 'footer top 742.75'), (759.6, 760.6, '#00c000', 'Q3/3b bottom 759.6')],
     [(521.7, 488.6, 539.0, 499.2, '#ff0000', '[28]b')]),
    ('p4_upper', 3, (55, 100, 575, 460), 3,
     [(291.2, 292.2, '#ff00ff', '3a/3b split 291.2')],
     [(521.7, 219.6, 539.0, 230.2, '#ff0000', '[28]a')]),
]

def esc(s): return html.escape(str(s))

blocks = []
for name, pno, rect, scale, marks, boxes in jobs:
    x0, y0, x1, y1 = rect
    page = doc[pno]
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=fitz.Rect(*rect))
    fn = f'{name}.png'
    pix.save(os.path.join(OUT, fn))
    W, H = pix.width, pix.height
    # overlay div
    ov = [f'<div style="position:relative;display:inline-block;border:1px solid #999">'
          f'<img src="{fn}" style="display:block;width:{W}px;height:{H}px">']
    # ticks every 20pt
    yt = int(y0 // 20 + 1) * 20
    while yt < y1:
        top = (yt - y0) * scale
        ov.append(f'<div style="position:absolute;left:0;top:{top:.1f}px;width:26px;height:0;'
                  f'border-top:1px solid rgba(120,120,120,.65)"></div>')
        ov.append(f'<div style="position:absolute;left:28px;top:{top-7:.1f}px;font:10px monospace;'
                  f'color:#555;background:rgba(255,255,255,.75)">{yt}</div>')
        yt += 20
    for (a, b, color, label) in marks:
        top = (a - y0) * scale
        ov.append(f'<div style="position:absolute;left:0;top:{top:.1f}px;width:100%;height:0;'
                  f'border-top:2px solid {color}"></div>')
        ov.append(f'<div style="position:absolute;right:4px;top:{top-12:.1f}px;font:11px monospace;'
                  f'color:{color};background:rgba(255,255,255,.85)">{esc(label)}</div>')
    for (bx0, by0, bx1, by1, color, label) in boxes:
        l = (bx0 - x0) * scale; t = (by0 - y0) * scale
        w = (bx1 - bx0) * scale; h = (by1 - by0) * scale
        ov.append(f'<div style="position:absolute;left:{l:.1f}px;top:{t:.1f}px;width:{w:.1f}px;'
                  f'height:{h:.1f}px;border:2px solid {color};box-sizing:border-box"></div>')
        ov.append(f'<div style="position:absolute;left:{l:.1f}px;top:{t-13:.1f}px;font:11px monospace;'
                  f'color:{color};background:rgba(255,255,255,.85)">{esc(label)}</div>')
    ov.append('</div>')
    blocks.append(f'<div style="margin:16px 0"><div style="font:13px monospace;background:#eee;padding:4px">'
                  f'{esc(name)}  page {pno+1}  rect=({x0},{y0},{x1},{y1}) @{scale}x  {W}x{H}px</div>'
                  + ''.join(ov) + '</div>')
    print(f'{fn} {W}x{H}')

open(os.path.join(OUT, 'view.html'), 'w', encoding='utf-8').write(
    '<!doctype html><meta charset="utf-8"><body style="margin:10px">'
    '<h3>0472/2025/Jun/42 QP lower halves with ruler (y in PDF pt)</h3>'
    + ''.join(blocks) + '</body>')
print('view.html written')
