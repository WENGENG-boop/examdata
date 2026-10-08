#!/usr/bin/env python
"""Segment a PDF column strip into glyph bands and print each band as compact ASCII.

Usage: read_vals.py <book> <page> <x0> <y0> <x1> <y1> [dpi] [step]
Prints: label "y0pt..y1pt wpx" then ASCII rows for each ink band (gaps < 6px merged).
"""
import sys

import pymupdf

DOWNLOADS = "C:/Users/weo/Desktop/api/tmp_audit_ielts/downloads"


def main():
    book, page = sys.argv[1], int(sys.argv[2])
    x0, y0, x1, y1 = [float(v) for v in sys.argv[3:7]]
    dpi = float(sys.argv[7]) if len(sys.argv) > 7 else 600.0
    step = int(sys.argv[8]) if len(sys.argv) > 8 else 3
    doc = pymupdf.open(f"{DOWNLOADS}/book_{book}.pdf")
    pg = doc[page - 1]
    clip = pymupdf.Rect(x0, y0, x1, y1)
    pix = pg.get_pixmap(matrix=pymupdf.Matrix(dpi / 72.0, dpi / 72.0),
                        clip=clip, alpha=False, colorspace=pymupdf.csGRAY)
    w, h, n, stride = pix.width, pix.height, pix.n, pix.stride
    s = pix.samples
    scale = dpi / 72.0
    rows = []
    for yy in range(h):
        base = yy * stride
        cnt = sum(1 for xx in range(w) if s[base + xx * n] < 128)
        rows.append(cnt)
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
                if gap >= 6:
                    bands.append(cur)
                    cur = None
    if cur is not None:
        bands.append(cur)
    for b0, b1 in bands:
        print(f"--- band y={y0 + b0 / scale:.1f}..{y0 + b1 / scale:.1f} h={b1 - b0 + 1}px")
        for yy in range(b0, b1 + 1, step):
            base = yy * stride
            row = []
            for xx in range(0, w, max(1, step // 2)):
                v = s[base + xx * n]
                row.append('#' if v < 100 else ('+' if v < 170 else ('.' if v < 220 else ' ')))
            print(''.join(row).rstrip())


if __name__ == '__main__':
    main()
