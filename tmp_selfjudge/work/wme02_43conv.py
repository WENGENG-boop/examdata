"""Dump all WME02 questions labeled 4.1/4.2/4.3 with parent + wall markers."""
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
con = sqlite3.connect(f"file:{ROOT / '.data' / 'examdata.db'}?mode=ro", uri=True)
c = con.cursor()

for code in ["WME02-4.1", "WME02-4.2", "WME02-4.3"]:
    print(f"===== {code}")
    for qid, num, par, stem in c.execute(
            """select q.id, q.number_label, q.parent_id,
                      replace(q.stem_text, char(10), ' ')
               from question q
               join question_taxonomy qt on qt.question_id = q.id
               join taxonomy_node tn on tn.id = qt.node_id
               where tn.code = ?
               order by q.paper_id, q.display_order""", (code,)):
        s = (stem or "").lower()
        marks = []
        if "wall" in s:
            marks.append("WALL")
        if "second collision" in s or "subsequently collides" in s:
            marks.append("2ND")
        if "three particles" in s or "particles a, b and c" in s:
            marks.append("3P")
        tag = ",".join(marks) or "-"
        print(f"{qid} par={par} #{num} [{tag}] {s[:115]}")
    print()
