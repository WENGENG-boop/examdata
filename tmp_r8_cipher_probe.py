"""r8: probe the 71 LocationError docs (cipher-font accounting papers).
Dump decoded words for doc 1719 pages 2-4; check what left-column numbers look like.
Read-only."""
from __future__ import annotations
import sqlite3, sys, re
from pathlib import Path
import pymupdf
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from examdata.paperqa import locator as L

ROOT = Path(__file__).resolve().parent
con = sqlite3.connect(ROOT / ".data/examdata.db"); con.row_factory = sqlite3.Row
cur = con.cursor()

def path_for(doc_id):
    row = cur.execute("""SELECT a.storage_key FROM document d
        JOIN document_revision r ON r.id=d.current_revision_id
        JOIN artifact a ON a.id=r.artifact_id WHERE d.id=?""",(doc_id,)).fetchone()
    return ROOT/".data/artifacts"/row["storage_key"]

doc_id = int(sys.argv[1]) if len(sys.argv)>1 else 1719
p = path_for(doc_id)
print("path:", p, "exists:", p.exists())
pdf = pymupdf.open(p)
print("pages:", len(pdf), "ciphered:", L.is_ciphered(pdf))
for index in (0,1,2,3):
    if index >= len(pdf): break
    page = pdf[index]
    bounds = L._page_bounds(page)
    print(f"\n===== page {index+1} size={bounds.width:.0f}x{bounds.height:.0f} =====")
    words = sorted(L._page_words(page, True), key=lambda w:(round(w[1]/3), w[0]))
    # left column candidates
    cands = [w for w in words if w[0] < bounds.width*.125 and re.fullmatch(r"[1-9]\d{0,2}\.{0,2}", w[4].lstrip("*"))]
    print(f"total words={len(words)} left-col numeric candidates={len(cands)}")
    for w in cands[:30]:
        print(f"  x={w[0]:.1f} y={w[1]:.1f} {w[4]!r}")
    # show first 40 words raw
    print("  first words:", [(round(w[0]),round(w[1]),w[4]) for w in words[:20]])
