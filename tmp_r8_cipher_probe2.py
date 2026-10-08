"""Dump raw char codes of doc 1719 page 1-3 to identify cipher mapping. Read-only."""
from __future__ import annotations
import sqlite3, sys
from pathlib import Path
import pymupdf
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from examdata.paperqa import locator as L
ROOT = Path(__file__).resolve().parent
con = sqlite3.connect(ROOT/".data/examdata.db"); cur = con.cursor()
doc_id = int(sys.argv[1]) if len(sys.argv)>1 else 1719
row = cur.execute("""SELECT a.storage_key FROM document d
    JOIN document_revision r ON r.id=d.current_revision_id
    JOIN artifact a ON a.id=r.artifact_id WHERE d.id=?""",(doc_id,)).fetchone()
pdf = pymupdf.open(ROOT/".data/artifacts"/row[0])
for index in (0,1):
    page = pdf[index]
    txt = page.get_text()
    print(f"===== page {index+1} raw text (first 600 chars) =====")
    print(repr(txt[:600]))
    # span font info
    d = page.get_text("dict")
    for b in d["blocks"][:3]:
        if b["type"]!=0: continue
        for line in b["lines"][:2]:
            for span in line["spans"][:3]:
                print(f"  font={span['font']!r} size={span['size']:.1f} text={span['text'][:60]!r} codes={[hex(ord(c)) for c in span['text'][:20]]}")
    print()
