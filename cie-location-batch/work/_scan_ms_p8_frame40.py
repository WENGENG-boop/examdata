# -*- coding: utf-8 -*-
"""帧40 (msreg-9, M6(a)-M6(f)@p8) 核验: 各裁片底边与行分隔线对齐。只读本地 PDF。"""
import pymupdf

BR = "C:/Users/weo/Desktop/api/cie-location-batch"
ms = pymupdf.open(f"{BR}/tmp/0472/2026-Jun-22/0472_s26_ms_22.pdf")
p = ms[7]
print(f"p8 rect={p.rect} rotation={p.rotation}")

print("--- 横线/框线/灰底 y 80-400 ---")
for d in p.get_drawings():
    r = d["rect"]
    if (r.width > 0.3 or r.height > 0.3) and 80 <= r.y0 < 400:
        print(f"  [{r.x0:.1f},{r.y0:.1f},{r.x1:.1f},{r.y1:.1f}] w={r.width:.1f} h={r.height:.1f}")

print("--- 题号/分值词 (x<100 或 460<x<520) y 80-400 ---")
for w in p.get_text("words"):
    r = w[:4]
    if 80 <= r[1] < 400 and (r[0] < 100 or (460 < r[0] < 520)):
        print(f"  [{r[0]:.1f},{r[1]:.1f},{r[2]:.1f},{r[3]:.1f}] {w[4]!r}")

print("--- 行首词 y 80-400 (x 100-140) ---")
for w in p.get_text("words"):
    r = w[:4]
    if 80 <= r[1] < 400 and 100 <= r[0] < 140:
        print(f"  [{r[0]:.1f},{r[1]:.1f},{r[2]:.1f},{r[3]:.1f}] {w[4]!r}")
