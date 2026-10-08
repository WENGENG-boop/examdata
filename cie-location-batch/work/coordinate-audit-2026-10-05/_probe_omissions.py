"""逐行 dump 指定 MS 页的文本层（未旋转坐标），用于判定 parse_omission 是否真实缺题。"""
from __future__ import annotations

import sys
from pathlib import Path

import fitz

TARGETS = [
    ("8386/2024/Nov/11", "ms", [5], "1(a)"),
    ("8386/2024/Nov/13", "ms", [5], "1(a)"),
    ("9489/2026/Jun/11", "ms", [8, 9], "1(b)"),
]
TMP = Path("C:/Users/weo/Desktop/api/cie-location-batch/tmp")


def pdf_for(key: str, role: str) -> Path:
    subject, year, season, paper = key.split("/")
    d = TMP / subject / f"{year}-{season}-{paper}"
    hits = sorted(d.glob(f"*_{role}_*.pdf")) or sorted(d.glob(f"*{role}*.pdf"))
    if not hits:
        raise SystemExit(f"no {role} pdf in {d}")
    return hits[0]


def main() -> int:
    for key, role, pages, label in TARGETS:
        path = pdf_for(key, role)
        doc = fitz.open(path)
        print("=" * 90)
        print(f"{key} {role} {path.name} pages={doc.page_count}")
        for pno in pages:
            page = doc[pno - 1]
            rot = page.rotation
            mb = page.mediabox
            print(f"--- page {pno} rotation={rot} mediabox={mb.width}x{mb.height} "
                  f"textlen={len(page.get_text('text'))}")
            lines = []
            for block in page.get_text("dict")["blocks"]:
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    text = "".join(span["text"] for span in line.get("spans", []))
                    if not text.strip():
                        continue
                    x0, y0, x1, y1 = line["bbox"]
                    if rot == 90:
                        disp = (round(mb.width - y1, 1), round(x0, 1),
                                round(mb.width - y0, 1), round(x1, 1))
                    else:
                        disp = (round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1))
                    lines.append((x0, y0, x1, y1, disp, text))
            # 按显示坐标从上到下、从左到右排序
            lines.sort(key=lambda r: (round(r[4][1], 1), round(r[4][0], 1)))
            print(f"    [{'disp_x0':>8} {'disp_y0':>8} {'disp_x1':>8} {'disp_y1':>8}]"
                  f"  [{'un_x0':>8} {'un_y0':>8} {'un_x1':>8} {'un_y1':>8}]  text")
            for x0, y0, x1, y1, disp, text in lines:
                mark = "  <<<" if text.strip() == label else ""
                print(f"    [{disp[0]:>8} {disp[1]:>8} {disp[2]:>8} {disp[3]:>8}]"
                      f"  [{round(x0,1):>8} {round(y0,1):>8} {round(x1,1):>8} {round(y1,1):>8}]"
                      f"  {text.strip()[:90]!r}{mark}")
        doc.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
