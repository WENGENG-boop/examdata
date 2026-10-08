import sqlite3, sys
from pathlib import Path
import pymupdf
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from examdata.paperqa import locator as L
import tmp_r8_anchor_fix as T
ROOT = Path(__file__).resolve().parent
con = sqlite3.connect(ROOT/".data/examdata.db"); cur = con.cursor()
doc = cur.execute("select document_id from paper where id=706").fetchone()[0]
key = cur.execute("""SELECT a.storage_key FROM document d JOIN document_revision r ON r.id=d.current_revision_id
    JOIN artifact a ON a.id=r.artifact_id WHERE d.id=?""",(doc,)).fetchone()[0]
pdf = pymupdf.open(ROOT/".data/artifacts"/key)
a1,_ = L._anchors(pdf, "qp")
a2,_ = T.patched_anchors(pdf, "qp")
print("src :", [a.path for a in a1])
print("tmp :", [a.path for a in a2])
print("equal:", [a.path for a in a1]==[a.path for a in a2])
