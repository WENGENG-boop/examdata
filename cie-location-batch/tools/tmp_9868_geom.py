"""临时脚本：dump 9868 QP 指定页的文字 span 几何（origin 可靠）。"""
from __future__ import annotations

import sys
from pathlib import Path

import pymupdf

PDF = Path("C:/Users/weo/Desktop/api/cie-location-batch/tmp/9868/2026-Jun-12/9868_s26_qp_12.pdf")


def main() -> int:
    pages = [int(a) for a in sys.argv[1:]] or [2, 3, 4]
    with pymupdf.open(PDF) as doc:
        for pno in pages:
            page = doc[pno - 1]
            print(f"===== page {pno} rect={page.rect} rot={page.rotation}")
            spans = []
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    for sp in line.get("spans", []):
                        t = sp["text"].strip()
                        if not t:
                            continue
                        spans.append((round(sp["origin"][1], 1), round(sp["origin"][0], 1),
                                      round(sp["size"], 1), t))
            spans.sort()
            for y, x, size, t in spans:
                print(f"  y={y:7.1f} x={x:7.1f} sz={size:4.1f} | {t[:60]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
