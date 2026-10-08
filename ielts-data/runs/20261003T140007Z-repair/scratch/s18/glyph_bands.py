#!/usr/bin/env python
"""Precise glyph-band analysis of the p117 answer-key value column.

Renders the value column (and number column) of book_11.pdf p117 at high DPI,
thresholds dark ink, finds per-glyph row bands, then compares bands pairwise
(bounding-box aligned IoU) to cluster identical glyphs.

Usage: glyph_bands.py <book> <page> <x0> <x1> <y0> <y1> [dpi]
"""
import sys

import pymupdf

DOWNLOADS = "C:/Users/weo/Desktop/api/tmp_audit_ielts/downloads"


def bands_for(pg, x0, x1, y0, y1, dpi):
    clip = pymupdf.Rect(x0, y0, x1, y1)
    pix = pg.get_pixmap(matrix=pymupdf.Matrix(dpi / 72.0, dpi / 72.0),
                        clip=clip, alpha=False, colorspace=pymupdf.csGRAY)
    w, h, n, stride = pix.width, pix.height, pix.n, pix.stride
    s = pix.samples
    scale = dpi / 72.0
    # dark rows profile
    rows = []
    for yy in range(h):
        base = yy * stride
        cnt = 0
        for xx in range(w):
            if s[base + xx * n] < 128:
                cnt += 1
        rows.append(cnt)
    # find bands (ink>0), merge gaps < 8px
    bands = []
    cur = None
    gap = 0
    for yy, c in enumerate(rows):
        if c > 0:
            if cur is None:
                cur = [yy, yy]
            else:
                cur[1] = yy
            gap = 0
        else:
            if cur is not None:
                gap += 1
                if gap >= 8:
                    bands.append(cur)
                    cur = None
    if cur is not None:
        bands.append(cur)
    out = []
    for b0, b1 in bands:
        # bitmap of band
        bm = []
        for yy in range(b0, b1 + 1):
            base = yy * stride
            rowbits = 0
            for xx in range(w):
                if s[base + xx * n] < 128:
                    rowbits |= (1 << xx)
            bm.append(rowbits)
        # trim empty columns -> bounding box
        minx, maxx = w, -1
        for rb in bm:
            if rb:
                lo = (rb & -rb).bit_length() - 1
                hi = rb.bit_length() - 1
                minx = min(minx, lo)
                maxx = max(maxx, hi)
        # crop rows to bounding box
        out.append({
            "y0pt": round(y0 + b0 / scale, 2),
            "y1pt": round(y0 + b1 / scale, 2),
            "hpx": b1 - b0 + 1,
            "wpx": (maxx - minx + 1) if maxx >= 0 else 0,
            "x0px": minx if maxx >= 0 else 0,
            "bm": bm, "minx": minx, "maxx": maxx, "w": w,
        })
    return out


def iou(a, b):
    """Align by bbox top-left, compute ink IoU."""
    # normalize: crop both bitmaps to their bbox, then compare with same size
    def crop(bd):
        rows = bd["bm"][:]
        minx, maxx = bd["minx"], bd["maxx"]
        # also trim empty top/bottom rows
        while rows and rows[0] == 0:
            rows.pop(0)
        while rows and rows[-1] == 0:
            rows.pop()
        out = []
        for rb in rows:
            v = (rb >> minx) & ((1 << (maxx - minx + 1)) - 1)
            out.append(v)
        return out, (maxx - minx + 1)
    ra, wa = crop(a)
    rb_, wb = crop(b)
    ha, hb = len(ra), len(rb_)
    W = max(wa, wb)
    H = max(ha, hb)
    inter = union = 0
    for yy in range(H):
        va = ra[yy] if yy < ha else 0
        vb = rb_[yy] if yy < hb else 0
        inter += bin(va & vb).count("1")
        union += bin(va | vb).count("1")
    return inter / union if union else 0.0


def main():
    book, page = int(sys.argv[1]), int(sys.argv[2])
    x0, x1, y0, y1 = [float(v) for v in sys.argv[3:7]]
    dpi = float(sys.argv[7]) if len(sys.argv) > 7 else 1200.0
    doc = pymupdf.open(f"{DOWNLOADS}/book_{book}.pdf")
    pg = doc[page - 1]
    bands = bands_for(pg, x0, x1, y0, y1, dpi)
    print(f"# {len(bands)} bands in x[{x0},{x1}] y[{y0},{y1}] dpi={dpi}")
    for i, b in enumerate(bands):
        print(f"[{i}] y {b['y0pt']}-{b['y1pt']}  h={b['hpx']}px w={b['wpx']}px")
    if len(bands) >= 2:
        print("--- IoU matrix ---")
        print("    " + " ".join(f"{j:>5d}" for j in range(len(bands))))
        for i in range(len(bands)):
            row = [f"{iou(bands[i], bands[j]):.3f}" for j in range(len(bands))]
            print(f"[{i:2d}] " + " ".join(row))
        # clusters at threshold 0.75
        import itertools
        groups = []
        assigned = {}
        for i in range(len(bands)):
            for j in range(i + 1, len(bands)):
                if iou(bands[i], bands[j]) >= 0.75:
                    gi = assigned.get(i)
                    gj = assigned.get(j)
                    if gi is None and gj is None:
                        g = len(groups)
                        groups.append([i, j])
                        assigned[i] = assigned[j] = g
                    elif gi is not None and gj is None:
                        groups[gi].append(j)
                        assigned[j] = gi
                    elif gi is None and gj is not None:
                        groups[gj].append(i)
                        assigned[i] = gj
                    elif gi != gj:
                        groups[gi].extend(groups[gj])
                        for k in groups[gj]:
                            assigned[k] = gi
                        groups[gj] = []
        print("--- clusters (IoU>=0.75) ---")
        for g in groups:
            if g:
                print(" ", sorted(set(g)))


if __name__ == "__main__":
    main()
