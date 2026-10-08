"""Render a probe image: full page + overlay boxes (display space) for a region.

Usage:
  python probe_region.py <key> <role> <page> <out.png> '<json boxes>'

boxes = [{"bbox":[x0,y0,x1,y1],"color":[r,g,b],"label":"current"}, ...]
Coordinates are unrotated PDF points; drawn after multiplying by rotation_matrix.
No network. Requires venv python (pymupdf).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import paperlib as P
import pymupdf

ZOOM = 1.3


def main() -> int:
    key, role, page_no, out_png, boxes_json = sys.argv[1:6]
    boxes = json.loads(boxes_json)
    tmp = P.paper_tmp(key)
    entry = P.load_paper(key)
    docs = entry.get(role) or []
    name = docs[0] if isinstance(docs[0], str) else docs[0]["filename"]
    pdf = tmp / name
    doc = pymupdf.open(pdf)
    page = doc[int(page_no) - 1]
    out = pymupdf.open()
    op = out.new_page(width=page.rect.width * ZOOM, height=page.rect.height * ZOOM)
    op.show_pdf_page(op.rect, doc, page.number)
    for b in boxes:
        r = pymupdf.Rect(b["bbox"]) * page.rotation_matrix
        r = pymupdf.Rect(r.x0 * ZOOM, r.y0 * ZOOM, r.x1 * ZOOM, r.y1 * ZOOM)
        color = tuple(c / 255.0 for c in b.get("color", [255, 0, 0]))
        op.draw_rect(r, color=color, width=2)
        if b.get("label"):
            op.insert_text((r.x0 + 3, max(12, r.y0 - 4)), b["label"],
                           fontsize=11, color=color)
    outp = Path(out_png)
    outp.parent.mkdir(parents=True, exist_ok=True)
    op.get_pixmap(matrix=pymupdf.Matrix(1, 1), alpha=False).save(outp)
    doc.close()
    out.close()
    print(f"saved {outp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
