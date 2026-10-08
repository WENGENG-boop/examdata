# Probe: draw index region bboxes onto rendered pages (display orientation) for 0472/2025/Jun/41.
import json, os, sys
import pymupdf

BR = 'C:/Users/weo/Desktop/api/cie-location-batch'
KEY = '0472/2025/Jun/41'
SUBJ, YS, PP = '0472', '2025-Jun-41', '41'
IDX = f'{BR}/indexes/{SUBJ}/{YS}/cie-index.json'
QP = f'{BR}/tmp/{SUBJ}/{YS}/0472_s25_qp_41.pdf'
MS = f'{BR}/tmp/{SUBJ}/{YS}/0472_s25_ms_41.pdf'
OUT = f'{BR}/tmp/{SUBJ}/{YS}/probe'
os.makedirs(OUT, exist_ok=True)

idx = json.load(open(IDX, encoding='utf-8'))

# collect regions per role/page
regions = {'qp': {}, 'ms': {}}
for q in idx['questions']:
    for role in ('qp', 'ms'):
        for r in q.get(role, []):
            regions[role].setdefault(r['page'], []).append(
                (q['question'], r['bbox']))

ZOOM = 2.0
for role, path in (('qp', QP), ('ms', MS)):
    doc = pymupdf.open(path)
    for pageno in sorted(regions[role]):
        page = doc[pageno - 1]
        pix = page.get_pixmap(matrix=pymupdf.Matrix(ZOOM, ZOOM))
        out = pymupdf.open()
        op = out.new_page(width=pix.width, height=pix.height)
        op.insert_image(op.rect, stream=pix.tobytes('png'))
        print(f'--- {role} page {pageno} (rot={page.rotation}, rect={page.rect}) ---')
        for qn, bbox in regions[role][pageno]:
            r = pymupdf.Rect(bbox)
            rd = r * page.rotation_matrix
            print(f'  Q{qn}: unrot={bbox} -> disp=({rd.x0:.1f},{rd.y0:.1f},{rd.x1:.1f},{rd.y1:.1f})')
            d = pymupdf.Rect(rd.x0 * ZOOM, rd.y0 * ZOOM, rd.x1 * ZOOM, rd.y1 * ZOOM)
            op.draw_rect(d, color=(1, 0, 0), width=3)
            op.insert_text((d.x0 + 4, d.y0 + 18), f'Q{qn}', fontsize=16, color=(1, 0, 0))
        opix = op.get_pixmap()
        opix.save(f'{OUT}/overlay-{role}-p{pageno}.png')
        out.close()
    doc.close()
print('done')
