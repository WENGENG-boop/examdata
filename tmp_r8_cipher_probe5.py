"""Dump raw text of doc 1719 page 3 (full) + char code histogram. Read-only."""
from __future__ import annotations
import sqlite3, sys, collections
from pathlib import Path
import pymupdf
ROOT = Path(__file__).resolve().parent
con = sqlite3.connect(ROOT/".data/examdata.db"); cur = con.cursor()
doc_id = int(sys.argv[1]) if len(sys.argv)>1 else 1719
pg = int(sys.argv[2])-1 if len(sys.argv)>2 else 2
row = cur.execute("""SELECT a.storage_key FROM document d
    JOIN document_revision r ON r.id=d.current_revision_id
    JOIN artifact a ON a.id=r.artifact_id WHERE d.id=?""",(doc_id,)).fetchone()
pdf = pymupdf.open(ROOT/".data/artifacts"/row[0])
t = pdf[pg].get_text()
print("len:", len(t))
print(repr(t[:3000]))
print("...")
h = collections.Counter(ord(c) for c in t)
print("top codes:", [(hex(k), v) for k, v in h.most_common(30)])
