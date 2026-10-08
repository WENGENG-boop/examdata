"""Measure which characters form dot-like runs immediately right of a left-column digit. Read-only."""
from __future__ import annotations
import sqlite3, sys, json, re
from pathlib import Path
from collections import Counter
import pymupdf
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from examdata.paperqa import locator as L
ROOT = Path(__file__).resolve().parent
con = sqlite3.connect(ROOT/".data/examdata.db"); con.row_factory=sqlite3.Row; cur = con.cursor()
d=json.load(open("tmp_r8_scan_split.json"))
docs=[c["doc"] for c in d["changed"]]
pat = re.compile(r"^[1-9]\d{0,2}\.{0,2}$")
cnt = Counter(); examples = {}
for doc_id in docs:
    row = cur.execute("""SELECT a.storage_key FROM document d
        JOIN document_revision r ON r.id=d.current_revision_id
        JOIN artifact a ON a.id=r.artifact_id WHERE d.id=?""",(doc_id,)).fetchone()
    if row is None: continue
    p = ROOT/".data/artifacts"/row["storage_key"]
    if not p.exists(): continue
    pdf = pymupdf.open(p); cip = L.is_ciphered(pdf)
    for index, page in enumerate(pdf):
        if index == 0: continue
        bounds = L._page_bounds(page)
        words = sorted(L._page_words(page, cip), key=lambda w: (round(w[1]/3), w[0]))
        for w in words:
            if not (w[0] < bounds.width*.125 and pat.match(w[4].lstrip("*"))): continue
            x, y, x1, y1 = w[0], w[1], w[2], w[3]
            for o in words:
                if o is w: continue
                if o[0] >= x1 - 2 and o[0] - x1 < 24 and o[1] < y1 and o[3] > y:
                    t = o[4]
                    if len(t) >= 4:
                        sig = "".join(sorted(set(t)))[:12]
                        cnt[sig] += 1
                        examples.setdefault(sig, (doc_id, index+1, t[:30]))
    pdf.close()
for sig, n in cnt.most_common():
    print(n, repr(sig), "ex:", examples[sig])
