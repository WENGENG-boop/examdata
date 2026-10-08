"""Check whether doc 1719 pages are image-based; count images/drawings/text. Read-only."""
from __future__ import annotations
import sqlite3, sys
from pathlib import Path
import pymupdf
ROOT = Path(__file__).resolve().parent
con = sqlite3.connect(ROOT/".data/examdata.db"); cur = con.cursor()
doc_id = int(sys.argv[1]) if len(sys.argv)>1 else 1719
row = cur.execute("""SELECT a.storage_key FROM document d
    JOIN document_revision r ON r.id=d.current_revision_id
    JOIN artifact a ON a.id=r.artifact_id WHERE d.id=?""",(doc_id,)).fetchone()
pdf = pymupdf.open(ROOT/".data/artifacts"/row[0])
for i in range(len(pdf)):
    page = pdf[i]
    imgs = page.get_images(full=True)
    txt = page.get_text()
    print(f"page {i+1:3d}: words={len(txt.split()):4d} chars={len(txt):6d} images={len(imgs)} drawings={len(page.get_drawings())}")
