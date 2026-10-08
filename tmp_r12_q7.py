"""Find source booklets + list WAC11/WAC12 docs."""
import sqlite3
from pathlib import Path
ROOT = Path(__file__).resolve().parent
con = sqlite3.connect(ROOT / '.data/examdata.db'); con.row_factory = sqlite3.Row
cur = con.cursor()
out = []
out.append("### docs with 'source' or 'booklet' in title")
for r in cur.execute("SELECT id, paper_code, doc_type, year, title FROM document WHERE title LIKE '%ource%' OR title LIKE '%ooklet%' LIMIT 100"):
    out.append(f"  doc{r['id']} {r['paper_code']} {r['doc_type']} {r['year']} :: {r['title']}")
out.append("### all WAC11 docs")
for r in cur.execute("SELECT id, paper_code, doc_type, year, title FROM document WHERE paper_code LIKE 'wac11%' ORDER BY year LIMIT 100"):
    out.append(f"  doc{r['id']} {r['paper_code']} {r['doc_type']} {r['year']} :: {r['title']}")
out.append("### all WAC12 docs")
for r in cur.execute("SELECT id, paper_code, doc_type, year, title FROM document WHERE paper_code LIKE 'wac12%' ORDER BY year LIMIT 100"):
    out.append(f"  doc{r['id']} {r['paper_code']} {r['doc_type']} {r['year']} :: {r['title']}")
# papers 1358, 1412, 1407, 1391 docs
out.append("### papers of interest")
for pid in (1358, 1412, 1407, 1391, 2185, 2206):
    r = cur.execute("SELECT p.id, d.id as did, d.paper_code, d.title, d.doc_type, d.year FROM paper p JOIN document d ON d.id=p.document_id WHERE p.id=?", (pid,)).fetchone()
    if r:
        out.append(f"  paper{pid} -> doc{r['did']} {r['paper_code']} {r['doc_type']} {r['year']} :: {r['title']}")
con.close()
(ROOT / "tmp_r12_q7_out.txt").write_text("\n".join(out), encoding="utf-8")
print("written", len(out))
