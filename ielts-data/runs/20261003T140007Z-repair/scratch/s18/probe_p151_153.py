# -*- coding: utf-8 -*-
"""S18 probe: p151 (book10 T4 reading) Q19-26 rows; p153 (GT-B) Q22-27 glyph rows."""
import importlib.util
import json
import re

import pymupdf

spec = importlib.util.spec_from_file_location("pav", "ielts-api/tools/pdf-answer-values.py")
pav = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pav)

doc = pymupdf.open("tmp_audit_ielts/downloads/book_10.pdf")
ocr = json.load(open("ielts-data/runs/20261003T140007Z-repair/official-keys/ocr/book_10.json", encoding="utf-8"))
ocr_pages = {int(p["file_page"]): p.get("words") or [] for p in ocr.get("pages", [])}


def probe_page(pno, c, y_lo, y_hi, label):
    pg = doc[pno - 1]
    rawt = pav.raw_tokens(pg)
    words = ocr_pages[pno]
    band = (c + 10, c + 200)
    aband = (c - 10, c + 16)
    col_anchor_ys = []
    for w in words:
        m = pav.NUM_RE.match((w.get("text") or "").strip())
        if m and 1 <= int(m.group(1)) <= 45 and aband[0] <= w["x0"] <= aband[1]:
            col_anchor_ys.append(w["y0"])
    print(f"==== {label} page {pno} col {c} band {band} anchor-band {aband}")
    print("col_anchor_ys:", [round(y, 1) for y in sorted(col_anchor_ys)])
    o_items = [w for w in words if band[0] <= w["x0"] <= band[1]]
    r_items = [t for t in rawt if band[0] <= t["x0"] <= band[1]]
    orows = pav.build_rows(o_items, 5.0)
    rrows = pav.build_rows(r_items, 4.0)
    print(f"-- raw rows ({len(rrows)}):")
    for r in rrows:
        t = pav.join_raw_row(r["items"])
        if max(x["size"] for x in r["items"]) > 20:
            kept = "DROP(size)"
        elif re.search(r"[A-Za-z0-9]", t):
            kept = "KEEP"
        elif any(abs(r["y"] - ay) <= 7.0 for ay in col_anchor_ys):
            kept = "KEEP(anchor)"
        else:
            kept = "DROP(sym)"
        if y_lo <= r["y"] <= y_hi or kept.startswith("DROP"):
            print(f"   y={r['y']:.1f} x0={r['x0']:.1f} {kept} text={t[:60]!r} "
                  f"sizes={[x['size'] for x in r['items']][:6]} font={r['items'][0]['font']}")
    print(f"-- ocr rows ({len(orows)}):")
    for r in orows:
        t = " ".join((w.get("text") or "").strip() for w in r["items"])
        if y_lo <= r["y"] <= y_hi:
            print(f"   y={r['y']:.1f} x0={r['x0']:.1f} text={t[:70]!r}")
    print("-- rawt tokens in window:")
    for t in rawt:
        if y_lo <= t["y0"] <= y_hi and (c - 20) <= t["x0"] <= (c + 200):
            print(f"   y={t['y0']:.1f} x0={t['x0']:.1f} size={t['size']} font={t['font']} text={t['text']!r}")


probe_page(151, 57.1, 240, 420, "book10 T4 reading p151")
print()
probe_page(153, 275.6, 100, 200, "book10 GT-B p153")
