# -*- coding: utf-8 -*-
"""render_visual_batch.py — I3 视觉核验: 官方答案页关键区域批量渲染 (诊断脚本, 不改被测代码)

用法: python render_visual_batch.py A|B
输出: evidence/i3/visual_batch{A|B}.png (每个区域带标签 + 该页图片对象数)
"""
import sys

import pymupdf

BASE = 'C:/Users/weo/Desktop/api/tmp_audit_ielts'
DOWN = BASE + '/downloads'
OUT = BASE + '/repair-20261003-152644/evidence/i3'

BATCHES = {
    'A': [
        (4, 157, (50, 153, 110, 177), 'b4 p157 Q1 (1112 years?)'),
        (5, 153, (50, 214, 105, 236), 'b5 p153 Q4 (Pallisades?)'),
        (5, 155, (55, 224, 120, 245), 'b5 p155 Q9 (Grantingham?)'),
        (5, 159, (50, 155, 115, 180), 'b5 p159 Q3 (I year?)'),
        (5, 159, (48, 222, 90, 245), 'b5 p159 Q9 (lOO?)'),
        (5, 159, (50, 364, 205, 388), 'b5 p159 Q19 (newsletter?)'),
    ],
    'B': [
        (6, 152, (55, 238, 85, 262), 'b6 p152 Q6 (I?)'),
        (6, 152, (55, 248, 150, 272), 'b6 p152 Q7 (4.30/10?)'),
        (6, 158, (255, 335, 320, 360), 'b6 p158 Q35 (,450?)'),
        (7, 161, (50, 205, 90, 230), 'b7 p161 Q7 (8659/B659?)'),
        (7, 163, (42, 148, 90, 172), 'b7 p163 Q2 (106337/JO6337?)'),
    ],
}

ZOOM = 5.0


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else 'A'
    items = BATCHES[which]
    rows = []
    for b, p, rect, label in items:
        d = pymupdf.open(f'{DOWN}/book_{b}.pdf')
        pg = d[p - 1]
        nimg = len(pg.get_images(full=True))
        pix = pg.get_pixmap(matrix=pymupdf.Matrix(ZOOM, ZOOM), clip=pymupdf.Rect(*rect))
        rows.append((label, pix, nimg))
        d.close()
    w = max(pix.width for _, pix, _ in rows) + 20
    h = 10 + sum(24 + pix.height + 12 for _, pix, _ in rows)
    out = pymupdf.open()
    page = out.new_page(width=w, height=h)
    y = 10
    for label, pix, nimg in rows:
        page.insert_text((10, y + 14), f'{label}  [page images={nimg}]', fontsize=13, fontname='helv')
        page.insert_image(pymupdf.Rect(10, y + 24, 10 + pix.width, y + 24 + pix.height),
                          stream=pix.tobytes('png'))
        y += 24 + pix.height + 12
    pix = page.get_pixmap(matrix=pymupdf.Matrix(1, 1))
    fp = f'{OUT}/visual_batch{which}.png'
    pix.save(fp)
    print(f'saved {fp}  {pix.width}x{pix.height}px')
    out.close()


if __name__ == '__main__':
    main()
