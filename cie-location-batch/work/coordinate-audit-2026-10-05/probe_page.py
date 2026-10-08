"""只读探针：打印某卷某 role 某页的全部文字行（显示坐标）与索引区域（索引坐标 + 显示坐标）。

用法:
  probe_page.py <key> <role> <page> [--cols]
例:
  probe_page.py 8386/2024/Nov/11 ms 5
"""
import json
import os
import sys

import pymupdf

A = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, A)
from ms_row_audit import pdf_for, index_path, to_display, text_rows  # noqa: E402


def main():
    key, role, page = sys.argv[1], sys.argv[2], sys.argv[3]
    pgno = int(page)
    pdf = pdf_for(key, role)
    print("pdf:", pdf)
    doc = pymupdf.open(pdf)
    pg = doc[pgno - 1]
    rot, w, h = pg.rotation, pg.mediabox.width, pg.mediabox.height
    print(f"page {pgno}: rotation={rot} mediabox={w}x{h}")

    idx = json.loads(index_path(key).read_text(encoding="utf-8"))
    print("--- index regions on this page ---")
    for q in idx["questions"]:
        for r in (q.get("qp") or []):
            if r["page"] == pgno:
                print(f"  qp {q['question']:12s} idx={r['bbox']} disp={tuple(round(v,1) for v in to_display(r['bbox'], rot, w, h))}")
        for r in (q.get("ms") or []):
            if r["page"] == pgno:
                print(f"  ms {q['question']:12s} idx={r['bbox']} disp={tuple(round(v,1) for v in to_display(r['bbox'], rot, w, h))}")

    print("--- text lines (display coords) ---")
    rows = []
    for bb, t in text_rows(pg):
        d = to_display(bb, rot, w, h)
        rows.append((round(d[1], 1), round(d[0], 1), round(d[2], 1), round(d[3], 1), t))
    rows.sort()
    for y0, x0, x1, y1, t in rows:
        print(f"  y={y0:7.1f} x=[{x0:7.1f},{x1:7.1f}] dy={y1-y0:5.1f}  {t[:110]}")


if __name__ == "__main__":
    main()
