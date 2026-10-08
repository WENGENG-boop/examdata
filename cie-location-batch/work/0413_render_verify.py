"""Render the 0413 repair-script NEW/CHANGED regions + QP footer fix for visual check.

Reads only local PDFs; writes probe PNGs under tmp/0413/2026-Jun-11/probe/.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pymupdf

TMP = Path(__file__).resolve().parents[1] / "tmp/0413/2026-Jun-11"
QP = TMP / "0413_s26_qp_11.pdf"
MS = TMP / "0413_s26_ms_11.pdf"
OUT = TMP / "probe"

# (label, role, page, bbox) — NEW/CHANGED regions from work/0413_repair_index.py MS dict
REGIONS = [
    ("p08 Q2 [58.4,66,342]", "ms", 8, [58.4, 66.0, 342.0, 729.2]),
    ("p08 Q2c [102,66,342]", "ms", 8, [102.0, 66.0, 342.0, 729.2]),
    ("p11 Q5 [337.2,65.2,554]", "ms", 11, [337.2, 65.2, 554.0, 729.2]),
    ("p11 Q5b [407.6,65.2,554]", "ms", 11, [407.6, 65.2, 554.0, 729.2]),
    ("p18 Q10 [95,84.8,166.5]", "ms", 18, [95.0, 84.8, 166.5, 735.2]),
    ("p18 Q11ai [200,84.8,318.5]", "ms", 18, [200.0, 84.8, 318.5, 735.2]),
    ("p18 Q11aii [318.5,84.8,476]", "ms", 18, [318.5, 84.8, 476.0, 735.2]),
    ("p19 Q11bi [96,68.8,250.5]", "ms", 19, [96.0, 68.8, 250.5, 729.2]),
    ("p19 Q11bii [250.5,68.8,309]", "ms", 19, [250.5, 68.8, 309.0, 729.2]),
    ("p21 Q12b [102,64.8,507.2]", "ms", 21, [102.0, 64.8, 507.2, 729.2]),
    ("p22 Q12ci [96,70,166.5]", "ms", 22, [96.0, 70.0, 166.5, 729.2]),
    ("p22 Q12cii [166.5,70,333]", "ms", 22, [166.5, 70.0, 333.0, 729.2]),
    ("p22 Q13 [333,70,517]", "ms", 22, [333.0, 70.0, 517.0, 729.2]),
    ("p24 Q14b [102,96.8,482.8]", "ms", 24, [102.0, 96.8, 482.8, 729.2]),
    ("p25 Q14c [96,121.2,238]", "ms", 25, [96.0, 121.2, 238.0, 729.2]),
]

GROUPS = {
    "verify-p08.png": [0, 1],
    "verify-p11.png": [2, 3],
    "verify-p18.png": [4, 5, 6],
    "verify-p19.png": [7, 8],
    "verify-p21.png": [9],
    "verify-p22.png": [10, 11, 12],
    "verify-p24.png": [13],
    "verify-p25.png": [14],
}

SCALE = 2.0
LABEL_H = 22
GAP = 10


def render(role, page_no, bbox, scale):
    doc = pymupdf.open(QP if role == "qp" else MS)
    page = doc[page_no - 1]
    visible = pymupdf.Rect(bbox) * page.rotation_matrix
    pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), clip=visible, alpha=False)
    data = pix.tobytes("png")
    doc.close()
    return data, pix.width, pix.height


def montage(items, out_path, scale):
    """items: list of (label, role, page, bbox)."""
    pixmaps = []
    for label, role, page_no, bbox in items:
        data, w, h = render(role, page_no, bbox, scale)
        pixmaps.append((label, data, w, h))
    total_h = sum(h + LABEL_H + GAP for _, _, w, h in pixmaps) + GAP
    total_w = max(w for _, _, w, _ in pixmaps) + 20
    out = pymupdf.open()
    pg = out.new_page(width=total_w, height=total_h)
    y = GAP
    for label, data, w, h in pixmaps:
        pg.insert_text((10, y + 14), label, fontsize=13)
        y += LABEL_H
        pg.insert_image(pymupdf.Rect(10, y, 10 + w, y + h), stream=data)
        y += h + GAP
    pg.get_pixmap(matrix=pymupdf.Matrix(1, 1), alpha=False).save(str(out_path))
    out.close()
    print("saved", out_path, total_w, "x", total_h)


def main():
    for out_name, idxs in GROUPS.items():
        montage([REGIONS[i] for i in idxs], OUT / out_name, SCALE)

    # QP footer fix verification: old x0=92.4 vs new x0=70.4 bottom bands + full fixed region
    qp = pymupdf.open(QP)
    for pno in (7, 9):
        page = qp[pno - 1]
        for tag, x0 in (("old", 92.4), ("new", 70.4)):
            clip = pymupdf.Rect(x0, 700, 570, 760)
            pix = page.get_pixmap(matrix=pymupdf.Matrix(2.6, 2.6), clip=clip, alpha=False)
            pix.save(str(OUT / f"qp-p{pno:02d}-footer-{tag}.png"))
        clip = pymupdf.Rect(70.4, 58.8, 541.2, 748.4)
        pix = page.get_pixmap(matrix=pymupdf.Matrix(1.1, 1.1), clip=clip, alpha=False)
        pix.save(str(OUT / f"qp-p{pno:02d}-fixed-full.png"))
        print("qp p", pno, "footer crops + full done")
    qp.close()

    # side-by-side compare montage for footer old/new on both pages
    for pno in (7, 9):
        items = []
        for tag in ("old", "new"):
            path = OUT / f"qp-p{pno:02d}-footer-{tag}.png"
            img = pymupdf.open(str(path))
            rect = img[0].rect
            items.append((f"p{pno} footer x0={92.4 if tag == 'old' else 70.4}", rect))
        # simple stacked compare using PIL not needed: just note files exist
        print("compare files ready for p", pno)


if __name__ == "__main__":
    main()
