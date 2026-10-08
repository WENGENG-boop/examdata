"""Structural dump of doc 1719 page 3 rawdict: blocks/spans/bboxes. Read-only."""
from __future__ import annotations
import sqlite3, sys
from pathlib import Path
import pymupdf
ROOT = Path(__file__).resolve().parent
con = sqlite3.connect(ROOT/".data/examdata.db"); cur = con.cursor()
doc_id = int(sys.argv[1]) if len(sys.argv)>1 else 1719
pg = int(sys.argv[2])-1 if len(sys.argv)>2 else 2
row = cur.execute("""SELECT a.storage_key FROM document d
    JOIN document_revision r ON r.id=d.current_revision_id
    JOIN artifact a ON a.id=r.artifact_id WHERE d.id=?""",(doc_id,)).fetchone()
doc = pymupdf.open(ROOT/".data/artifacts"/row[0])
page = doc[pg]
d = page.get_text("rawdict")
print("blocks:", len(d["blocks"]))
for bi, b in enumerate(d["blocks"]):
    if b["type"] != 0:
        print(f"  block {bi}: type={b['type']} bbox={b['bbox']}")
        continue
    print(f"  block {bi}: type=0 bbox={tuple(round(v,1) for v in b['bbox'])} lines={len(b['lines'])}")
    for li, line in enumerate(b["lines"][:6]):
        txt = "".join(ch["c"] for sp in line["spans"] for ch in sp["chars"])
        fonts = {sp["font"] for sp in line["spans"]}
        print(f"    line {li}: bbox={tuple(round(v,1) for v in line['bbox'])} nchars={len(txt)} fonts={fonts}")
        print(f"       text[:120]={txt[:120]!r}")
print()
print("drawings sample:")
for dr in page.get_drawings()[:12]:
    print(f"  type={dr['type']} rect={tuple(round(v,1) for v in dr['rect'])} items={len(dr['items'])} fill={dr.get('fill')} color={dr.get('color')}")
