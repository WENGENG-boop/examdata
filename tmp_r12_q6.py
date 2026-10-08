"""Extract raw PDF text: paper 1358 (partner statement, pages 29-32) and paper 1412 (Eva scenario, pages 17-22)."""
import sqlite3, re, sys
from pathlib import Path
import fitz

ROOT = Path(__file__).resolve().parent
con = sqlite3.connect(ROOT / '.data/examdata.db'); con.row_factory = sqlite3.Row
cur = con.cursor()
out = []


def pdf_path_for_paper(pid):
    row = cur.execute("""
        SELECT a.storage_key FROM paper p
        JOIN document d ON d.id = p.document_id
        JOIN document_revision dr ON dr.id = d.current_revision_id
        JOIN artifact a ON a.id = dr.artifact_id
        WHERE p.id = ?""", (pid,)).fetchone()
    return ROOT / '.data' / 'artifacts' / row['storage_key'] if row else None


for pid, pages, label in [(1358, range(28, 33), "paper1358 partner statement"),
                          (1412, range(17, 23), "paper1412 Eva scenario")]:
    path = pdf_path_for_paper(pid)
    out.append(f"===== {label} pid={pid} file={path}")
    if not path or not path.exists():
        out.append("  PDF NOT FOUND")
        continue
    doc = fitz.open(path)
    out.append(f"  pages={doc.page_count}")
    for pno in pages:
        if pno - 1 >= doc.page_count:
            continue
        page = doc[pno - 1]
        text = page.get_text()
        out.append(f"\n----- PAGE {pno} -----")
        for l in text.splitlines():
            s = l.strip()
            if s:
                out.append(s[:160])
con.close()
(ROOT / "tmp_r12_q6_out.txt").write_text("\n".join(out), encoding="utf-8")
print("written", len(out))
