"""Verify the production locator patch reproduces the validated fixtures. Read-only."""
from __future__ import annotations
import sqlite3, sys
from pathlib import Path
import pymupdf
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from examdata.paperqa import locator as L
ROOT = Path(__file__).resolve().parent
con = sqlite3.connect(ROOT/".data/examdata.db"); con.row_factory = sqlite3.Row; cur = con.cursor()

FIX = {
    706: ['1','1(a)','1(b)','1(b)(i)','1(b)(ii)','1(c)','1(d)','1(d)(i)','1(d)(ii)','1(e)','2','2(a)','2(b)','2(c)','2(d)','3','3(a)','3(a)(i)','3(a)(ii)','3(a)(iii)','3(a)(iv)','3(b)','3(b)(i)','3(b)(ii)','3(b)(iii)','3(b)(iv)','3(b)(v)'],
    2162: ['1','1(a)','1(b)','1(c)','2','2(a)','2(b)','2(c)','3','4','4(a)','4(b)','4(c)','5','5(a)','5(b)','6','6(a)','6(b)','6(c)','7','8','9'],
    1351: ['1','1(a)','1(b)','1(b)(i)','1(b)(ii)','1(c)','1(d)','1(e)','2','2(a)','2(b)','2(b)(i)','2(b)(ii)','2(c)','2(c)(i)','2(c)(ii)','3','3(a)','3(b)','4','4(a)','4(b)','5','5(a)','5(b)','6'],
}
def doc_of_paper(pid):
    return cur.execute("select document_id from paper where id=?",(pid,)).fetchone()[0]
def path_for(doc_id):
    row = cur.execute("""SELECT a.storage_key FROM document d
        JOIN document_revision r ON r.id=d.current_revision_id
        JOIN artifact a ON a.id=r.artifact_id WHERE d.id=?""",(doc_id,)).fetchone()
    return ROOT/".data/artifacts"/row["storage_key"]
ok=True
for pid, expected in FIX.items():
    doc_id = doc_of_paper(pid)
    pdf = pymupdf.open(path_for(doc_id))
    anchors, end = L._anchors(pdf, "qp")
    got = [a.path for a in anchors]
    same = got == expected
    ok &= same
    print(f"paper {pid}: {'OK' if same else 'MISMATCH'}  n={len(got)}")
    if not same:
        print("   got:", got)
        print("   exp:", expected)
print("ALL OK" if ok else "FAILED")
