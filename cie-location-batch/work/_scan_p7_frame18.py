# -*- coding: utf-8 -*-
"""帧18 (stack-12, Q3@p7) 坐标核验: 页眉条形码底部、(d) 标签顶、[1]/[Total: 7] 位置。只读本地 PDF。"""
import pymupdf

BR = "C:/Users/weo/Desktop/api/cie-location-batch"
qp = pymupdf.open(f"{BR}/tmp/0472/2026-Jun-22/0472_s26_qp_22.pdf")
p = qp[6]
print(f"p7 rect={p.rect} rotation={p.rotation}")

print("--- words y<80 (页眉区) ---")
for w in p.get_text("words"):
    r = w[:4]
    if r[3] < 80:
        print(f"  [{r[0]:.1f},{r[1]:.1f},{r[2]:.1f},{r[3]:.1f}] {w[4]!r}")

print("--- drawings y<80 ---")
for d in p.get_drawings():
    r = d["rect"]
    if r.y0 < 80 and r.width > 1 and r.height > 0.5:
        print(f"  [{r.x0:.1f},{r.y0:.1f},{r.x1:.1f},{r.y1:.1f}] w={r.width:.1f} h={r.height:.1f}")

print("--- words y 80-130 (d 区) ---")
for w in p.get_text("words"):
    r = w[:4]
    if 80 <= r[1] < 130:
        print(f"  [{r[0]:.1f},{r[1]:.1f},{r[2]:.1f},{r[3]:.1f}] {w[4]!r}")

print("--- words x>500 (右列 [1] 等) ---")
for w in p.get_text("words"):
    r = w[:4]
    if r[0] > 500:
        print(f"  [{r[0]:.1f},{r[1]:.1f},{r[2]:.1f},{r[3]:.1f}] {w[4]!r}")

print("--- words y>560 (底部 [Total] 区) ---")
for w in p.get_text("words"):
    r = w[:4]
    if r[1] > 560:
        print(f"  [{r[0]:.1f},{r[1]:.1f},{r[2]:.1f},{r[3]:.1f}] {w[4]!r}")
