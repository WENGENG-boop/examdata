"""Brute-force the cipher shift for doc 1719 by scoring decoded page-1 text. Read-only."""
from __future__ import annotations
import sqlite3, sys, re
from pathlib import Path
import pymupdf
ROOT = Path(__file__).resolve().parent
con = sqlite3.connect(ROOT/".data/examdata.db"); cur = con.cursor()
doc_id = int(sys.argv[1]) if len(sys.argv)>1 else 1719
row = cur.execute("""SELECT a.storage_key FROM document d
    JOIN document_revision r ON r.id=d.current_revision_id
    JOIN artifact a ON a.id=r.artifact_id WHERE d.id=?""",(doc_id,)).fetchone()
pdf = pymupdf.open(ROOT/".data/artifacts"/row[0])
txt = "".join(pdf[i].get_text() for i in range(min(3,len(pdf))))
WORDS = ["Pearson","Edexcel","Instructions","Answer","Question","Write","Information","Turn over","paper","total","marks","candidate"]
def dec(t, sh):
    out=[]
    for ch in t:
        c=ord(ch)
        if c in (0x09,0x0A,0x0D,0x20) or c<0x03 or c>0x61: out.append(ch)
        else: out.append(chr(c+sh))
    return "".join(out)
best=[]
for sh in range(0, 0x61):
    d=dec(txt, sh)
    score=sum(d.count(w) for w in WORDS)
    letters=sum(1 for c in d if c.isalpha())
    best.append((score, letters, sh))
best.sort(reverse=True)
for score,letters,sh in best[:8]:
    print(f"shift={sh:#04x} ({sh}) score={score} letters={letters}")
    print("   ", repr(dec(txt[:200], sh)))
