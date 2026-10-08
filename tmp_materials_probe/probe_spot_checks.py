# -*- coding: utf-8 -*-
import sys
from pathlib import Path
import pymupdf
sys.path.insert(0, str(Path("examdata/src")))
from examdata.timetable import parser as P

# 1) 2014-11 p12: labels and last rows
doc = pymupdf.open("tmp_materials_probe/downloads/zone5_gap7/2014-11.pdf")
page = doc[11]
print("== 2014-11 p12 labels ==")
for (y, x0, x1, t) in sorted(P._legacy_page_spans(page)):
    c = P._legacy_clean(t)
    if x0 < 100 and c and P._legacy_parse_label(c):
        print(f"  y={y:7.1f} x={x0:5.1f} {c!r}")
print("  -- last data rows (y>960) --")
for (y, x0, x1, t) in sorted(P._legacy_page_spans(page)):
    c = P._legacy_clean(t)
    if y > 960 and x0 >= 140 and c and not P._legacy_is_noise(c) and c not in ("Code","Duration") and "Syllabus" not in c:
        print(f"  y={y:7.1f} x={x0:5.1f} {c[:45]!r}")

# 2) 2014-06 p4: labels vs rect brackets
doc2 = pymupdf.open("tmp_materials_probe/downloads/zone5_gap7/2014-06.pdf")
page2 = doc2[3]
print("\n== 2014-06 p4 labels vs rect brackets ==")
print("  brackets:", end=" ")
brs = []
for d in page2.get_drawings():
    r = d["rect"]
    if [i[0] for i in d.get("items", [])] == ["re"] and 30 <= (r.x1-r.x0) <= 80 and (r.y1-r.y0) >= 60:
        brs.append((round(r.y0,1), round(r.y1,1)))
print(brs)
for (y, x0, x1, t) in sorted(P._legacy_page_spans(page2)):
    c = P._legacy_clean(t)
    if x0 < 100 and c and P._legacy_parse_label(c):
        inside = [i for i,(b0,b1) in enumerate(brs) if b0 <= y <= b1]
        print(f"  y={y:7.1f} {c!r} inside bracket {inside}")
