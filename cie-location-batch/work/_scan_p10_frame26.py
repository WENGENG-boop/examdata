# -*- coding: utf-8 -*-
"""帧26 (stack-20, Q5@p10) 核验: y480-650 内容、e 框底、答案线、右缘 x。只读本地 PDF。"""
import pymupdf

BR = "C:/Users/weo/Desktop/api/cie-location-batch"
qp = pymupdf.open(f"{BR}/tmp/0472/2026-Jun-22/0472_s26_qp_22.pdf")
p = qp[9]
print(f"p10 rect={p.rect} rotation={p.rotation}")

print("--- words y 480-660 (e 框内容与底缘) ---")
for w in p.get_text("words"):
    r = w[:4]
    if 480 <= r[1] < 660:
        print(f"  [{r[0]:.1f},{r[1]:.1f},{r[2]:.1f},{r[3]:.1f}] {w[4]!r}")

print("--- drawings y 480-660 ---")
for d in p.get_drawings():
    r = d["rect"]
    if 480 <= r.y0 < 660 and (r.height > 0.3 or r.width > 0.3):
        print(f"  [{r.x0:.1f},{r.y0:.1f},{r.x1:.1f},{r.y1:.1f}] w={r.width:.1f} h={r.height:.1f}")

print("--- drawings x>440 (右缘答案线/点) ---")
for d in p.get_drawings():
    r = d["rect"]
    if r.x0 > 440:
        print(f"  [{r.x0:.1f},{r.y0:.1f},{r.x1:.1f},{r.y1:.1f}] w={r.width:.1f} h={r.height:.1f}")

print("--- words y 660-760 (页脚) ---")
for w in p.get_text("words"):
    r = w[:4]
    if 660 <= r[1] < 760:
        print(f"  [{r[0]:.1f},{r[1]:.1f},{r[2]:.1f},{r[3]:.1f}] {w[4]!r}")
