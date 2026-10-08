# -*- coding: utf-8 -*-
"""0509 MS edge check: magnify the fixed edges of v-ms-p08-r01, v-ms-p12-r01,
v-ms-p13-r01 (rotated to reading orientation) + numeric ink distance to edge.

MS reading-space mapping: (x', y') = (842 - y_pdf, x_pdf); content rotated.
The crops render unrotated PDF space, so rotate the extracted strip 90 CW to
read normally: reading x' increases left->right, reading y' increases top->bottom.
"""
import sys
from pathlib import Path

from PIL import Image

CROPS = Path(r"C:/Users/weo/Desktop/api/cie-location-batch/tmp/0509/2026-Jun-11/crops")
OUT = Path(r"C:/Users/weo/Desktop/api/cie-location-batch/tmp/0509/2026-Jun-11/probe")

# (name, side, bbox used for render: x0,y0,x1,y1)
CASES = [
    ("v-ms-p08-r01", "left", (62.0, 57.08, 540.0, 780.0)),
    ("v-ms-p12-r01", "bottom", (100.0, 57.08, 466.2, 780.75)),
    ("v-ms-p13-r01", "bottom", (49.5, 57.08, 192.3, 780.75)),
]

STRIP_PX = 140
UP = 2
DARK = 200


def min_ink_distance(img, side):
    """Return (min distance in px from the fixed edge, list of closest rows/cols)."""
    g = img.convert("L")
    w, h = g.size
    px = g.load()
    best = None
    closest = []
    if side == "left":
        for y in range(h):
            for x in range(0, min(w, 60)):
                if px[x, y] < DARK:
                    d = x
                    if best is None or d < best:
                        best = d
                        closest = [(y, d)]
                    elif d == best:
                        closest.append((y, d))
                    break
    else:  # bottom
        for x in range(w):
            for y in range(h - 1, max(-1, h - 60), -1):
                if px[x, y] < DARK:
                    d = h - 1 - y
                    if best is None or d < best:
                        best = d
                        closest = [(x, d)]
                    elif d == best:
                        closest.append((x, d))
                    break
    return best, closest[:20]


def main():
    for name, side, bbox in CASES:
        path = CROPS / f"{name}.png"
        img = Image.open(path)
        w, h = img.size
        x0, y0, x1, y1 = bbox
        sx, sy = w / (x1 - x0), h / (y1 - y0)
        print(f"{name}: {w}x{h} scale=({sx:.4f},{sy:.4f})")
        dist_px, closest = min_ink_distance(img, side)
        if side == "left":
            dist_pt = dist_px / sx
            print(f"  closest ink to LEFT edge: {dist_px}px = {dist_pt:.2f}pt"
                  f" (reading y'={x0}+{dist_pt:.2f})")
            print(f"  closest rows (y_px, x_px): {closest}")
            strip = img.crop((0, 0, STRIP_PX, h))
        else:
            dist_pt = dist_px / sy
            print(f"  closest ink to BOTTOM edge: {dist_px}px = {dist_pt:.2f}pt"
                  f" (reading x'={842 - (y1)}.. edge; ink at x'={842 - y1 + dist_pt:.2f})")
            print(f"  closest cols (x_px, y_px): {closest}")
            strip = img.crop((0, h - STRIP_PX, w, h))
        strip = strip.resize((strip.width * UP, strip.height * UP), Image.LANCZOS)
        rot = strip.transpose(Image.ROTATE_270)  # 90 deg clockwise
        print(f"  strip {strip.size} -> rotated {rot.size}")
        rw, rh = rot.size
        n_chunks = max(1, (rw + 1180) // 1190)
        step = (rw + n_chunks - 1) // n_chunks
        for i in range(n_chunks):
            chunk = rot.crop((i * step, 0, min(rw, (i + 1) * step), rh))
            outp = OUT / f"msedge-{name.split('-')[2]}-{side}-{i + 1}.png"
            chunk.save(outp)
            print(f"  saved {outp} {chunk.size}")


if __name__ == "__main__":
    sys.exit(main())
