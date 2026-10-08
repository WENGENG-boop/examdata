#!/usr/bin/env python
"""G14b: page-layout map for books with text layers to learn standard Cambridge layout."""
import re
import sys
from pathlib import Path

import fitz

ROOT = Path("C:/Users/weo/Desktop/api")
DL = ROOT / "tmp_audit_ielts/downloads"
OUT = ROOT / "ielts-data/runs/20261003T140007Z-repair/scratch/s18/g14b-layout-map.txt"
lines = []

for b in (11, 1, 17):
    p = DL / f"book_{b}.pdf"
    d = fitz.open(p)
    lines.append(f"########## book_{b} pages={len(d)} ##########")
    for i, pg in enumerate(d):
        t = pg.get_text().strip()
        first = ""
        for ln in t.split("\n"):
            ln = ln.strip()
            if len(ln) >= 3:
                first = ln[:70]
                break
        flags = []
        tl = t.lower()
        if "listening" in tl:
            flags.append("L")
        if "reading" in tl:
            flags.append("R")
        if "writing" in tl:
            flags.append("W")
        if "answer key" in tl or "answer keys" in tl:
            flags.append("K")
        lines.append(f"p{i+1}\t{''.join(flags):4s}\t{first}")
    d.close()
    lines.append("")

OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines[:1]))
print(f"wrote {OUT} ({len(lines)} lines)")
