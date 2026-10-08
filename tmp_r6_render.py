"""Render a region of a PDF page to PNG."""
import sys

import pymupdf

path = sys.argv[1]
page_no = int(sys.argv[2])
out = sys.argv[3]
y0, y1, x0, x1 = (float(v) for v in sys.argv[4:8])
zoom = float(sys.argv[8]) if len(sys.argv) > 8 else 4.0

doc = pymupdf.open(path)
page = doc[page_no]
mat = pymupdf.Matrix(zoom, zoom)
clip = pymupdf.Rect(x0, y0, x1, y1)
pix = page.get_pixmap(matrix=mat, clip=clip)
pix.save(out)
print('saved', out, pix.width, pix.height)
