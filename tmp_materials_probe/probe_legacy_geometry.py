# -*- coding: utf-8 -*-
"""Decide legacy date-label convention: does each day block's label sit at its
top or its bottom?  Uses page drawings (table borders) + span y-coordinates."""
import sys
from pathlib import Path

import pymupdf

PDF = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("tmp_materials_probe/downloads/zone5_gap7/2013-11.pdf")
PAGE = int(sys.argv[2]) if len(sys.argv) > 2 else 5

doc = pymupdf.open(PDF)
page = doc[PAGE]

print(f"=== page {PAGE+1} size={page.rect.width:.0f}x{page.rect.height:.0f} ===")

print("\n--- spans (y, x0, x1, text) ---")
spans = []
for block in page.get_text("dict")["blocks"]:
    if block["type"] != 0:
        continue
    for line in block["lines"]:
        for span in line["spans"]:
            text = span["text"].strip()
            if text:
                spans.append((round(span["bbox"][1], 1), round(span["bbox"][0], 1), round(span["bbox"][2], 1), text))
for y, x0, x1, text in sorted(spans):
    print(f"y={y:7.1f} x=[{x0:6.1f},{x1:6.1f}] {text!r}")

print("\n--- drawings: filled rects / lines (big ones) ---")
seen = set()
for d in page.get_drawings():
    r = d["rect"]
    key = (round(r.x0, 1), round(r.y0, 1), round(r.x1, 1), round(r.y1, 1))
    if key in seen:
        continue
    seen.add(key)
    w, h = r.x1 - r.x0, r.y1 - r.y0
    kind = d.get("type", "?")
    if w * h > 400 or (h < 3 and w > 100) or (w < 3 and h > 40):
        print(f"{kind:8s} rect x=[{r.x0:6.1f},{r.x1:6.1f}] y=[{r.y0:6.1f},{r.y1:6.1f}] w={w:6.1f} h={h:6.1f}")
