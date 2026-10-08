"""判定 parse_omission：
1) 8386/2024/Nov/11 ms p5：用 get_drawings() 找表格分隔线，定 1(a) 行的 x 边界。
2) 9489/2026/Jun/11 ms p8/p9：dump 文本行，判定 '1(b)' 命中是否为页眉/表头误匹配。
"""
from __future__ import annotations

from pathlib import Path

import pymupdf

TMP = Path("C:/Users/weo/Desktop/api/cie-location-batch/tmp")


def pdf_for(key: str, role: str) -> Path:
    subject, year, season, paper = key.split("/")
    d = TMP / subject / f"{year}-{season}-{paper}"
    hits = sorted(d.glob(f"*_{role}_*.pdf")) or sorted(d.glob(f"*{role}*.pdf"))
    if not hits:
        raise SystemExit(f"no {role} pdf in {d}")
    return hits[0]


def lines(page):
    out = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            text = "".join(s["text"] for s in line.get("spans", []))
            if text.strip():
                out.append((line["bbox"], text.strip()))
    return out


def dump_page(key, role, pno, tag):
    doc = pymupdf.open(pdf_for(key, role))
    page = doc[pno - 1]
    print(f"### {key} {role} p{pno} rot={page.rotation} "
          f"mediabox={page.mediabox.width}x{page.mediabox.height} "
          f"textlen={len(page.get_text('text'))} {tag}")
    rows = lines(page)
    rows.sort(key=lambda r: (round(r[0][0], 1), round(r[0][1], 1)))
    for bbox, text in rows:
        print(f"   un[{bbox[0]:7.1f},{bbox[1]:7.1f},{bbox[2]:7.1f},{bbox[3]:7.1f}] "
              f"dispX[{792-bbox[3]:7.1f},{792-bbox[1]:7.1f}] dispY[{bbox[0]:7.1f},{bbox[2]:7.1f}] "
              f"{text[:80]!r}")
    doc.close()


def drawings_x(key, role, pno, xlo, xhi):
    """列出该页中位于 x∈[xlo,xhi] 的横向分隔线（未旋转坐标下：y 恒定的线段）。"""
    doc = pymupdf.open(pdf_for(key, role))
    page = doc[pno - 1]
    print(f"### drawings {key} {role} p{pno} rot={page.rotation}  x∈[{xlo},{xhi}]")
    for d in page.get_drawings():
        for item in d["items"]:
            if item[0] == "l":
                p1, p2 = item[1], item[2]
                if abs(p1.x - p2.x) < 0.5 and xlo <= p1.x <= xhi and abs(p1.y - p2.y) > 50:
                    print(f"   竖线 x={p1.x:.2f} y[{min(p1.y,p2.y):.1f},{max(p1.y,p2.y):.1f}] "
                          f"w={d.get('width')}")
            elif item[0] == "re":
                r = item[1]
                if xlo <= r.x0 <= xhi and r.width < 3 and r.height > 50:
                    print(f"   矩形竖条 x[{r.x0:.2f},{r.x1:.2f}] y[{r.y0:.1f},{r.y1:.1f}]")
    doc.close()


if __name__ == "__main__":
    drawings_x("8386/2024/Nov/11", "ms", 5, 95, 260)
    dump_page("9489/2026/Jun/11", "ms", 8, "(1(b) 命中页)")
    dump_page("9489/2026/Jun/11", "ms", 9, "(1(b) 命中页)")
