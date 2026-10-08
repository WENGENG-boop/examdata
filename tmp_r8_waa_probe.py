"""Probe WAA (Arabic) paper numbering: find digits and their positions. Read-only."""
from __future__ import annotations
import sqlite3, sys, re
from pathlib import Path
import pymupdf
ROOT = Path(__file__).resolve().parent
con = sqlite3.connect(ROOT/".data/examdata.db"); cur = con.cursor()
doc_id = int(sys.argv[1]) if len(sys.argv)>1 else 1778
row = cur.execute("""SELECT a.storage_key FROM document d
    JOIN document_revision r ON r.id=d.current_revision_id
    JOIN artifact a ON a.id=r.artifact_id WHERE d.id=?""",(doc_id,)).fetchone()
doc = pymupdf.open(ROOT/".data/artifacts"/row[0])
AR = "".join(chr(0x660+i) for i in range(10))
pat = re.compile(r"^[%s\d]{1,3}[.\u066B]?$" % AR)
for pg in range(1, min(len(doc), 12)):
    page = doc[pg]
    b = page.rect * page.derotation_matrix
    words = page.get_text("words")
    hits = [w for w in words if pat.match(w[4].strip())]
    print(f"--- page {pg+1} ({b.width:.0f}x{b.height:.0f}) digits={len(hits)}")
    for w in hits[:14]:
        print(f"    x={w[0]:6.1f} y={w[1]:6.1f} {w[4]!r}")
