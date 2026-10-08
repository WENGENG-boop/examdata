import sys, json
import pymupdf

QP = r"C:/Users/weo/Desktop/api/cie-location-batch/tmp/0472/2025-Jun-21/0472_s25_qp_21.pdf"
MS = r"C:/Users/weo/Desktop/api/cie-location-batch/tmp/0472/2025-Jun-21/0472_s25_ms_21.pdf"

doc = pymupdf.open(QP)

# p14: check y-range of ink in x sub-bands 520..585
page = doc[13]
d = page.get_text("dict")
H = page.rect.height
print("=== QP p14 (index 13) x-band y-profiles ===")
bands = [(500,510),(510,520),(520,528),(528,536),(536,544),(544,552),(552,560),(560,566),(566,574),(574,582),(582,590)]
for x0,x1 in bands:
    ys = []
    for b in d["blocks"]:
        for l in b.get("lines", []):
            for s in l.get("spans", []):
                r = pymupdf.Rect(s["bbox"])
                if r.x1 > x0 and r.x0 < x1 and s["text"].strip():
                    ys.append((round(r.y0,1), round(r.y1,1), s["text"][:25]))
    drawings = []
    for dr in page.get_drawings():
        r = dr["rect"]
        if r.x1 > x0 and r.x0 < x1:
            drawings.append((round(r.y0,1), round(r.y1,1), "draw"))
    imgs = []
    for im in page.get_image_info():
        r = pymupdf.Rect(im["bbox"])
        if r.x1 > x0 and r.x0 < x1:
            imgs.append((round(r.y0,1), round(r.y1,1), "img"))
    allitems = sorted(ys + drawings + imgs)
    if allitems:
        ymin = min(i[0] for i in allitems); ymax = max(i[1] for i in allitems)
        ntext = len(ys)
        print(f"x[{x0},{x1}): items={len(allitems)} (text={ntext},draw={len(drawings)},img={len(imgs)}) y-range=[{ymin},{ymax}]")
        # show first few
        for it in allitems[:6]:
            print(f"    {it}")
    else:
        print(f"x[{x0},{x1}): EMPTY")

# Also pixel-based scan for the same bands to catch raster content
print()
print("=== pixel dark-pixel scan p14 (2px/pt render) ===")
zoom = 2.0
pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
import numpy as np
arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
gray = arr[:,:,:3].mean(axis=2)
for x0,x1 in bands:
    px0, px1 = int(x0*zoom), int(x1*zoom)
    band = gray[:, px0:px1]
    dark = (band < 128)
    rows = np.where(dark.any(axis=1))[0]
    if len(rows):
        print(f"x[{x0},{x1}): dark rows y=[{rows.min()/zoom:.1f},{rows.max()/zoom:.1f}] count={len(rows)} (of {gray.shape[0]})")
    else:
        print(f"x[{x0},{x1}): no dark pixels")

doc.close()

# MS pages: check ink beyond x474 and below x76
print()
print("=== MS boundary scan (all pages) ===")
doc = pymupdf.open(MS)
for pi in range(len(doc)):
    page = doc[pi]
    pix = page.get_pixmap(matrix=pymupdf.Matrix(2.0,2.0))
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    gray = arr[:,:,:3].mean(axis=2)
    dark = gray < 128
    # right of x474
    right = dark[:, int(474*2):]
    cols = np.where(right.any(axis=0))[0]
    if len(cols):
        xmin = (474*2 + cols.min())/2.0
        print(f"ms p{pi+1}: ink right of 474 from x={xmin:.1f} (count cols={len(cols)})")
    else:
        print(f"ms p{pi+1}: no ink right of 474")
    # left of x76
    left = dark[:, :int(76*2)]
    cols = np.where(left.any(axis=0))[0]
    if len(cols):
        xmax = cols.max()/2.0
        print(f"ms p{pi+1}: ink left of 76 up to x={xmax:.1f} (count cols={len(cols)})")
    else:
        print(f"ms p{pi+1}: no ink left of 76")
    # overall ink extent
    cols_all = np.where(dark.any(axis=0))[0]
    rows_all = np.where(dark.any(axis=1))[0]
    print(f"ms p{pi+1}: overall ink x=[{cols_all.min()/2.0:.1f},{cols_all.max()/2.0:.1f}] y=[{rows_all.min()/2.0:.1f},{rows_all.max()/2.0:.1f}]")
doc.close()
print("DONE")
