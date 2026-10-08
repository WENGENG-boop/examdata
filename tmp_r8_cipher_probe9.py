"""Deep dive on doc 1778 (WAA02 Jun 2022) and 2130 (WFR02 Jun 2019): blocks, images, drawings. Read-only."""
from __future__ import annotations
import sqlite3, sys, collections
from pathlib import Path
import pymupdf
ROOT = Path(__file__).resolve().parent
con = sqlite3.connect(ROOT/".data/examdata.db"); cur = con.cursor()
def get(doc_id):
    row = cur.execute("""SELECT a.storage_key FROM document d
        JOIN document_revision r ON r.id=d.current_revision_id
        JOIN artifact a ON a.id=r.artifact_id WHERE d.id=?""",(doc_id,)).fetchone()
    return pymupdf.open(ROOT/".data/artifacts"/row[0])
for doc_id, pages in ((1778,(0,1,2)), (2130,(0,1,2))):
    doc = get(doc_id)
    print(f"\n########## doc {doc_id} pages={len(doc)} ##########")
    for pg in pages:
        page = doc[pg]
        print(f"--- page {pg+1}: imgs={len(page.get_images(full=True))} drawings={len(page.get_drawings())} xobj={len(page.get_xobjects())}")
        d = page.get_text("rawdict")
        blocks=[b for b in d["blocks"]]
        print(f"    blocks={len(blocks)}")
        for bi,b in enumerate(blocks[:10]):
            if b["type"]!=0:
                print(f"    block{bi}: IMAGE bbox={tuple(round(v) for v in b['bbox'])}")
                continue
            for line in b["lines"][:3]:
                txt="".join(ch["c"] for sp in line["spans"] for ch in sp["chars"])
                if len(txt)>70: txt=txt[:70]+f"...(+{len(txt)-70})"
                print(f"    block{bi} line bbox={tuple(round(v) for v in line['bbox'])} n={len(txt)} {txt!r}")
