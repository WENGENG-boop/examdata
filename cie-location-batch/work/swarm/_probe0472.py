"""Compute objective per-question QP regions for 0472/2026/Jun/11 (span-level markers)."""
import json
import re
import pymupdf

PDF = r"C:\Users\weo\Desktop\api\cie-location-batch\tmp\0472\2026-Jun-11\0472_s26_qp_11.pdf"
OUT = r"C:\Users\weo\Desktop\api\cie-location-batch\work\swarm\_probe0472.json"

# question -> page, read off the rendered/text content of the printed paper
QMAP = {1: 3, 2: 3, 3: 4, 4: 4, 5: 4, 6: 5, 7: 5, 8: 5,
        9: 6, 10: 6, 11: 6, 12: 7, 13: 7, 14: 7,
        15: 8, 16: 8, 17: 8, 18: 8, 19: 8,
        20: 9, 21: 9, 22: 9, 23: 10, 24: 10, 25: 10, 26: 10,
        27: 11, 28: 11, 29: 12, 30: 12, 31: 12, 32: 13, 33: 13, 34: 13,
        35: 14, 36: 14, 37: 15}

doc = pymupdf.open(PDF)
PAD = 3.0
NUM = re.compile(r"^(\d{1,2})(?:\s|$)")

pages = {}
for pno in range(1, doc.page_count + 1):
    pg = doc[pno - 1]
    spans, blocks = [], []
    for blk in pg.get_text("dict")["blocks"]:
        if blk.get("type") != 0:
            continue
        for line in blk["lines"]:
            for sp in line["spans"]:
                t = sp["text"].strip()
                if t:
                    spans.append({"x0": sp["bbox"][0], "y0": sp["bbox"][1],
                                  "x1": sp["bbox"][2], "y1": sp["bbox"][3], "t": t})
        txt = " ".join(s["text"] for l in blk["lines"] for s in l["spans"]).strip()
        if txt:
            blocks.append({"x0": blk["bbox"][0], "y0": blk["bbox"][1],
                           "x1": blk["bbox"][2], "y1": blk["bbox"][3], "t": txt})
    pages[pno] = {"spans": spans, "blocks": blocks,
                  "draws": [tuple(d["rect"]) for d in pg.get_drawings()],
                  "imgs": [tuple(i["bbox"]) for i in pg.get_image_info()]}

# locate the question-number marker span on each page
markers = {}
for pno, pg in pages.items():
    got = {}
    for sp in pg["spans"]:
        m = NUM.match(sp["t"])
        if not m or sp["x0"] > 130:
            continue
        n = int(m.group(1))
        if QMAP.get(n) != pno:      # only accept a number that really starts a question here
            continue
        if n in got and got[n]["y0"] <= sp["y0"]:
            continue
        got[n] = sp
    markers[pno] = got

report = {}
for q, pno in sorted(QMAP.items()):
    pg = pages[pno]
    mk = markers[pno].get(q)
    if mk is None:
        print("!! marker missing", q, "page", pno)
        continue
    y_lo = mk["y0"] - PAD
    if q in (15, 16, 17, 18, 19):      # shared "Information" stimulus + section rubric
        for b in pg["blocks"]:
            if b["t"].startswith("Questions 15"):
                y_lo = min(y_lo, b["y0"] - PAD)
    # lower bound: next marker on the page, or the next "Questions n-m" section header
    y_hi = 792.0
    for n, sp in markers[pno].items():
        if n != q and sp["y0"] > mk["y0"]:
            y_hi = min(y_hi, sp["y0"] - PAD)
    for b in pg["blocks"]:
        if b["t"].startswith("Questions ") and b["y0"] > mk["y0"]:
            y_hi = min(y_hi, b["y0"] - PAD)
    for b in pg["blocks"]:
        if b["t"].startswith("[Turn over") and b["y0"] > mk["y0"]:
            y_hi = min(y_hi, b["y0"] + 12)
    cover = [mk["x0"], mk["y0"], mk["x1"], mk["y1"]]
    for b in pg["blocks"]:
        if b["y0"] >= y_lo - 1 and b["y1"] <= y_hi + 1:
            if "Cambridge University Press" in b["t"] or b["t"].startswith("©"):
                continue
            cover = [min(cover[0], b["x0"]), min(cover[1], b["y0"]),
                     max(cover[2], b["x1"]), max(cover[3], b["y1"])]
    for r in pg["draws"] + pg["imgs"]:
        cy = (r[1] + r[3]) / 2.0
        if y_lo <= cy <= y_hi and r[2] > 72 and r[0] < 560:
            cover = [min(cover[0], r[0]), min(cover[1], r[1]),
                     max(cover[2], r[2]), max(cover[3], r[3])]
    report[q] = [{"page": pno, "bbox": [round(v, 1) for v in cover]}]

json.dump(report, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for q in sorted(report):
    print(q, "p%d" % QMAP[q], report[q][0]["bbox"])
