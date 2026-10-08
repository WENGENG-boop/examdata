# -*- coding: utf-8 -*-
"""0509 probe 2: measure red boxes in rot images + ink band profiles.

Reading space (x', y') = (842 - y, x) for unrotated PDF point (x, y).
rot image px = (x' * z, y' * z), z = 2.
"""
import sys
from PIL import Image, ImageChops

BASE = r"C:/Users/weo/Desktop/api/cie-location-batch"
PROBE = BASE + "/tmp/0509/2026-Jun-11/probe"
Z = 2.0
PW, PH = 842.0, 595.22  # reading-space page size in points

def red_mask(im):
    r, g, b = im.split()[:3]
    mr = r.point(lambda v: 255 if v > 170 else 0).convert("1")
    mg = g.point(lambda v: 255 if v < 110 else 0).convert("1")
    mb = b.point(lambda v: 255 if v < 110 else 0).convert("1")
    return ImageChops.logical_and(ImageChops.logical_and(mr, mg), mb)

def dark_mask(im):
    r, g, b = im.split()[:3]
    mr = r.point(lambda v: 255 if v < 190 else 0).convert("1")
    mg = g.point(lambda v: 255 if v < 190 else 0).convert("1")
    mb = b.point(lambda v: 255 if v < 190 else 0).convert("1")
    return ImageChops.logical_and(ImageChops.logical_and(mr, mg), mb)

def report_box(name, im):
    m = red_mask(im)
    bb = m.getbbox()
    print(f"[{name}] size={im.size} red_px={bb}")
    if bb:
        x0, y0, x1, y1 = bb
        # px -> reading pts
        rx0, ry0, rx1, ry1 = x0 / Z, y0 / Z, x1 / Z, y1 / Z
        print(f"  reading pts: x' [{rx0:.2f},{rx1:.2f}] y' [{ry0:.2f},{ry1:.2f}]")
        # reading -> unrotated: x = y', y = 842 - x'
        ux0, uy0, ux1, uy1 = ry0, 842 - rx1, ry1, 842 - rx0
        print(f"  unrotated bbox: [{ux0:.2f},{uy0:.2f},{ux1:.2f},{uy1:.2f}]")
    return bb

def row_profile(name, im, x0pt, x1pt, ylim=(0, 595)):
    """dark fraction per reading row y' in [x0pt,x1pt]."""
    dm = dark_mask(im)
    px0, px1 = int(x0pt * Z), int(x1pt * Z)
    px0 = max(0, px0); px1 = min(im.size[0], px1)
    y0, y1 = int(ylim[0] * Z), int(ylim[1] * Z)
    crop = dm.crop((px0, y0, px1, y1))
    h = crop.size[1]
    strip = crop.convert("L").resize((1, h), Image.BOX)
    vals = list(strip.getdata())
    print(f"[{name}] row profile y' in [{ylim[0]},{ylim[1]}], x' in [{x0pt},{x1pt}] (thr 0.004)")
    bands = []
    cur = None
    for i, v in enumerate(vals):
        frac = v / 255.0
        ypt = ylim[0] + i / Z
        if frac > 0.004:
            if cur is None:
                cur = [ypt, ypt, frac]
            else:
                cur[1] = ypt
                cur[2] = max(cur[2], frac)
        else:
            if cur is not None:
                bands.append(cur)
                cur = None
    if cur is not None:
        bands.append(cur)
    for b in bands:
        print(f"   band y' [{b[0]:.2f},{b[1]:.2f}] maxfrac {b[2]:.3f}")

def col_profile(name, im, y0pt, y1pt, xlim=(0, 842)):
    dm = dark_mask(im)
    py0, py1 = int(y0pt * Z), int(y1pt * Z)
    x0, x1 = int(xlim[0] * Z), int(xlim[1] * Z)
    crop = dm.crop((x0, py0, x1, py1))
    w = crop.size[0]
    strip = crop.convert("L").resize((w, 1), Image.BOX)
    vals = list(strip.getdata())
    print(f"[{name}] col profile x' in [{xlim[0]},{xlim[1]}], y' in [{y0pt},{y1pt}] (thr 0.004)")
    bands = []
    cur = None
    for i, v in enumerate(vals):
        frac = v / 255.0
        xpt = xlim[0] + i / Z
        if frac > 0.004:
            if cur is None:
                cur = [xpt, xpt, frac]
            else:
                cur[1] = xpt
                cur[2] = max(cur[2], frac)
        else:
            if cur is not None:
                bands.append(cur)
                cur = None
    if cur is not None:
        bands.append(cur)
    for b in bands:
        print(f"   band x' [{b[0]:.2f},{b[1]:.2f}] maxfrac {b[2]:.3f}")

for pno in (8, 12, 14, 15):
    p = f"{PROBE}/ms-{pno:02d}-z2-rot.png"
    try:
        im = Image.open(p).convert("RGB")
    except FileNotFoundError:
        print(f"missing {p}")
        continue
    bb = report_box(f"ms-{pno}", im)
    if pno == 8:
        row_profile("ms-08 rows", im, 130, 784, (0, 320))
        row_profile("ms-08 rows mid", im, 130, 784, (300, 595))
    if pno == 12:
        col_profile("ms-12 cols", im, 200, 466, (0, 842))
        row_profile("ms-12 rows", im, 62, 784, (60, 200))
    if pno == 15:
        row_profile("ms-15 rows", im, 130, 784, (0, 320))
    if pno == 14:
        row_profile("ms-14 rows", im, 130, 784, (300, 595))
