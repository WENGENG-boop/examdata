"""Print current DB taxonomy labels for qids.

usage: python tmp_labels.py qid1 qid2 ...
"""
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
con = sqlite3.connect(f"file:{ROOT / '.data' / 'examdata.db'}?mode=ro", uri=True)
c = con.cursor()

for qid in [int(x) for x in sys.argv[1:]]:
    row = c.execute("select id, number_label, parent_id from question where id=?", (qid,)).fetchone()
    if not row:
        print(f"{qid} NOT FOUND")
        continue
    codes = [r[0] for r in c.execute(
        "select tn.code from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id "
        "where qt.question_id=? order by tn.code", (qid,))]
    print(f"{qid} #{row[1]} par={row[2]} :: {', '.join(codes) if codes else '-'}")
