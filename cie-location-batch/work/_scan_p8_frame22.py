# -*- coding: utf-8 -*-
"""帧22 (stack-16, Q4@p8) 核验: p8 (a)(b)(c) 标签、[1] 列、区域底部内容。只读本地 PDF。"""
import pymupdf

BR = "C:/Users/weo/Desktop/api/cie-location-batch"
qp = pymupdf.open(f"{BR}/tmp/0472/2026-Jun-22/0472_s26_qp_22.pdf")
p = qp[7]
print(f"p8 rect={p.rect} rotation={p.rotation}")

print("--- words x>500 ---")
for w in p.get_text("words"):
    r = w[:4]
    if r[0] > 500:
        print(f"  [{r[0]:.1f},{r[1]:.1f},{r[2]:.1f},{r[3]:.1f}] {w[4]!r}")

print("--- words y 600-700 x<200 (含 (c) 标签) ---")
for w in p.get_text("words"):
    r = w[:4]
    if 600 <= r[1] < 700 and r[0] < 200:
        print(f"  [{r[0]:.1f},{r[1]:.1f},{r[2]:.1f},{r[3]:.1f}] {w[4]!r}")

print("--- drawings y 600-700 ---")
for d in p.get_drawings():
    r = d["rect"]
    if 600 <= r.y0 < 700 and r.height > 0.3:
        print(f"  [{r.x0:.1f},{r.y0:.1f},{r.x1:.1f},{r.y1:.1f}] w={r.width:.1f} h={r.height:.1f}")

print("--- words y 700-750 (页脚/底部) ---")
for w in p.get_text("words"):
    r = w[:4]
    if 700 <= r[3]:
        print(f"  [{r[0]:.1f},{r[1]:.1f},{r[2]:.1f},{r[3]:.1f}] {w[4]!r}")
