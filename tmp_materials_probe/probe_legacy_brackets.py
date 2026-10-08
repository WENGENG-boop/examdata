# -*- coding: utf-8 -*-
"""Print the day-bracket shapes (line-based paths) and light header bands per weekly page."""
import pymupdf
doc = pymupdf.open("tmp_materials_probe/downloads/zone5_gap7/2013-11.pdf")
for pno in range(len(doc)):
    page = doc[pno]
    text = page.get_text()
    if "Syllabus/Component" not in text or "Morning session" not in text:
        continue
    print(f"\n=== page {pno+1} ===")
    for d in page.get_drawings():
        r = d["rect"]
        items = d.get("items", [])
        itypes = [i[0] for i in items]
        fill = d.get("fill")
        if itypes and all(t == 'l' for t in itypes) and len(items) >= 3 and (r.y1 - r.y0) > 80:
            # day bracket: show the actual line segments
            segs = []
            for it in items:
                p1, p2 = it[1], it[2]
                segs.append(f"({p1.x:.1f},{p1.y:.1f})-({p2.x:.1f},{p2.y:.1f})")
            print(f"  BRACKET rect=({r.x0:.1f},{r.y0:.1f},{r.x1:.1f},{r.y1:.1f}) segs: {'; '.join(segs)}")
        elif itypes and all(t == 're' for t in itypes) and fill and abs(fill[0]-0.8009) < 0.01 and (r.x1-r.x0) > 250:
            print(f"  HEADBAND rect=({r.x0:.1f},{r.y0:.1f},{r.x1:.1f},{r.y1:.1f})")
