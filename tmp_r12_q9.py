"""Extract MS PDF text: Jan 2021 WAC11 (Eva Q3 d/e), Jun 2016 (q68440), Jun 2019 6(e) full."""
import sqlite3, re
from pathlib import Path
import fitz

ROOT = Path(__file__).resolve().parent
con = sqlite3.connect(ROOT / '.data/examdata.db'); con.row_factory = sqlite3.Row
cur = con.cursor()
out = []


def pdf_path_for_doc(did):
    row = cur.execute("""
        SELECT a.storage_key FROM document d
        JOIN document_revision dr ON dr.id = d.current_revision_id
        JOIN artifact a ON a.id = dr.artifact_id
        WHERE d.id = ?""", (did,)).fetchone()
    return ROOT / '.data' / 'artifacts' / row['storage_key'] if row else None


def dump(did, label, pat=None, maxpages=80):
    path = pdf_path_for_doc(did)
    out.append(f"\n===== {label} doc{did} file={path}")
    if not path or not path.exists():
        out.append("  NOT FOUND")
        return
    doc = fitz.open(path)
    out.append(f"  pages={doc.page_count}")
    for pno in range(min(doc.page_count, maxpages)):
        text = doc[pno].get_text()
        if pat and not re.search(pat, text):
            continue
        out.append(f"\n----- PAGE {pno+1} -----")
        for l in text.splitlines():
            s = l.strip()
            if s:
                out.append(s[:150])


# Jan 2021 WAC11 MS — find Q3 (Eva) pages
dump(1762, "Jan2021 MS doc1762", pat=r'Question 3|Eva|security|stolen|3\s*\(', maxpages=40)
con.close()
(ROOT / "tmp_r12_q9_out.txt").write_text("\n".join(out), encoding="utf-8")
print("written", len(out))
