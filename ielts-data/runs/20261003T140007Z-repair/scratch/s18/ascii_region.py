#!/usr/bin/env python
"""ASCII-render a PDF region for visual inspection. Usage: ascii_region.py <book> <page> <x0> <y0> <x1> <y1> [dpi] [pxperchar]"""
import sys
import pymupdf

DOWNLOADS = "C:/Users/weo/Desktop/api/tmp_audit_ielts/downloads"

def main():
    book, page = sys.argv[1], int(sys.argv[2])
    x0, y0, x1, y1 = [float(v) for v in sys.argv[3:7]]
    dpi = float(sys.argv[7]) if len(sys.argv) > 7 else 600.0
    ppc = float(sys.argv[8]) if len(sys.argv) > 8 else 2.0
    doc = pymupdf.open(f"{DOWNLOADS}/book_{book}.pdf")
    pg = doc[page - 1]
    pix = pg.get_pixmap(matrix=pymupdf.Matrix(dpi/72, dpi/72), clip=pymupdf.Rect(x0, y0, x1, y1), alpha=False, colorspace=pymupdf.csGRAY)
    w, h = pix.width, pix.height
    print(f"# {w}x{h}px dpi={dpi} region=({x0},{y0},{x1},{y1})")
    step = max(1, int(ppc * dpi / 72))
    samples = pix.samples
    n = pix.n
    for yy in range(0, h, step):
        row = []
        base_y = yy * pix.stride
        for xx in range(0, w, step):
            v = samples[base_y + xx * n]
            row.append('#' if v < 100 else ('+' if v < 170 else ('.' if v < 220 else ' ')))
        print(''.join(row).rstrip())

if __name__ == "__main__":
    main()
