import sqlite3, sys
from pathlib import Path
import pymupdf
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from examdata.paperqa import locator as L
ROOT = Path(__file__).resolve().parent
con = sqlite3.connect(ROOT/".data/examdata.db"); cur = con.cursor()
doc = cur.execute("select document_id from paper where id=706").fetchone()[0]
key = cur.execute("""SELECT a.storage_key FROM document d JOIN document_revision r ON r.id=d.current_revision_id
    JOIN artifact a ON a.id=r.artifact_id WHERE d.id=?""",(doc,)).fetchone()[0]
pdf = pymupdf.open(ROOT/".data/artifacts"/key)
cip = L.is_ciphered(pdf)
anchors,_ = L._anchors(pdf, "qp", ciphered=cip)
for a in anchors:
    if a.path in ("2",):
        page = pdf[a.page]; b = L._page_bounds(page)
        words = L._page_words(page, cip)
        line = sorted((w for w in words if abs(w[1]-a.y) < 8), key=lambda w: w[0])
        print(f"anchor {a.path!r} page={a.page+1} y={a.y:.1f}  line={[(round(w[0]), round(w[1]), w[4][:24]) for w in line[:8]]}")
        # check dots nearby
        near = [w for w in words if w[0] >= 60 and abs(w[1]-a.y) < 12]
        print("   right-of-60 words:", [(round(w[0]), round(w[1]), w[4][:30]) for w in near[:6]])
