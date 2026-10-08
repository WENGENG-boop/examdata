# -*- coding: utf-8 -*-
"""帧33 (msreg-2, M2@p6) 核验: y1 385.2→346.1 边界、Q3伪表头行证据。只读本地 PDF。"""
import pymupdf

BR = "C:/Users/weo/Desktop/api/cie-location-batch"
ms = pymupdf.open(f"{BR}/tmp/0472/2026-Jun-22/0472_s26_ms_22.pdf")
p = ms[5]
print(f"p6 rect={p.rect} rotation={p.rotation}")

print("--- words y 190-430 ---")
for w in p.get_text("words"):
    r = w[:4]
    if 190 <= r[1] < 430:
        print(f"  [{r[0]:.1f},{r[1]:.1f},{r[2]:.1f},{r[3]:.1f}] {w[4]!r}")

print("--- drawings y 190-430 (横线/框线/灰底) ---")
for d in p.get_drawings():
    r = d["rect"]
    if (r.width > 0.3 or r.height > 0.3) and 190 <= r.y0 < 430:
        print(f"  [{r.x0:.1f},{r.y0:.1f},{r.x1:.1f},{r.y1:.1f}] w={r.width:.1f} h={r.height:.1f}")

print("--- words x<80 (左缘) y190-430 ---")
for w in p.get_text("words"):
    r = w[:4]
    if r[0] < 80 and 190 <= r[1] < 430:
        print(f"  [{r[0]:.1f},{r[1]:.1f},{r[2]:.1f},{r[3]:.1f}] {w[4]!r}")

print("--- words x>460 (右缘) y190-430 ---")
for w in p.get_text("words"):
    r = w[:4]
    if r[2] > 460 and 190 <= r[1] < 430:
        print(f"  [{r[0]:.1f},{r[1]:.1f},{r[2]:.1f},{r[3]:.1f}] {w[4]!r}")
