# -*- coding: utf-8 -*-
"""帧19 (stack-13, Q3(a)(b)(c)@p6) 核验: p6 右列 [1] 位置。只读本地 PDF。"""
import pymupdf

BR = "C:/Users/weo/Desktop/api/cie-location-batch"
qp = pymupdf.open(f"{BR}/tmp/0472/2026-Jun-22/0472_s26_qp_22.pdf")
p = qp[5]
print(f"p6 rect={p.rect} rotation={p.rotation}")

print("--- words x>500 ---")
for w in p.get_text("words"):
    r = w[:4]
    if r[0] > 500:
        print(f"  [{r[0]:.1f},{r[1]:.1f},{r[2]:.1f},{r[3]:.1f}] {w[4]!r}")

print("--- words y 290-320 ((a) 标签区) ---")
for w in p.get_text("words"):
    r = w[:4]
    if 290 <= r[1] < 320 and r[0] < 130:
        print(f"  [{r[0]:.1f},{r[1]:.1f},{r[2]:.1f},{r[3]:.1f}] {w[4]!r}")

print("--- words y 440-460 ((b) 标签区) ---")
for w in p.get_text("words"):
    r = w[:4]
    if 440 <= r[1] < 460 and r[0] < 130:
        print(f"  [{r[0]:.1f},{r[1]:.1f},{r[2]:.1f},{r[3]:.1f}] {w[4]!r}")
