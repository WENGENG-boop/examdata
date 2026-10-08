# -*- coding: utf-8 -*-
"""0509: analyze ink at the edges of the exact worker crops.

For each crop PNG: convert edge ink pixels to reading-space (x',y') coords.
crop was rendered: clip=[x0-pad, y0-pad, x1+pad, y1+pad], pad=0.4, zoom 1.65 (unrotated).
image px -> unrotated pt: ux = (x0-pad) + px/1.65 ; uy = (y0-pad) + py/1.65
reading: x' = 842 - uy ; y' = ux
"""
from PIL import Image

BASE = r"C:/Users/weo/Desktop/api/cie-location-batch"
CROPS = BASE + "/tmp/0509/2026-Jun-11/crops"
Z = 1.65
PAD = 0.4

CASES = {
    "v-ms-p08-r01.png": [60.0, 57.08, 540.0, 780.0],
    "v-ms-p12-r01.png": [100.0, 57.08, 466.2, 665.76],
    "v-ms-p13-r01.png": [49.5, 57.08, 192.3, 660.0],
    "v-ms-p15-r01.png": [74.26, 57.08, 200.62, 779.7],
}

def dark(px):
    r, g, b = px[:3]
    return r < 190 and g < 190 and b < 190

for fname, bb in CASES.items():
    x0, y0, x1, y1 = bb
    im = Image.open(f"{CROPS}/{fname}").convert("RGB")
    w, h = im.size
    px = im.load()
    print(f"=== {fname} size={w}x{h} bbox={bb}")
    edges = {
        "left(img x=0..2, reading y'=x0 side)": [(x, y) for x in range(0, 3) for y in range(h)],
        "right(img x=w-3..w-1, reading y'=x1 side)": [(x, y) for x in range(w - 3, w) for y in range(h)],
        "top(img y=0..2, reading x'=842-y0 side)": [(x, y) for y in range(0, 3) for x in range(w)],
        "bottom(img y=h-3..h-1, reading x'=842-y1 side)": [(x, y) for y in range(h - 3, h) for x in range(w)],
    }
    for ename, pixels in edges.items():
        hits = [(x, y) for (x, y) in pixels if dark(px[x, y])]
        if not hits:
            print(f"  {ename}: clean")
            continue
        # group by reading coordinate along the edge
        coords = []
        for (x, y) in hits:
            ux = (x0 - PAD) + x / Z
            uy = (y0 - PAD) + y / Z
            coords.append((842 - uy, ux))
        xs = sorted(c[0] for c in coords)
        ys = sorted(c[1] for c in coords)
        print(f"  {ename}: {len(hits)} ink px, reading x' [{xs[0]:.1f},{xs[-1]:.1f}] y' [{ys[0]:.1f},{ys[-1]:.1f}]")
        # histogram of y' runs (reading): group consecutive
        runs = []
        cur = [ys[0], ys[0]]
        for v in ys[1:]:
            if v - cur[1] <= 1.0:
                cur[1] = v
            else:
                runs.append(cur); cur = [v, v]
        runs.append(cur)
        print(f"     y' runs: " + ", ".join(f"[{a:.1f},{b:.1f}]" for a, b in runs[:20]))
