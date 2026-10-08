# -*- coding: utf-8 -*-
"""0509: draw CORRECT region boxes on rotated renders.

rect px = ((842-y1)*z, x0*z, (842-y0)*z, x1*z)
"""
from PIL import Image, ImageDraw

BASE = r"C:/Users/weo/Desktop/api/cie-location-batch"
PROBE = BASE + "/tmp/0509/2026-Jun-11/probe"
Z = 2

BOXES = {
    "ms-08": ([60.0, 57.08, 540.0, 780.0], (255, 0, 0)),
    "ms-12": ([100.0, 57.08, 466.2, 665.76], (255, 0, 0)),
    "ms-15": ([74.26, 57.08, 200.62, 779.7], (255, 0, 0)),
}

for name, (bb, color) in BOXES.items():
    src = f"{PROBE}/{name}-z2.png"
    im = Image.open(src).convert("RGB")
    im = im.transpose(Image.Transpose.ROTATE_270)  # clockwise 90
    dr = ImageDraw.Draw(im)
    x0, y0, x1, y1 = bb
    r = ((842 - y1) * Z, x0 * Z, (842 - y0) * Z, x1 * Z)
    dr.rectangle(r, outline=color, width=3)
    out = f"{PROBE}/{name}-box.png"
    im.save(out)
    print("saved", out, "rect", [round(v, 1) for v in r], "imgsize", im.size)
