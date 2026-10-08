# -*- coding: utf-8 -*-
import pymupdf
from collections import Counter

for name, pno in [("2014-06.pdf", 3), ("2014-11.pdf", 7), ("2014-11.pdf", 11)]:
    doc = pymupdf.open(f"tmp_materials_probe/downloads/zone5_gap7/{name}")
    page = doc[pno]
    ds = page.get_drawings()
    print(f"=== {name} p{pno+1}: {len(ds)} drawings ===")
    for d in ds:
        r = d["rect"]
        items = d.get("items", [])
        itypes = Counter(i[0] for i in items)
        w, h = r.x1 - r.x0, r.y1 - r.y0
        if h > 60 or (itypes and list(itypes) != ['re']):
            print(f"  type={d.get('type')} rect=({r.x0:.1f},{r.y0:.1f},{r.x1:.1f},{r.y1:.1f}) w={w:.0f} h={h:.0f} items={dict(itypes)} fill={d.get('fill')}")
    # also: all items types across drawings
    allt = Counter()
    for d in ds:
        for i in d.get("items", []):
            allt[i[0]] += 1
    print("  item types overall:", dict(allt))
