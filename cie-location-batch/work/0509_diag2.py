# -*- coding: utf-8 -*-
"""0509 forensics round 2: page rotation, text dirs, strip content, fresh renders."""
import json
import pymupdf

BASE = r"C:/Users/weo/Desktop/api/cie-location-batch"
TMP = BASE + "/tmp/0509/2026-Jun-11"
PROBE = TMP + "/probe"
MS = TMP + "/0509_s26_ms_11.pdf"
QP = TMP + "/0509_s26_qp_11.pdf"

doc = pymupdf.open(MS)
print("MS pages:", doc.page_count)
for pno in range(doc.page_count):
    page = doc[pno]
    print(f"p{pno+1}: rot={page.rotation} rect={page.rect} mb={page.mediabox} crop={page.cropbox} imgs={len(page.get_images())}")

print("\n=== text dir histogram (pages 8,12,14,15) ===")
for pno in [7, 11, 13, 14]:
    page = doc[pno]
    d = page.get_text("dict")
    hist = {}
    sample = {}
    for b in d["blocks"]:
        if b["type"] != 0:
            continue
        for l in b["lines"]:
            key = tuple(round(x, 1) for x in l.get("dir", (1, 0)))
            txt = "".join(s["text"] for s in l["spans"])
            hist[key] = hist.get(key, 0) + 1
            if key not in sample and txt.strip():
                sample[key] = (txt[:40], [round(x, 1) for x in l["bbox"]])
    print(f"p{pno+1}: {hist}")
    for k, v in sample.items():
        print("   dir", k, "->", v)

def strip_spans(page, r, label, cap=60):
    print(f"\n=== {label}: spans intersecting {[round(x,1) for x in r]} ===")
    d = page.get_text("dict")
    cnt = 0
    rows = []
    for b in d["blocks"]:
        if b["type"] != 0:
            continue
        for l in b["lines"]:
            lb = pymupdf.Rect(l["bbox"])
            if lb.intersects(r):
                for s in l["spans"]:
                    sb = pymupdf.Rect(s["bbox"])
                    if sb.intersects(r):
                        cnt += 1
                        rows.append((tuple(round(x) for x in l.get("dir", (1, 0))), [round(x, 1) for x in s["bbox"]], s["text"][:70]))
    for row in rows[:cap]:
        print("  ", row)
    print("  total:", cnt)
    return rows

p14 = doc[13]
p15 = doc[14]
strip_spans(p14, pymupdf.Rect(411.03, 62.2, 480.31, 779.7), "p14 strip r07")
strip_spans(p15, pymupdf.Rect(74.26, 57.08, 200.62, 779.7), "p15 strip r01")

print("\n=== p14 all line bboxes (first 60) ===")
d = p14.get_text("dict")
lines = []
for b in d["blocks"]:
    if b["type"] != 0:
        continue
    for l in b["lines"]:
        txt = "".join(s["text"] for s in l["spans"])[:50]
        lines.append(([round(x, 1) for x in l["bbox"]], txt))
lines.sort(key=lambda t: (t[0][0], t[0][1]))
for ln in lines[:60]:
    print("  ", ln)
print("  total lines:", len(lines))

print("\n=== p15 all line bboxes (first 40) ===")
d = p15.get_text("dict")
lines = []
for b in d["blocks"]:
    if b["type"] != 0:
        continue
    for l in b["lines"]:
        txt = "".join(s["text"] for s in l["spans"])[:50]
        lines.append(([round(x, 1) for x in l["bbox"]], txt))
lines.sort(key=lambda t: (t[0][0], t[0][1]))
for ln in lines[:40]:
    print("  ", ln)
print("  total lines:", len(lines))

# fresh renders
for pno, name in [(13, "ms-14-fresh.png"), (14, "ms-15-fresh.png")]:
    page = doc[pno]
    pix = page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5))
    pix.save(PROBE + "/" + name)
    print("saved", name, pix.width, pix.height)

page = p14
clip = pymupdf.Rect(411.03, 62.2, 480.31, 779.7) * page.rotation_matrix
pix = page.get_pixmap(clip=clip, matrix=pymupdf.Matrix(1.65, 1.65))
pix.save(PROBE + "/r07-fresh.png")
print("saved r07-fresh.png", pix.width, pix.height)

page = p15
clip = pymupdf.Rect(74.26, 57.08, 200.62, 779.7) * page.rotation_matrix
pix = page.get_pixmap(clip=clip, matrix=pymupdf.Matrix(1.65, 1.65))
pix.save(PROBE + "/r01-fresh.png")
print("saved r01-fresh.png", pix.width, pix.height)

# ink profiles
def row_profile(page, clip, zoom, thresh=200):
    pix = page.get_pixmap(clip=clip, matrix=pymupdf.Matrix(zoom, zoom), colorspace=pymupdf.csGRAY)
    w, h = pix.width, pix.height
    s = pix.samples
    stride = pix.stride
    out = []
    for yy in range(h):
        base = yy * stride
        ink = 0
        for xx in range(w):
            if s[base + xx] < thresh:
                ink += 1
        out.append(ink)
    return out

def col_profile(page, clip, zoom, thresh=200):
    pix = page.get_pixmap(clip=clip, matrix=pymupdf.Matrix(zoom, zoom), colorspace=pymupdf.csGRAY)
    w, h = pix.width, pix.height
    s = pix.samples
    stride = pix.stride
    out = []
    for xx in range(w):
        ink = 0
        for yy in range(h):
            if s[yy * stride + xx] < thresh:
                ink += 1
        out.append(ink)
    return out

print("\n=== p8 ink rows y 45..72 (x 55..545, zoom 4) ===")
p8 = doc[7]
clip = pymupdf.Rect(55, 45, 545, 72) * p8.rotation_matrix
prof = row_profile(p8, clip, 4)
for i, c in enumerate(prof):
    y = 45 + (i + 0.5) / 4
    if c > 0:
        print(f"  y={y:.2f} ink={c}")
print("  (rows with ink listed above; blank otherwise)")

print("\n=== p12 column ink x 85..150 (y 60..670, zoom 4) ===")
p12 = doc[11]
clip = pymupdf.Rect(85, 60, 150, 670) * p12.rotation_matrix
prof = col_profile(p12, clip, 4)
for i, c in enumerate(prof):
    x = 85 + (i + 0.5) / 4
    if c > 0:
        print(f"  x={x:.2f} ink={c}")

print("\n=== QP page rotations ===")
qd = pymupdf.open(QP)
for pno in range(qd.page_count):
    page = qd[pno]
    print(f"qp p{pno+1}: rot={page.rotation} rect={page.rect}")

# dump failed qp regions from current index
print("\n=== current index qp regions for failed questions ===")
idx = json.load(open(BASE + "/indexes/0509/2026-Jun-11/cie-index.json", encoding="utf-8"))
failed = {"1(a)", "1(b)", "1(c)", "1(d)", "1(e)", "1(g)", "1(h)", "3", "3(a)", "3(b)", "3(c)", "3(d)", "3(e)", "3(e)(iii)", "3(e)(iv)", "3(f)"}
for q in idx["questions"]:
    if q["question"] in failed:
        print(q["question"], "qp:", q.get("qp"))
