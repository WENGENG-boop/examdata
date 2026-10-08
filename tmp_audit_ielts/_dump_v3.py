# -*- coding: utf-8 -*-
"""临时: 逐页 dump 答案页词坐标（写 v3 前校准用）"""
import sys
import pymupdf

BASE = 'C:/Users/weo/Desktop/api/tmp_audit_ielts'


def rows_of(page, tol=3.0):
    words = [(w[0], w[1], w[2], w[3], w[4]) for w in page.get_text('words')]
    ws = sorted(words, key=lambda w: (w[1], w[0]))
    rows = []
    for w in ws:
        if rows and w[1] - rows[-1][0][1] <= tol:
            rows[-1].append(w)
        else:
            rows.append([w])
    return rows


for book, pages in [(4, [153, 155, 157, 159]), (3, [153, 155, 157, 159])]:
    doc = pymupdf.open(f'{BASE}/downloads/book_{book}.pdf')
    for pno in pages:
        page = doc[pno - 1]
        print(f'#### book{book} p{pno} W={page.rect.width}')
        for r in rows_of(page):
            parts = []
            for x0, y0, x1, y1, t in sorted(r, key=lambda w: w[0]):
                parts.append(f'{x0:.1f}-{x1:.1f}:{t}')
            print(f'{r[0][1]:.1f} | ' + '  '.join(parts))
    doc.close()
