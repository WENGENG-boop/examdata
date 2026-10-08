# -*- coding: utf-8 -*-
"""帧34 (msreg-3) 核验: p6 y430-580（3(g)行底线与下一段伪表头）、p7 y0-140（M3@p7伪表头行证据）。只读本地 PDF。"""
import pymupdf

BR = "C:/Users/weo/Desktop/api/cie-location-batch"
ms = pymupdf.open(f"{BR}/tmp/0472/2026-Jun-22/0472_s26_ms_22.pdf")

for idx, y0, y1 in [(5, 430, 580), (6, 0, 140)]:
    p = ms[idx]
    print(f"=== p{idx+1} rect={p.rect} rot={p.rotation} ===")
    print("--- words ---")
    for w in p.get_text("words"):
        r = w[:4]
        if y0 <= r[1] < y1:
            print(f"  [{r[0]:.1f},{r[1]:.1f},{r[2]:.1f},{r[3]:.1f}] {w[4]!r}")
    print("--- drawings ---")
    for d in p.get_drawings():
        r = d["rect"]
        if (r.width > 0.3 or r.height > 0.3) and y0 <= r.y0 < y1:
            print(f"  [{r.x0:.1f},{r.y0:.1f},{r.x1:.1f},{r.y1:.1f}] w={r.width:.1f} h={r.height:.1f}")
