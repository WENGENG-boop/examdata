"""一次性探针：MS 第 7 页 Question 列到底有没有行标签。"""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.path.insert(0, "C:/Users/weo/Desktop/api/cie-location-batch/tools")

import paperlib as P

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

MS = Path("C:/Users/weo/Desktop/api/cie-location-batch/tmp/9709/2024-Jun-11/9709_s24_ms_11.pdf")


def main() -> None:
    for page_no in (6, 7):
        print(f"=== MS page {page_no} lines with y0 >= 600 ===")
        for line in P.page_lines(MS, page_no):
            if line["y0"] < 600:
                continue
            print(f"    y0={line['y0']:6.1f} y1={line['y1']:6.1f} "
                  f"x0={line['x0']:7.1f} x1={line['x1']:7.1f} blk={line['block']:3d} "
                  f"ln={line['line']:3d}  {line['text'][:70]!r}")
        print(f"=== MS page {page_no} words with y0 >= 675 ===")
        for w in P.page_words(MS, page_no):
            if w["y0"] < 675:
                continue
            print(f"    y0={w['y0']:6.1f} y1={w['y1']:6.1f} x0={w['x0']:7.1f} "
                  f"x1={w['x1']:7.1f}  {w['text']!r}")


if __name__ == "__main__":
    main()
