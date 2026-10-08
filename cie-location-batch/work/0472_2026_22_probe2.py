# -*- coding: utf-8 -*-
"""第二组探针 0472/2026/Jun/22: 解决修复清单剩余未定数值。只读本地 PDF。"""
import pymupdf

BR = "C:/Users/weo/Desktop/api/cie-location-batch"
qp = pymupdf.open(f"{BR}/tmp/0472/2026-Jun-22/0472_s26_qp_22.pdf")
ms = pymupdf.open(f"{BR}/tmp/0472/2026-Jun-22/0472_s26_ms_22.pdf")


def words(page, ymin=-1e9, ymax=1e9, xmin=-1e9, xmax=1e9):
    out = []
    for w in page.get_text("words"):
        r = w[:4]
        if r[1] >= ymin and r[3] <= ymax and r[0] >= xmin and r[2] <= xmax:
            out.append((r, w[4]))
    return out


def draws(page, ymin=-1e9, ymax=1e9, xmin=-1e9, xmax=1e9, minw=0.5, minh=0.5):
    out = []
    for d in page.get_drawings():
        r = d["rect"]
        if r.width < minw and r.height < minh:
            continue
        if r.y1 >= ymin and r.y0 <= ymax and r.x1 >= xmin and r.x0 <= xmax:
            out.append(r)
    return out


def show_w(rs, tag):
    print(f"  W {tag}: {len(rs)}")
    for r, t in rs:
        print(f"    [{r[0]:.1f},{r[1]:.1f},{r[2]:.1f},{r[3]:.1f}] {t!r}")


def show_d(rs, tag):
    print(f"  D {tag}: {len(rs)}")
    for r in rs:
        print(f"    [{r.x0:.1f},{r.y0:.1f},{r.x1:.1f},{r.y1:.1f}] w={r.width:.1f} h={r.height:.1f}")


print("========== A. QP p3 bottom (y>=690) ==========")
p = qp[2]
show_w(words(p, ymin=690), "p3 y>=690")
show_d(draws(p, ymin=690, minw=1.0, minh=0.5), "p3 y>=690 w>=1")

print("========== B. QP [1]/[Total] marks x>500 ==========")
for pno in range(1, 14):
    p = qp[pno]
    rs = words(p, ymin=60, xmin=500)
    keep = [(r, t) for r, t in rs if r[0] > 500 and r[1] > 60]
    show_w(keep, f"p{pno + 1} x>500")

print("========== C. QP p10 structure ==========")
p = qp[9]
print(f"p10 rect={p.rect} rotation={p.rotation}")
show_w(words(p, ymin=55), "p10 all words")
ds = draws(p, ymin=55, minw=1.0, minh=1.0)
print(f"  D p10 w>=1 h>=1: {len(ds)}")
for r in ds:
    print(f"    [{r.x0:.1f},{r.y0:.1f},{r.x1:.1f},{r.y1:.1f}] w={r.width:.1f} h={r.height:.1f}")

print("========== D. QP p11 structure ==========")
p = qp[10]
print(f"p11 rect={p.rect} rotation={p.rotation}")
show_w(words(p, ymin=640), "p11 y>=640 words")
show_d(draws(p, ymin=640, minw=1.0, minh=0.5), "p11 y>=640 draws")
show_d(draws(p, minw=1.0, minh=1.0, xmin=45.0), "p11 draws x>=45 w/h>=1 (count)")

print("========== E. QP p12 bottom ==========")
p = qp[11]
show_w(words(p, ymin=630), "p12 y>=630")
show_d(draws(p, ymin=630, minw=1.0, minh=0.3), "p12 y>=630")

print("========== F. QP p13 bottom ==========")
p = qp[12]
show_w(words(p, ymin=420), "p13 y>=420")
show_d(draws(p, ymin=420, minw=1.0, minh=0.3), "p13 y>=420")

print("========== G. MS p6 bottom (y>=500) ==========")
p = ms[5]
show_w(words(p, ymin=500), "ms p6 y>=500")
show_d(draws(p, ymin=500, minw=1.0, minh=0.3), "ms p6 y>=500")

print("========== G2. MS p6 section1 (y 130-200) ==========")
show_w(words(p, ymin=130, ymax=200), "ms p6 130-200")
show_d(draws(p, ymin=130, ymax=200, minw=1.0, minh=0.3), "ms p6 130-200 draws")

print("========== H. MS p7 bottom (y>=640) ==========")
p = ms[6]
show_w(words(p, ymin=640), "ms p7 y>=640")
show_d(draws(p, ymin=640, minw=1.0, minh=0.3), "ms p7 y>=640")

print("========== I. MS p8 bottom (y>=590) ==========")
p = ms[7]
show_w(words(p, ymin=590), "ms p8 y>=590")
show_d(draws(p, ymin=590, minw=1.0, minh=0.3), "ms p8 y>=590")
