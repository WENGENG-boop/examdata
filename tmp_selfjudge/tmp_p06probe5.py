"""p06 probe 5: 29089 family (23) topic check."""
import sqlite3, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
con = sqlite3.connect(f"file:{ROOT / '.data' / 'examdata.db'}?mode=ro", uri=True)
c = con.cursor()

def sq(t, n=600):
    return re.sub(r"\s+", " ", (t or "").strip())[:n]

def codes(qid):
    cur = con.cursor()
    rows = cur.execute("""select tn.code from question_taxonomy qt
        join taxonomy_node tn on tn.id=qt.node_id where qt.question_id=?
        order by tn.code""", (qid,)).fetchall()
    return ",".join(r[0] for r in rows) or "-"

for qid in (29089, 29090, 29094, 29095):
    row = c.execute("select id, number_path, parent_id, marks, stem_text from question where id=?", (qid,)).fetchone()
    if row:
        print(f"\n[{row[0]}] {row[1]} m={row[3]} par={row[2]} codes={codes(qid)}")
        print(f"Q: {sq(row[4], 600)}")
        cur2 = con.cursor()
        for ms in cur2.execute("select answer_text from mark_scheme_entry where question_id=?", (qid,)).fetchall():
            print(f"MS: {sq(ms[0], 400)}")
print("\nDONE")
