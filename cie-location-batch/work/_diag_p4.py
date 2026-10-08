# -*- coding: utf-8 -*-
import pymupdf, io

QP = r'C:/Users/weo/Desktop/api/cie-location-batch/tmp/0472/2026-Jun-41/0472_s26_qp_41.pdf'
doc = pymupdf.open(QP)

out = io.StringIO()
for pno in range(len(doc)):
    page = doc[pno]
    txt = page.get_text()
    out.write(f'=== page {pno+1} len={len(txt)} ===\n')
    if pno == 3:
        d = page.get_text('dict')
        for block in d['blocks']:
            if block['type'] != 0: continue
            for line in block['lines']:
                y0 = line['bbox'][1]; y1 = line['bbox'][3]
                if not (85 <= y0 <= 430): continue
                spans = [(s['text'], round(s['size'],1)) for s in line['spans']]
                out.write(f"y {y0:7.1f}-{y1:7.1f} x {line['bbox'][0]:7.1f}-{line['bbox'][2]:7.1f} {spans}\n")
    else:
        out.write(txt[:300].replace('\n',' | ')[:300] + '\n')
open(r'C:/Users/weo/Desktop/api/cie-location-batch/work/_p4_words.txt','w',encoding='utf-8').write(out.getvalue())

# grid render for page 4
page = doc[3]
shape = page.new_shape()
for y in range(50, 800, 50):
    shape.draw_line(pymupdf.Point(0, y), pymupdf.Point(612, y))
for x in range(50, 612, 50):
    shape.draw_line(pymupdf.Point(x, 0), pymupdf.Point(x, 792))
shape.finish(color=(0.75,0.75,0.75), width=0.4)
for y in (107.6, 278.8, 414.8):
    shape.draw_line(pymupdf.Point(0, y), pymupdf.Point(612, y))
shape.finish(color=(1,0,0), width=1.5)
shape.commit()
for y in range(100, 800, 100):
    page.insert_text((2, y-1), str(y), fontsize=7, color=(0.4,0.4,0.4))
pix = page.get_pixmap(matrix=pymupdf.Matrix(2,2))
pix.save(r'C:/Users/weo/Desktop/api/cie-location-batch/tmp/0472/2026-Jun-41/crops/_diag_p4_grid.png')
print('saved', pix.width, pix.height)
