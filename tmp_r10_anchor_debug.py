"""r10 debug: list anchors found by _anchors for a given doc's QP, with page/y,
plus the raw words near each anchor to explain spurious ones. Read-only.

Usage: ./.venv/Scripts/python.exe -X utf8 tmp_r10_anchor_debug.py <doc_id>
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import pymupdf  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from examdata.core import models as m  # noqa: E402
from examdata.paperqa import locator as L  # noqa: E402


def main() -> None:
    doc_id = int(sys.argv[1])
    eng = create_engine(f"sqlite:///{ROOT / '.data' / 'examdata.db'}")
    s = Session(eng)
    d = s.get(m.Document, doc_id)
    rev = s.get(m.DocumentRevision, d.current_revision_id)
    art = s.get(m.Artifact, rev.artifact_id)
    path = ROOT / ".data/artifacts" / art.storage_key
    pdf = pymupdf.open(path)
    ciphered = L.is_ciphered(pdf)
    anchors, end = L._anchors(pdf, "qp", ciphered=ciphered)
    print(f"doc {doc_id} {d.title[:70]!r} pages={len(pdf)} ciphered={ciphered} end={end}")
    for a in anchors:
        page = pdf[a.page]
        bounds = L._page_bounds(page)
        words = sorted(L._page_words(page, ciphered), key=lambda w: (round(w[1] / 3), w[0]))
        # find the exact word at this anchor position
        near = [w for w in words if abs(w[1] - a.y) < 2 and w[0] < bounds.width * .2]
        ctx = " | ".join(w[4] for w in near[:6])
        print(f"  [{a.path:12s}] p{a.page+1:3d} y={a.y:7.1f}  ctx: {ctx[:90]}")
    pdf.close()
    s.close()


if __name__ == "__main__":
    main()
