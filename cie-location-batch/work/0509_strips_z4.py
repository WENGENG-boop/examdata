# -*- coding: utf-8 -*-
"""0509: high-zoom reading-space strips to measure cut edges.

Renders page at z=4, rotates to reading orientation, crops given reading-space
rects, and also prints dark-pixel band profiles for chosen strips.
"""
import pymupdf
from PIL import Image, ImageChops

BASE = r"C:/Users/weo/Desktop/api/cie-location-batch"
TMP = BASE + "/tmp/0509/2026-Jun-11"
PROBE = TMP + "/probe"
MS = TMP + "/0509_s26_ms_11.pdf"
Z = 4

doc = pymupdf.open(MS)

def rot_img(pno):
    page = doc[pno - 1]
    pix = page.get_pixmap(matrix=pymupdf.Matrix(Z, Z))
    im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    return im.transpose(Image.Transpose.ROTATE_270)  # reading orientation

def dark_mask(im):
    r, g, b = im.split()[:3]
    mr = r.point(lambda v: 255 if v < 190 else 0).convert("1")
    mg = g.point(lambda v: 255 if v < 190 else 0).convert("1")
    mb = b.point(lambda v: 255 if v < 190 else 0).convert("1")
    return ImageChops.logical_and(ImageChops.logical_and(mr, mg), mb)

def rows_of(name, dm, x0pt, x1pt, y0pt, y1pt, thr=0.004):
    c = dm.crop((int(x0pt * Z), int(y0pt * Z), int(x1pt * Z), int(y1pt * Z)))
    h = c.size[1]
    vals = list(c.convert("L").resize((1, h), Image.BOX).getdata())
    print(f"[{name}] rows x'[{x0pt},{x1pt}] y'[{y0pt},{y1pt}]")
    bands, cur = [], None
    for i, v in enumerate(vals):
        frac = v / 255.0
        ypt = y0pt + i / Z
        if frac > thr:
            cur = [ypt, ypt, frac] if cur is None else [cur[0], ypt, max(cur[2], frac)]
        elif cur is not None:
            bands.append(cur); cur = None
    if cur: bands.append(cur)
    for b in bands:
        print(f"   y' [{b[0]:.2f},{b[1]:.2f}] f={b[2]:.3f}")

def cols_of(name, dm, x0pt, x1pt, y0pt, y1pt, thr=0.004):
    c = dm.crop((int(x0pt * Z), int(y0pt * Z), int(x1pt * Z), int(y1pt * Z)))
    w = c.size[0]
    vals = list(c.convert("L").resize((w, 1), Image.BOX).getdata())
    print(f"[{name}] cols y'[{y0pt},{y1pt}] x'[{x0pt},{x1pt}]")
    bands, cur = [], None
    for i, v in enumerate(vals):
        frac = v / 255.0
        xpt = x0pt + i / Z
        if frac > thr:
            cur = [xpt, xpt, frac] if cur is None else [cur[0], xpt, max(cur[2], frac)]
        elif cur is not None:
            bands.append(cur); cur = None
    if cur: bands.append(cur)
    for b in bands:
        print(f"   x' [{b[0]:.2f},{b[1]:.2f}] f={b[2]:.3f}")

# p8: Section 2 heading vs crop top x0=60
im8 = rot_img(8); dm8 = dark_mask(im8)
rows_of("p8 left col", dm8, 62, 120, 35, 120)
# p8: does 'Candidates will be assessed' start below?
rows_of("p8 full-width", dm8, 62, 784, 35, 120, thr=0.002)
# crop the reading-space strip for viewing: x' 55..200, y' 30..130
im8.crop((int(55*Z), int(30*Z), int(200*Z), int(130*Z))).save(f"{PROBE}/p8-top-strip.png")

# p12: left column content between x' 62..250
im12 = rot_img(12); dm12 = dark_mask(im12)
cols_of("p12 left", dm12, 55, 260, 110, 460)
im12.crop((int(50*Z), int(100*Z), int(320*Z), int(470*Z))).save(f"{PROBE}/p12-left-strip.png")

# p13: left column content between x' 55..300
im13 = rot_img(13); dm13 = dark_mask(im13)
cols_of("p13 left", dm13, 55, 300, 60, 240)
im13.crop((int(50*Z), int(50*Z), int(320*Z), int(250*Z))).save(f"{PROBE}/p13-left-strip.png")

# p15: verify 3(f) row: what's just above y'=74.26 (x0) and below y'=200.62 (x1)?
im15 = rot_img(15); dm15 = dark_mask(im15)
rows_of("p15 3f col", dm15, 62, 784, 60, 210)
print("saved strips")
