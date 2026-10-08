"""只读探针：列出某卷 MS 各页的「题号行」与表头行（显示坐标），用于判定区域归属。

用法: probe_rows.py <key> <role> <page> [<page> ...]
"""
import json
import os
import sys

import pymupdf

A = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, A)
from ms_row_audit import pdf_for, index_path, to_display, text_rows  # noqa: E402

LABELCOL = 118.0


def main():
    key, role = sys.argv[1], sys.argv[2]
    pages = [int(p) for p in sys.argv[3:]]
    pdf = pdf_for(key, role)
    doc = pymupdf.open(pdf)
    idx = json.loads(index_path(key).read_text(encoding="utf-8"))
    for pgno in pages:
        pg = doc[pgno - 1]
        rot, w, h = pg.rotation, pg.mediabox.width, pg.mediabox.height
        print(f"=== {key} {role} p{pgno} rot={rot} {w}x{h} ===")
        regs = []
        for q in idx["questions"]:
            for r in (q.get("qp") if role == "qp" else q.get("ms")) or []:
                if r["page"] == pgno:
                    regs.append((q["question"], r["bbox"], to_display(r["bbox"], rot, w, h)))
        for q, ib, d in sorted(regs, key=lambda t: t[2][1]):
            print(f"  REG {q:12s} idx={ib} disp=({d[0]:.1f},{d[1]:.1f},{d[2]:.1f},{d[3]:.1f})")
        lines = []
        for bb, t in text_rows(pg):
            d = to_display(bb, rot, w, h)
            lines.append((d[1], d[0], d[2], d[3], t))
        lines.sort()
        for y0, x0, x1, y1, t in lines:
            if x0 < LABELCOL:
                kind = "LABEL"
            elif t in ("Question", "Answer", "Marks"):
                kind = "HDR"
            else:
                continue
            print(f"  {kind:5s} y={y0:7.1f} x=[{x0:7.1f},{x1:7.1f}]  {t[:80]}")


if __name__ == "__main__":
    main()
