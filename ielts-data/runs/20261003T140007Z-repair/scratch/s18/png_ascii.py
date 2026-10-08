import sys, glob, os
import pymupdf as fitz

OUT = r"C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/scratch/s18/glyphs_render"

def ascii_of(png, maxw=44, maxh=30):
    pix = fitz.Pixmap(png)
    w, h = pix.width, pix.height
    samples = pix.samples
    n = pix.n
    # find ink bbox (dark pixels)
    minx, miny, maxx, maxy = w, h, -1, -1
    for y in range(h):
        row = samples[y*w*n:(y+1)*w*n]
        for x in range(w):
            v = row[x*n]
            if v < 200:
                if x < minx: minx = x
                if x > maxx: maxx = x
                if y < miny: miny = y
                if y > maxy: maxy = y
    if maxx < 0:
        return "(blank)"
    cw = maxx - minx + 1
    ch = maxy - miny + 1
    sx = max(1, cw // maxw)
    sy = max(1, ch // maxh)
    lines = []
    for y in range(miny, maxy+1, sy):
        line = []
        for x in range(minx, maxx+1, sx):
            block = 0; cnt = 0
            for yy in range(y, min(y+sy, h)):
                row = samples[yy*w*n:(yy+1)*w*n]
                for xx in range(x, min(x+sx, w)):
                    block += row[xx*n]; cnt += 1
            avg = block / max(1, cnt)
            line.append('#' if avg < 100 else ('+' if avg < 180 else ' '))
        lines.append(''.join(line))
    return '\n'.join(lines)

files = sorted(glob.glob(OUT + "/*.png"))
for fn in files:
    base = os.path.basename(fn)
    print("=====", base)
    print(ascii_of(fn))
