import pymupdf

doc = pymupdf.open("C:/Users/weo/Desktop/api/tmp_audit_ielts/downloads/book_10.pdf")
pg = doc[151]  # p152
dpi = 1200; scale = dpi/72.0

bands = [(220.4,227.2),(231.4,238.2),(242.4,249.2),(253.7,260.5),(264.8,271.6),
         (275.8,282.6),(287.1,293.9),(298.1,304.9),(309.4,316.0),(320.4,327.0),
         (331.5,338.0),(342.3,349.3),(353.6,360.0)]

crops = []
for i,(y0,y1) in enumerate(bands):
    clip = pymupdf.Rect(258.0, y0-1.0, 270.0, y1+1.0)
    pix = pg.get_pixmap(matrix=pymupdf.Matrix(scale,scale), clip=clip, alpha=False, colorspace=pymupdf.csGRAY)
    w,h = pix.width, pix.height
    s = pix.samples
    def dark(x,y): return s[y*pix.stride + x] < 128
    xs_d = [x for x in range(w) if any(dark(x,y) for y in range(h))]
    ys_d = [y for y in range(h) if any(dark(x,y) for x in range(w))]
    if not xs_d:
        print(f"glyph {i+1}: EMPTY"); crops.append(None); continue
    x0,x1,y0p,y1p = min(xs_d), max(xs_d), min(ys_d), max(ys_d)
    cw, ch = x1-x0+1, y1p-y0p+1
    c = [[1 if dark(x,y) else 0 for x in range(x0,x1+1)] for y in range(y0p,y1p+1)]
    crops.append(c)
    print(f"=== glyph {i+1} band y={y0}-{y1} bbox {cw}x{ch}px")
    step_r = max(1, ch//22); step_c = max(1, cw//44)
    for r in range(0, ch, step_r):
        print(''.join('#' if v else ' ' for v in c[r][::step_c]))

def norm(c, size=48):
    if c is None: return None
    ch, cw = len(c), len(c[0])
    out = []
    for a in range(size):
        ya0 = a*ch//size; ya1 = max(ya0+1, (a+1)*ch//size)
        row = []
        for b in range(size):
            xb0 = b*cw//size; xb1 = max(xb0+1, (b+1)*cw//size)
            tot = 0; cnt = 0
            for y in range(ya0, min(ya1,ch)):
                for x in range(xb0, min(xb1,cw)):
                    tot += c[y][x]; cnt += 1
            row.append(tot/cnt if cnt else 0)
        out.append(row)
    return out

norms = [norm(c) for c in crops]
print("\n=== pairwise mean-abs-diff (low = same glyph) ===")
hdr = "     " + "".join(f"{j+1:>7}" for j in range(13))
print(hdr)
for i in range(13):
    row = []
    for j in range(13):
        if norms[i] is None or norms[j] is None: row.append("   -   ")
        else:
            d = sum(abs(norms[i][a][b]-norms[j][a][b]) for a in range(48) for b in range(48))/2304
            row.append(f"{d:7.3f}")
    print(f"{i+1:>3}: " + "".join(row))
