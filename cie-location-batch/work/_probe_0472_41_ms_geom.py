# -*- coding: utf-8 -*-
"""Dump MS pages 7-14 text lines in display coords for 0472/2026/Jun/41.

Display mapping for rot=90 (mediabox 612x792): dispX = 792 - y_unrot, dispY = x_unrot.
Text extraction coords are expected in unrotated space; sanity check prints max extents.
"""
import pymupdf

MS = r'C:/Users/weo/Desktop/api/cie-location-batch/tmp/0472/2026-Jun-41/0472_s26_ms_41.pdf'
doc = pymupdf.open(MS)
print(f'pages={len(doc)}')
for i in range(6, len(doc)):
    page = doc[i]
    print(f'===== MS p{i+1} rot={page.rotation} rect=({page.rect.width:.0f}x{page.rect.height:.0f}) mb=({page.mediabox.width:.0f}x{page.mediabox.height:.0f})')
    d = page.get_text('dict')
    lines = []
    maxx = maxy = 0.0
    for b in d['blocks']:
        if b.get('type') != 0:
            continue
        for ln in b['lines']:
            text = ''.join(s['text'] for s in ln['spans']).strip()
            if not text:
                continue
            x0, y0, x1, y1 = ln['bbox']
            maxx = max(maxx, x1)
            maxy = max(maxy, y1)
            dY0, dY1 = x0, x1          # display Y range = unrot x
            dX0, dX1 = 792 - y1, 792 - y0  # display X range = 792 - unrot y
            lines.append((dY0, dY1, dX0, dX1, text[:110]))
    print(f'  sanity: max_x1={maxx:.1f} max_y1={maxy:.1f} (unrot<=612x792, rot<=792x612)')
    lines.sort(key=lambda t: (round(t[0], 1), t[2]))
    for dY0, dY1, dX0, dX1, t in lines:
        print(f'  dY=[{dY0:6.1f},{dY1:6.1f}] dX=[{dX0:6.1f},{dX1:6.1f}] {t}')
    dr = page.get_drawings()
    if dr:
        X0 = Y0 = 1e9
        X1 = Y1 = -1e9
        for p in dr:
            r = p['rect']
            for (ux, uy) in ((r.x0, r.y0), (r.x1, r.y0), (r.x0, r.y1), (r.x1, r.y1)):
                X, Y = 792 - uy, ux
                X0 = min(X0, X); X1 = max(X1, X)
                Y0 = min(Y0, Y); Y1 = max(Y1, Y)
        print(f'  drawings={len(dr)} disp_bbox=[{X0:.1f},{Y0:.1f},{X1:.1f},{Y1:.1f}]')
doc.close()
