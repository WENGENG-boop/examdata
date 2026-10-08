#!/usr/bin/env python
"""Render each rawdict char's own bbox as ASCII to decode glyph->digit mapping.
Usage: char_probe.py <book> <page> <x0> <y0> <x1> <y1>   (region in PDF points, selects chars by bbox center)
"""
import sys
import pymupdf

DOWNLOADS = "C:/Users/weo/Desktop/api/tmp_audit_ielts/downloads"

def ascii_pix(pix, step=2):
    samples = pix.samples
    n = pix.n
    out = []
    for yy in range(0, pix.height, step):
        base = yy * pix.stride
        row = []
        for xx in range(0, pix.width, step):
            v = samples[base + xx * n]
            row.append('#' if v < 100 else ('+' if v < 170 else ('.' if v < 220 else ' ')))
        out.append(''.join(row).rstrip())
    return out

def main():
    book, page = sys.argv[1], int(sys.argv[2])
    x0, y0, x1, y1 = [float(v) for v in sys.argv[3:7]]
    doc = pymupdf.open(f"{DOWNLOADS}/book_{book}.pdf")
    pg = doc[page - 1]
    d = pg.get_text("rawdict")
    chars = []
    for blk in d["blocks"]:
        if blk["type"] != 0: continue
        for ln in blk["lines"]:
            for sp in ln["spans"]:
                for ch in sp["chars"]:
                    bx0, by0, bx1, by1 = ch["bbox"]
                    cx, cy = (bx0+bx1)/2, (by0+by1)/2
                    if x0 <= cx <= x1 and y0 <= cy <= y1:
                        chars.append((by0, bx0, bx1, by1, ch["c"], sp["font"], round(sp["size"],1)))
    chars.sort()
    for (by0, bx0, bx1, by1, c, font, size) in chars:
        r = pymupdf.Rect(bx0-0.5, by0-0.5, bx1+0.5, by1+0.5)
        pix = pg.get_pixmap(matrix=pymupdf.Matrix(600/72, 600/72), clip=r, alpha=False, colorspace=pymupdf.csGRAY)
        print(f"=== char {c!r} font={font} size={size} bbox=({bx0:.2f},{by0:.2f},{bx1:.2f},{by1:.2f}) h={by1-by0:.2f}")
        for row in ascii_pix(pix, 2):
            if row: print('   ' + row)
        print()

if __name__ == "__main__":
    main()
