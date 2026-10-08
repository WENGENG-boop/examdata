# -*- coding: utf-8 -*-
"""帧27 (stack-21, Q5@p11) 核验: y0=58.8 是否切标题、y1=700.6 是否含 [5] 排除页脚、盒线 x 缘。只读本地 PDF。"""
import pymupdf

BR = "C:/Users/weo/Desktop/api/cie-location-batch"
qp = pymupdf.open(f"{BR}/tmp/0472/2026-Jun-22/0472_s26_qp_22.pdf")
p = qp[10]
print(f"p11 rect={p.rect} rotation={p.rotation}")

print("--- words y 0-120 (页眉 + 标题) ---")
for w in p.get_text("words"):
    r = w[:4]
    if r[1] < 120:
        print(f"  [{r[0]:.1f},{r[1]:.1f},{r[2]:.1f},{r[3]:.1f}] {w[4]!r}")

print("--- words y 640-790 (底部 [5] 与页脚) ---")
for w in p.get_text("words"):
    r = w[:4]
    if 640 <= r[1] < 790:
        print(f"  [{r[0]:.1f},{r[1]:.1f},{r[2]:.1f},{r[3]:.1f}] {w[4]!r}")

print("--- drawings (盒线) 全部 ---")
for d in p.get_drawings():
    r = d["rect"]
    if r.width > 0.3 or r.height > 0.3:
        print(f"  [{r.x0:.1f},{r.y0:.1f},{r.x1:.1f},{r.y1:.1f}] w={r.width:.1f} h={r.height:.1f}")

print("--- words x<75 (左缘) ---")
for w in p.get_text("words"):
    r = w[:4]
    if r[0] < 75:
        print(f"  [{r[0]:.1f},{r[1]:.1f},{r[2]:.1f},{r[3]:.1f}] {w[4]!r}")

print("--- words x>500 (右缘) ---")
for w in p.get_text("words"):
    r = w[:4]
    if r[2] > 500:
        print(f"  [{r[0]:.1f},{r[1]:.1f},{r[2]:.1f},{r[3]:.1f}] {w[4]!r}")
