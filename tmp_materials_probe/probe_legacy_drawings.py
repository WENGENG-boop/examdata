# -*- coding: utf-8 -*-
import pymupdf
doc = pymupdf.open("tmp_materials_probe/downloads/zone5_gap7/2013-11.pdf")
for pno in (3, 5):
    page = doc[pno]
    ds = page.get_drawings()
    print(f"=== page {pno+1}: {len(ds)} drawings ===")
    from collections import Counter
    kinds = Counter(d.get("type") for d in ds)
    print("kinds:", dict(kinds))
    # print first 40 with rect + items summary
    for d in ds[:40]:
        r = d["rect"]
        items = d.get("items", [])
        itypes = Counter(i[0] for i in items)
        print(f"  type={d.get('type')} rect=({r.x0:.1f},{r.y0:.1f},{r.x1:.1f},{r.y1:.1f}) items={dict(itypes)} fill={d.get('fill')} color={d.get('color')} width={d.get('width')}")
