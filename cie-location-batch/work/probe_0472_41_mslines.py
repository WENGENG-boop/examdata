# Probe: dump MS text lines (display coords) for 0472/2025/Jun/41 pages 6-12.
import pymupdf

MS = 'C:/Users/weo/Desktop/api/cie-location-batch/tmp/0472/2025-Jun-41/0472_s25_ms_41.pdf'
doc = pymupdf.open(MS)
for pno in (6, 7, 8, 9, 10, 11, 12):
    page = doc[pno - 1]
    print(f'=== page {pno}  rot={page.rotation} rect={page.rect}')
    d = page.get_text('dict')
    lines = []
    for b in d['blocks']:
        if b['type'] != 0:
            continue
        for l in b['lines']:
            r = pymupdf.Rect(l['bbox']) * page.rotation_matrix
            text = ''.join(s['text'] for s in l['spans'])
            lines.append((r, text))
    lines.sort(key=lambda t: (round(t[0].y0, 1), t[0].x0))
    for r, text in lines:
        print(f'  disp=({r.x0:6.1f},{r.y0:6.1f},{r.x1:6.1f},{r.y1:6.1f})  {text[:90]}')
    if lines:
        x0 = min(r.x0 for r, _ in lines)
        y0 = min(r.y0 for r, _ in lines)
        x1 = max(r.x1 for r, _ in lines)
        y1 = max(r.y1 for r, _ in lines)
        print(f'  BOUNDS all-lines: x0={x0:.1f} y0={y0:.1f} x1={x1:.1f} y1={y1:.1f}')
doc.close()
