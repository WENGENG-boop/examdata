#!/usr/bin/env python
"""G14b: match hash PDFs against downloads books by sha256; title-scan unmatched ones."""
import hashlib
import json
import re
from pathlib import Path

import fitz

ROOT = Path("C:/Users/weo/Desktop/api")
DL = ROOT / "tmp_audit_ielts/downloads"
HASH_DIR = ROOT / "ielts-data/pdf"
OUT = ROOT / "ielts-data/runs/20261003T140007Z-repair/scratch/s18/g14b-hash-match.txt"
lines = []


def sha(p: Path, buf=1 << 20):
    h = hashlib.sha256()
    with p.open("rb") as f:
        while True:
            b = f.read(buf)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


# sha of downloads books
dl_map = {}
for b in range(1, 21):
    p = DL / f"book_{b}.pdf"
    if p.exists():
        h = sha(p)
        dl_map[h] = f"downloads/book_{b}.pdf"
        lines.append(f"DL book_{b}: {h}")

# extra copies
for extra in ["book_9_22193053_b25f954dd25e058dfc05913c8f3b9ffead6581aa23bb10f8f2e98e6314f7af24_h.pdf"]:
    p = DL / extra
    if p.exists():
        lines.append(f"DL extra {extra}: {sha(p)}")

for i in (1, 2, 3, 4):
    p = ROOT / f"ielts-data/raw/pdf-source/book20-test{i}.pdf"
    lines.append(f"src book20-test{i}: {sha(p)}")

for name in ("fresh_b1.pdf", "fresh_b20.pdf"):
    p = ROOT / "tmp_audit_ielts" / name
    if p.exists():
        lines.append(f"fresh {name}: {sha(p)}")

lines.append("")
# match hash pdfs
for f in sorted(HASH_DIR.glob("*.pdf")):
    h = f.name[:64]
    match = dl_map.get(h, "")
    # title scan: pages 1-6, look for IELTS number
    d = fitz.open(f)
    title = ""
    for i in range(min(6, len(d))):
        t = d[i].get_text()
        m = re.search(r"IELTS\s*[^0-9]{0,20}(\d{1,2})", t, re.I)
        if m:
            title = f"p{i+1}: IELTS {m.group(1)}"
            break
    if not title:
        t0 = d[0].get_text().replace("\n", " ")[:70]
        title = f"p1: {t0}"
    lines.append(f"HASH {f.name[:20]} pages={len(d)} match={match or 'NONE'} | {title}")
    d.close()

OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
print(f"\nwrote {OUT}")
