"""Survey the 71 LocationError docs: pages, ciphered, text density, fonts. Read-only."""
from __future__ import annotations
import sqlite3, sys, json, collections
from pathlib import Path
import pymupdf
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from examdata.paperqa import locator as L
ROOT = Path(__file__).resolve().parent
con = sqlite3.connect(ROOT/".data/examdata.db"); cur = con.cursor()
d=json.load(open('tmp_r8_scan_split.json'))
errs=[e for e in d['errors'] if e.get('error','').startswith('LocationError')]
ids=[e['doc'] for e in errs]
if len(sys.argv)>1: ids=[int(x) for x in sys.argv[1:]]
for doc_id in ids:
    row = cur.execute("""SELECT a.storage_key FROM document d
        JOIN document_revision r ON r.id=d.current_revision_id
        JOIN artifact a ON a.id=r.artifact_id WHERE d.id=?""",(doc_id,)).fetchone()
    p = ROOT/".data/artifacts"/row[0]
    try:
        doc = pymupdf.open(p)
    except Exception as ex:
        print(doc_id, "OPEN-FAIL", ex); continue
    cip = L.is_ciphered(doc)
    # char stats for first 12 pages
    stats=[]
    for i in range(min(12,len(doc))):
        t = doc[i].get_text()
        h = collections.Counter(ord(c) for c in t)
        top = h.most_common(1)[0] if h else (0,0)
        stats.append((len(t), top[0], round(top[1]/max(1,len(t)),2)))
    fonts = set()
    for i in range(min(6,len(doc))):
        for f in doc[i].get_fonts(): fonts.add(f[3])
    print(f"{doc_id}: pages={len(doc)} ciphered={cip} fonts={sorted(fonts)[:4]}")
    print(f"    per-page (chars, topcode, frac): {stats}")
    doc.close()
