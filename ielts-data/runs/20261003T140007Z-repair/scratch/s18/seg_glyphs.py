#!/usr/bin/env python
"""Segment a PDF region into row-bands, then per-glyph column segments, print each glyph as ASCII.

Usage: seg_glyphs.py <book> <page> <x0> <y0> <x1> <y1> [dpi] [colstep] [mincolsep]
Each glyph printed with its x-range in pt. Row bands merged on gaps < 5px; glyphs split on >=mincolsep blank columns.
"""
import sys

import pymupdf

DOWNLOADS = "C:/Users/weo/Desktop/api/tmp_audit_ielts/downloads"


def main():
    book, page = sys.argv[1], int(sys.argv[2])
    x0, y0, x1, y1 = [float(v) for v in sys.argv[3:7]]
    dpi = float(sys.argv[7]) if len(sys.argv) > 7 else 900.0
    colstep = int(sys.argv[8]) if len(sys.argv) > 8 else 2
    minsep = int(sys.argv[9]) if len(sys.argv) > 9 else 3
    doc = pymupdf.open(f"{DOWNLOADS}/book_{book}.pdf")
    pg = doc[page - 1]
    clip = pymupdf.Rect(x0, y0, x1, y1)
    pix = pg.get_pixmap(matrix=pymupdf.Matrix(dpi / 72.0, dpi / 72.0),
                        clip=clip, alpha=False, colorspace=pymupdf.csGRAY)
    w, h, n, stride = pix.width, pix.height, pix.n, pix.stride
    s = pix.samples
    scale = dpi / 72.0

    def dark(xx, yy):
        return s[yy * stride + xx * n] < 128

    rows = [sum(1 for xx in range(w) if dark(xx, yy)) for yy in range(h)]
    bands = []
    cur = None
    gap = 0
    for yy, c in enumerate(rows):
        if c > 0:
            if cur is None:
                cur = [yy, yy]
            else:
                cur[1] = yy
            gap = 0
        else:
            if cur is not None:
                gap += 1
                if gap >= 5:
                    bands.append(cur)
                    cur = None
    if cur is not None:
        bands.append(cur)

    for b in bands:
        by0, by1 = b
        cols = []
        for xx in range(w):
            cnt = sum(1 for yy in range(by0, by1 + 1) if dark(xx, yy))
            cols.append(cnt)
        segs = []
        c = None
        gap = 0
        for xx, cnt in enumerate(cols):
            if cnt > 0:
                if c is None:
                    c = [xx, xx]
                else:
                    c[1] = xx
                gap = 0
            else:
                if c is not None:
                    gap += 1
                    if gap >= minsep:
                        segs.append(c)
                        c = None
        if c is not None:
            segs.append(c)
        y0pt = y0 + by0 / scale
        y1pt = y0 + by1 / scale
        print(f"=== band y={y0pt:.1f}-{y1pt:.1f}pt  ({len(segs)} glyphs)")
        for g in segs:
            gx0, gx1 = g
            x0pt = x0 + gx0 / scale
            x1pt = x0 + gx1 / scale
            print(f"--- glyph x={x0pt:.1f}-{x1pt:.1f}pt")
            for yy in range(by0, by1 + 1, 2):
                row = []
                for xx in range(gx0, gx1 + 1, colstep):
                    row.append('#' if dark(xx, yy) else ' ')
                print(''.join(row).rstrip())


if __name__ == "__main__":
    main()
