#!/usr/bin/env python
"""S06 scratch: ink row profile for a page region, split into x strips.

Usage: s06_inkrows.py <book> <page> <x0> <y0> <x1> <y1> [--dpi 300] [--splits x1,x2]
Prints, for each x strip, the ink rows (runs of dark rows) in PDF pt coordinates.
"""
import sys

import numpy as np
import pymupdf

ROOT = "C:/Users/weo/Desktop/api"
DOWNLOADS = ROOT + "/tmp_audit_ielts/downloads"


def main():
    book = sys.argv[1]
    page_no = int(sys.argv[2])
    x0, y0, x1, y1 = [float(v) for v in sys.argv[3:7]]
    dpi = 300.0
    splits = None
    args = sys.argv[7:]
    i = 0
    while i < len(args):
        if args[i] == "--dpi":
            dpi = float(args[i + 1]); i += 2
        elif args[i] == "--splits":
            splits = [float(v) for v in args[i + 1].split(",")]; i += 2
        else:
            i += 1
    doc = pymupdf.open(f"{DOWNLOADS}/book_{book}.pdf")
    page = doc[page_no - 1]
    scale = dpi / 72.0
    rect = pymupdf.Rect(x0, y0, x1, y1)
    pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), clip=rect, alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        img = img[:, :, :3]
    gray = img.mean(axis=2)
    dark = gray < 160

    xbounds = [x0] + (splits or []) + [x1]
    for si in range(len(xbounds) - 1):
        sx0, sx1 = xbounds[si], xbounds[si + 1]
        c0 = int((sx0 - x0) * scale)
        c1 = int((sx1 - x0) * scale)
        strip = dark[:, c0:c1]
        rows = strip.sum(axis=1)
        thr = max(1, int(0.005 * (c1 - c0)))
        print(f"--- strip x={sx0}-{sx1} (thr={thr}) ---")
        run = None
        for r in range(len(rows)):
            on = rows[r] >= thr
            if on and run is None:
                run = r
            elif not on and run is not None:
                ytop = y0 + run / scale
                ybot = y0 + r / scale
                print(f"   band y={ytop:7.2f}-{ybot:7.2f} h={ybot - ytop:5.2f}")
                run = None
        if run is not None:
            print(f"   band y={y0 + run / scale:7.2f}-{y1:7.2f}")
    doc.close()


if __name__ == "__main__":
    main()
