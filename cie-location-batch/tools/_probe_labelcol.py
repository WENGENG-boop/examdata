"""探针：把题号列单独裁成窄条再 OCR，看能否救回整页 OCR 漏掉的标签。

用法：_probe_labelcol.py <key> <role> <page> [x_lo x_hi] [--zoom 6]
只读本地 PDF，不联网。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import batchlib as B
import pymupdf
import ocr_index as O
import paperlib as P

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("key")
    ap.add_argument("role")
    ap.add_argument("page", type=int)
    ap.add_argument("x", nargs="*", type=float, default=[])
    ap.add_argument("--zoom", type=float, default=6.0)
    args = ap.parse_args()

    subject, year, season, paper = args.key.split("/")
    tmp = B.paper_dir(subject, int(year), season, paper)
    pdfs = sorted(tmp.glob(f"{subject}_*_{args.role}_*.pdf"))
    if not pdfs:
        print(f"找不到 {args.role} 原件：{tmp}")
        return 2
    doc = pymupdf.open(pdfs[0])
    page = doc[args.page - 1]
    bx0, by0, bx1, by1 = P.analysis_bounds(page)
    x_lo = args.x[0] if len(args.x) > 0 else 55.0
    x_hi = args.x[1] if len(args.x) > 1 else 92.0
    clip = pymupdf.Rect(x_lo, by0, x_hi, by1) * page.rotation_matrix
    pix = page.get_pixmap(matrix=pymupdf.Matrix(args.zoom, args.zoom), clip=clip)
    out = tmp / f"_probe_lc_{args.role}_{args.page}.png"
    pix.save(out)
    print(f"strip {x_lo}..{x_hi} -> {out} ({pix.width}x{pix.height})")

    rows = O.run_ocr([out], tmp)
    lines, errors = O.page_lines(rows.get(str(out), []), args.zoom)
    print(f"rows={len(rows.get(str(out), []))} lines={len(lines)} errors={errors}")
    for line in lines:
        print(f"  y0={line['y0'] + by0:7.1f} y1={line['y1'] + by0:7.1f} "
              f"x0={line['x0'] + x_lo:6.1f} {line['text']!r}")
    doc.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
