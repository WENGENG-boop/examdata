"""一次性探针：QP 续页顶部的碎片行是什么；参考索引的区域长什么样。"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

sys.path.insert(0, "C:/Users/weo/Desktop/api/cie-location-batch/tools")

import paperlib as P
import propose as PR

if (getattr(sys.stdout, "encoding", "") or "").replace("-", "").lower() != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

QP = Path("C:/Users/weo/Desktop/api/cie-location-batch/tmp/9709/2024-Jun-11/9709_s24_qp_11.pdf")
REF = Path("C:/Users/weo/Desktop/api/cie-index-batch-2026-10-01/9709/2024-Jun-11/cie-index.json")


def main() -> None:
    ref = json.loads(REF.read_bytes().decode("utf-8"))
    print("=== 参考 qp 区域 ===")
    for q in ref["questions"]:
        print(f"  {q['question']:8s} {q['qp']}")
    print("=== 参考 ms 区域 ===")
    for q in ref["questions"]:
        print(f"  {q['question']:8s} {q.get('ms')}")
    doc = PR.read_doc(QP)
    for page_no in (4, 6, 14, 20):
        page = doc["pages"][page_no - 1]
        print(f"=== QP page {page_no} 前 8 行（按 y0 排序）===")
        for line in sorted(page["lines"], key=lambda l: (round(l["y0"], 1), l["x0"]))[:8]:
            keep = "" if not PR.is_decorative(line, page["bounds"]) else "  [装饰]"
            print(f"    y0={line['y0']:6.1f} y1={line['y1']:6.1f} x0={line['x0']:7.1f} "
                  f"x1={line['x1']:7.1f}  {line['text'][:70]!r}{keep}")
        print(f"--- page {page_no} 末尾 4 行 ---")
        for line in sorted(page["lines"], key=lambda l: (round(l["y0"], 1), l["x0"]))[-4:]:
            keep = "" if not PR.is_decorative(line, page["bounds"]) else "  [装饰]"
            print(f"    y0={line['y0']:6.1f} y1={line['y1']:6.1f} x0={line['x0']:7.1f} "
                  f"x1={line['x1']:7.1f}  {line['text'][:70]!r}{keep}")


if __name__ == "__main__":
    main()
