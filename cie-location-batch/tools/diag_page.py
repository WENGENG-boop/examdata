"""诊断：渲染整页并打印 OCR 行（显示态坐标），用于核对题号位置。

用法: diag_page.py <key> <role> <page> [--zoom 2.5] [--top 40]
"""
from __future__ import annotations

import argparse
import io
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

import batchlib as B  # noqa: E402
import paperlib as P  # noqa: E402
import verify_ocr as V  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("key")
    ap.add_argument("role")
    ap.add_argument("page", type=int)
    ap.add_argument("--zoom", type=float, default=V.PAGE_ZOOM)
    ap.add_argument("--top", type=int, default=40)
    args = ap.parse_args()

    tmp = P.paper_tmp(args.key)
    cands = sorted(tmp.glob(f"*_{args.role}_*.pdf"))
    if not cands:
        print(f"找不到 {args.role} PDF in {tmp}")
        return 2
    pdf = cands[0]

    import pymupdf
    with pymupdf.open(pdf) as doc:
        page = doc[args.page - 1]
        info = (f"PDF={pdf.name} page={args.page} rot={page.rotation} "
                f"rect={page.rect} derot={page.derotation_matrix}")
    print(info)

    out = tmp / "pages" / f"diag-{args.role}-p{args.page:03d}-z{args.zoom:g}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    P.render_page(pdf, args.page, out, zoom=args.zoom)
    ocr = V.run_ocr([out], tmp)
    rows = ocr.get(str(out), [])
    print(f"rows={len(rows)}")
    shown = 0
    for row in rows:
        if "text" not in row:
            print("  ", row)
            continue
        y0 = row["y0"] / args.zoom
        x0 = row["x0"] / args.zoom
        print(f"  y0={y0:7.1f} x0={x0:7.1f} {row['text'][:78]!r}")
        shown += 1
        if shown >= args.top:
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
