import fitz

path = r"C:/Users/weo/Desktop/api/cie-location-batch/tmp/0472/2025-Jun-42/0472_s25_qp_42.pdf"
doc = fitz.open(path)
S = 4


def ranges_of(dark):
    out = []
    start = None
    for i, d in enumerate(dark):
        if d and start is None:
            start = i
        if not d and start is not None:
            out.append((start, i - 1))
            start = None
    if start is not None:
        out.append((start, len(dark) - 1))
    return out


def rowdark(page, clip):
    pm = page.get_pixmap(clip=clip, matrix=fitz.Matrix(S, S))
    w, h, n, stride = pm.width, pm.height, pm.n, pm.stride
    rows = []
    for y in range(h):
        base = y * stride
        rows.append(any(pm.samples[base + i * n] < 150 for i in range(w)))
    return rows


def coldark(page, clip):
    pm = page.get_pixmap(clip=clip, matrix=fitz.Matrix(S, S))
    w, h, n, stride = pm.width, pm.height, pm.n, pm.stride
    cols = []
    for x in range(w):
        col = False
        for y in range(h):
            if pm.samples[y * stride + x * n] < 150:
                col = True
                break
        cols.append(col)
    return cols


for pi in (1, 2, 3):
    page = doc[pi]
    print(f"### page {pi + 1} rect={page.rect}")
    clip = fitz.Rect(60, 735, 560, 792)
    rr = ranges_of(rowdark(page, clip))
    print("  bottom y-ranges (x60-560):")
    for a, b in rr:
        print(f"    y {clip.y0 + a / S:.2f}..{clip.y0 + (b + 1) / S:.2f}")
    if rr:
        a, b = rr[-1]
        yc0, yc1 = clip.y0 + a / S, clip.y0 + (b + 1) / S
        cc = ranges_of(coldark(page, fitz.Rect(60, yc0, 560, yc1)))
        xr = [(round(60 + a2 / S, 1), round(60 + (b2 + 1) / S, 1)) for a2, b2 in cc]
        print(f"    last-range x-extents: {xr}")

page = doc[1]
clip = fitz.Rect(470, 20, 560, 110)
rr = ranges_of(rowdark(page, clip))
print("### page2 top-right (x470-560, y20-110) dark y-ranges:",
      [(round(clip.y0 + a / S, 1), round(clip.y0 + (b + 1) / S, 1)) for a, b in rr])
if rr:
    a, b = rr[0]
    cc = ranges_of(coldark(page, fitz.Rect(470, clip.y0 + a / S, 560, clip.y0 + (b + 1) / S)))
    print("    x-extents:", [(round(470 + a2 / S, 1), round(470 + (b2 + 1) / S, 1)) for a2, b2 in cc])
