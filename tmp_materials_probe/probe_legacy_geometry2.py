# -*- coding: utf-8 -*-
"""Full dump: spans + horizontal rules + section headers + margin labels, pages 4-8."""
import sys
from pathlib import Path
import pymupdf

PDF = Path("tmp_materials_probe/downloads/zone5_gap7/2013-11.pdf")
doc = pymupdf.open(PDF)
out = []
for pno in range(len(doc)):
    page = doc[pno]
    text = page.get_text()
    is_weekly = ("Morning session" in text or "Morning Session" in text) and (
        "Syllabus/Component" in text or "Syllabus / Component" in text)
    out.append(f"\n########## PAGE {pno+1}  weekly={is_weekly}  size={page.rect.width:.0f}x{page.rect.height:.0f}")
    if not is_weekly:
        out.append("(non-weekly page, first 200 chars: " + repr(text[:200]) + ")")
        continue
    # headers and margin labels
    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 0: continue
        for line in block["lines"]:
            for span in line["spans"]:
                t = span["text"].strip()
                if not t: continue
                x0, y0 = span["bbox"][0], span["bbox"][1]
                if "Syllabus" in t and "Component" in t:
                    out.append(f"HEADER  y={y0:7.1f} x={x0:6.1f} {t!r}")
                elif x0 < 140 and y0 > 80:
                    out.append(f"MARGIN  y={y0:7.1f} x={x0:6.1f} {t!r}")
    # horizontal rules: drawings with h<3 and w>300
    rules = []
    for d in page.get_drawings():
        r = d["rect"]
        if (r.y1 - r.y0) < 3 and (r.x1 - r.x0) > 300:
            rules.append((round(r.y0,1), round(r.x0,1), round(r.x1,1)))
    rules.sort()
    out.append(f"HRULES({len(rules)}): " + "; ".join(f"y={y:.1f}[{x0:.0f}-{x1:.0f}]" for y,x0,x1 in rules))
Path("tmp_materials_probe/legacy_geometry_full.txt").write_text("\n".join(out), encoding="utf-8")
print("written", len(out), "lines")
