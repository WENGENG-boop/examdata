# -*- coding: utf-8 -*-
"""帧23 (stack-17, Q4@p9) 核验: [1] 列位置、区域底缘 [Total: 12]、下方是否还有内容。只读本地 PDF。"""
import pymupdf

BR = "C:/Users/weo/Desktop/api/cie-location-batch"
qp = pymupdf.open(f"{BR}/tmp/0472/2026-Jun-22/0472_s26_qp_22.pdf")
p = qp[8]
print(f"p9 rect={p.rect} rotation={p.rotation}")

print("--- words x>500 (=[1] 列/右缘) ---")
for w in p.get_text("words"):
    r = w[:4]
    if r[0] > 500:
        print(f"  [{r[0]:.1f},{r[1]:.1f},{r[2]:.1f},{r[3]:.1f}] {w[4]!r}")

print("--- words y 540-600 (底缘附近, 含 Total) ---")
for w in p.get_text("words"):
    r = w[:4]
    if 540 <= r[1] < 600:
        print(f"  [{r[0]:.1f},{r[1]:.1f},{r[2]:.1f},{r[3]:.1f}] {w[4]!r}")

print("--- drawings y 540-620 ---")
for d in p.get_drawings():
    r = d["rect"]
    if 540 <= r.y0 < 620 and r.height > 0.3:
        print(f"  [{r.x0:.1f},{r.y0:.1f},{r.x1:.1f},{r.y1:.1f}] w={r.width:.1f} h={r.height:.1f}")

print("--- words y>=600 (底缘以下是否还有内容) ---")
for w in p.get_text("words"):
    r = w[:4]
    if r[3] >= 600:
        print(f"  [{r[0]:.1f},{r[1]:.1f},{r[2]:.1f},{r[3]:.1f}] {w[4]!r}")
