"""一次性探针：核对 MS 页的行分隔线到底是哪几条。

不参与交付，只用于确认 propose.py 的行带规则。
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

sys.path.insert(0, "C:/Users/weo/Desktop/api/cie-location-batch/tools")

import paperlib as P

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

MS = Path("C:/Users/weo/Desktop/api/cie-location-batch/tmp/9709/2024-Jun-11/9709_s24_ms_11.pdf")
REF = Path("C:/Users/weo/Desktop/api/cie-index-batch-2026-10-01/9709/2024-Jun-11/cie-index.json")


def main() -> None:
    import pymupdf
    ref = json.loads(REF.read_bytes().decode("utf-8"))
    with pymupdf.open(MS) as pdf:
        for page_no in (6, 7):
            page = pdf[page_no - 1]
            bounds = P.analysis_bounds(page)
            print(f"=== MS page {page_no} bounds={[round(v,1) for v in bounds]} "
                  f"rotation={page.rotation} rect={page.rect}")
            rules = []
            for d in page.get_drawings():
                r = d["rect"]
                if (r.x1 - r.x0) < 2.5:
                    rules.append((round((r.x0 + r.x1) / 2, 1), round(r.y0, 1),
                                  round(r.y1, 1), round(r.y1 - r.y0, 1)))
            rules.sort()
            print(f"  细竖线 {len(rules)} 条 (x, y0, y1, 长度):")
            for x, y0, y1, ln in rules:
                print(f"    x={x:7.1f}  y=[{y0:6.1f},{y1:6.1f}]  len={ln:6.1f}")
            print("  参考区域:")
            for q in ref["questions"]:
                for reg in q.get("ms") or []:
                    if reg["page"] == page_no:
                        print(f"    {q['question']:8s} {reg['bbox']}")
            print("  文字行 (x0, y0, x1, y1, text):")
            for line in P.page_lines(MS, page_no):
                if line["y0"] < 660:
                    continue
                print(f"    x0={line['x0']:7.1f} y0={line['y0']:6.1f} "
                      f"x1={line['x1']:7.1f} y1={line['y1']:6.1f}  {line['text'][:60]!r}")


if __name__ == "__main__":
    main()
