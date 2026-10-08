# -*- coding: utf-8 -*-
"""Nail [12] position on page 3 of 0472/42: tight ruler crop + raw text + drawings probe."""
import fitz, os

PDF = r'C:\Users\weo\Desktop\api\cie-location-batch\tmp\0472\2025-Jun-42\0472_s25_qp_42.pdf'
OUT = r'C:\Users\weo\Desktop\api\cie-location-batch\work\sheets\probe42d'
os.makedirs(OUT, exist_ok=True)
doc = fitz.open(PDF)
page = doc[2]

# --- raw text search around the area ---
print('--- words with x0>500 on page 3 ---')
for w in page.get_text('words'):
    x0, y0, x1, y1, txt = w[0], w[1], w[2], w[3], w[4]
    if x0 > 500:
        print(f'  ({x0:.1f},{y0:.1f},{x1:.1f},{y1:.1f}) {txt!r}')

print('--- rawdict chars x0>500, y 500-560 ---')
d = page.get_text('rawdict')
cnt = 0
for block in d['blocks']:
    for line in block.get('lines', []):
        for span in line['spans']:
            for ch in span.get('chars', []):
                x0, y0, x1, y1 = ch['bbox']
                if x0 > 500 and 500 < y0 < 560:
                    print(f'  ({x0:.1f},{y0:.1f},{x1:.1f},{y1:.1f}) {ch["c"]!r}')
                    cnt += 1
print(f'  chars found: {cnt}')

print('--- drawings intersecting Rect(500,500,612,560) ---')
n = 0
for dr in page.get_drawings():
    r = fitz.Rect(dr['rect'])
    if r.intersects(fitz.Rect(500, 500, 612, 560)):
        n += 1
        print(f'  rect=({r.x0:.1f},{r.y0:.1f},{r.x1:.1f},{r.y1:.1f}) items={len(dr["items"])} type={dr["type"]}')
print(f'  drawings found: {n}')

print('--- xobjects/images on page 3 ---')
for img in page.get_images(full=True):
    print('  image:', img)
for xref in range(1, doc.xref_length()):
    try:
        s = doc.xref_object(xref)
        if '/Subtype /Form' in s and 'Page' not in s:
            pass
    except Exception:
        pass

# --- tight ruler crop: x 470-612, y 495-565 @8x with x+y ticks ---
import html
x0, y0, x1, y1 = 470, 495, 612, 565
scale = 8
pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=fitz.Rect(x0, y0, x1, y1))
fn = 'p3_12_zone.png'
pix.save(os.path.join(OUT, fn))
W, H = pix.width, pix.height
ov = [f'<div style="position:relative;display:inline-block;border:1px solid #999">'
      f'<img src="{fn}" style="display:block;width:{W}px;height:{H}px">']
yt = int(y0 // 10 + 1) * 10
while yt < y1:
    top = (yt - y0) * scale
    ov.append(f'<div style="position:absolute;left:0;top:{top:.1f}px;width:34px;height:0;border-top:1px solid rgba(0,120,255,.6)"></div>')
    ov.append(f'<div style="position:absolute;left:36px;top:{top-8:.1f}px;font:12px monospace;color:#06c;background:rgba(255,255,255,.8)">{yt}</div>')
    yt += 10
xt = int(x0 // 10 + 1) * 10
while xt < x1:
    left = (xt - x0) * scale
    ov.append(f'<div style="position:absolute;left:{left:.1f}px;top:0;width:0;height:34px;border-left:1px solid rgba(255,0,120,.6)"></div>')
    ov.append(f'<div style="position:absolute;left:{left+2:.1f}px;top:36px;font:12px monospace;color:#c06;background:rgba(255,255,255,.8);writing-mode:vertical-rl">{xt}</div>')
    xt += 10
ov.append('</div>')
open(os.path.join(OUT, 'view.html'), 'w', encoding='utf-8').write(
    '<!doctype html><meta charset="utf-8"><body style="margin:10px">'
    '<h3>0472/42 p3 [12] zone  x470-612 y495-565 @8x</h3>' + ''.join(ov) + '</body>')
print(f'{fn} {W}x{H}; view.html written')
