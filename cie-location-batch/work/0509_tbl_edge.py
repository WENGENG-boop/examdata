# -*- coding: utf-8 -*-
"""0509: precise left-edge measurement of the Writing tables on MS p12/p13.

Conventions identical to 0509_strips_measure.py:
  probe/ms-XX-z4.png = unrotated page render at z=4 (no clip)
  reading space = image.transpose(ROTATE_270)
  reading coords (x',y') printed as-is; map back: unrotated x = y', unrotated y = 842 - x'
"""
from PIL import Image, ImageChops

BASE = r"C:/Users/weo/Desktop/api/cie-location-batch"
PROBE = BASE + "/tmp/0509/2026-Jun-11/probe"
Z = 4


def rot_img(pno):
    im = Image.open(f"{PROBE}/ms-{pno:02d}-z4.png").convert("RGB")
    return im.transpose(Image.Transpose.ROTATE_270)


def dark_mask(im):
    r, g, b = im.split()[:3]
    mr = r.point(lambda v: 255 if v < 190 else 0).convert("1")
    mg = g.point(lambda v: 255 if v < 190 else 0).convert("1")
    mb = b.point(lambda v: 255 if v < 190 else 0).convert("1")
    return ImageChops.logical_and(ImageChops.logical_and(mr, mg), mb)


def cols_of(name, dm, x0pt, x1pt, y0pt, y1pt, thr=0.004):
    c = dm.crop((int(x0pt * Z), int(y0pt * Z), int(x1pt * Z), int(y1pt * Z)))
    w = c.size[0]
    vals = list(c.convert("L").resize((w, 1), Image.BOX).get_flattened_data())
    print(f"[{name}] cols y'[{y0pt},{y1pt}] x'[{x0pt},{x1pt}] thr={thr}")
    bands, cur = [], None
    for i, v in enumerate(vals):
        frac = v / 255.0
        xpt = x0pt + i / Z
        if frac > thr:
            cur = [xpt, xpt, frac] if cur is None else [cur[0], xpt, max(cur[2], frac)]
        elif cur is not None:
            bands.append(cur); cur = None
    if cur:
        bands.append(cur)
    for b in bands:
        print(f"   x' [{b[0]:.2f},{b[1]:.2f}] f={b[2]:.3f}")


def rows_of(name, dm, x0pt, x1pt, y0pt, y1pt, thr=0.004):
    c = dm.crop((int(x0pt * Z), int(y0pt * Z), int(x1pt * Z), int(y1pt * Z)))
    h = c.size[1]
    vals = list(c.convert("L").resize((1, h), Image.BOX).get_flattened_data())
    print(f"[{name}] rows x'[{x0pt},{x1pt}] y'[{y0pt},{y1pt}] thr={thr}")
    bands, cur = [], None
    for i, v in enumerate(vals):
        frac = v / 255.0
        ypt = y0pt + i / Z
        if frac > thr:
            cur = [ypt, ypt, frac] if cur is None else [cur[0], ypt, max(cur[2], frac)]
        elif cur is not None:
            bands.append(cur); cur = None
    if cur:
        bands.append(cur)
    for b in bands:
        print(f"   y' [{b[0]:.2f},{b[1]:.2f}] f={b[2]:.3f}")


print("========== p12 (Table B, Writing: 5/4/3/2 rows) ==========")
im12 = rot_img(12); dm12 = dark_mask(im12)
# continuous vertical lines anywhere in x'[30,280] across the full table height
cols_of("p12 line-scan full y'100-466", dm12, 30, 280, 100, 466, thr=0.5)
cols_of("p12 line-scan y'100-283", dm12, 30, 280, 100, 283, thr=0.5)
cols_of("p12 line-scan y'283-466", dm12, 30, 280, 283, 466, thr=0.5)
# what ink sits left of the border (x' 30..70), low threshold
cols_of("p12 left margin ink y'100-466", dm12, 30, 75, 100, 466, thr=0.02)
# vertical extent of the left border (x' band 60..66)
rows_of("p12 x'60-66", dm12, 60, 66, 30, 500, thr=0.5)

print("========== p13 (table tail: 1/0 rows) ==========")
im13 = rot_img(13); dm13 = dark_mask(im13)
cols_of("p13 line-scan y'45-195", dm13, 30, 280, 45, 195, thr=0.5)
cols_of("p13 line-scan y'60-240", dm13, 30, 300, 60, 240, thr=0.5)
cols_of("p13 left margin ink y'45-195", dm13, 30, 75, 45, 195, thr=0.02)
rows_of("p13 x'60-66", dm13, 60, 66, 30, 280, thr=0.5)

print("========== p15 reference (known-good table row) ==========")
im15 = rot_img(15); dm15 = dark_mask(im15)
cols_of("p15 line-scan y'74-200", dm15, 30, 280, 74, 200, thr=0.5)
print("done")
