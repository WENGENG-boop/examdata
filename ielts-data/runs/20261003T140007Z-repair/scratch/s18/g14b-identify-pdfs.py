#!/usr/bin/env python
"""G14b: identify all local PDF copies (hash PDFs, no-text-layer books, fresh downloads)."""
import hashlib
import sys
from pathlib import Path

import fitz

ROOT = Path("C:/Users/weo/Desktop/api")
OUT = ROOT / "ielts-data/runs/20261003T140007Z-repair/scratch/s18/g14b-pdf-identify.txt"
lines = []


def stats(p: Path, label: str):
    try:
        d = fitz.open(p)
    except Exception as e:
        lines.append(f"{label}\t{p.name}\tOPEN-FAIL {e}")
        return
    n = len(d)
    tot = 0
    first_text = ""
    for i, pg in enumerate(d):
        t = pg.get_text().strip()
        tot += len(t)
        if i == 0 and t:
            first_text = t.replace("\n", " ")[:100]
    sz = p.stat().st_size
    lines.append(f"{label}\t{p.name}\tpages={n}\tsize={sz}\ttext_chars={tot}\tfirst={first_text}")
    d.close()


# 1) hash-named PDFs
for f in sorted((ROOT / "ielts-data/pdf").glob("*.pdf")):
    stats(f, "hash-pdf")

# 2) no-text-layer books in downloads
for b in (9, 16, 18, 19, 20):
    p = ROOT / "tmp_audit_ielts/downloads" / f"book_{b}.pdf"
    if p.exists():
        stats(p, f"dl-book{b}")

# 3) raw pdf-source book20 tests
for i in (1, 2, 3, 4):
    p = ROOT / "ielts-data/raw/pdf-source" / f"book20-test{i}.pdf"
    if p.exists():
        stats(p, f"src-b20t{i}")

# 4) fresh downloads
for name in ("fresh_b1.pdf", "fresh_b20.pdf"):
    p = ROOT / "tmp_audit_ielts" / name
    if p.exists():
        stats(p, "fresh")

# 5) derived/pdf
dd = ROOT / "ielts-data/derived/pdf"
if dd.exists():
    for f in sorted(dd.glob("*.pdf")):
        stats(f, "derived")

OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
print(f"\nwrote {OUT}")
