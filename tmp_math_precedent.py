"""Dump existing labels for a unit prefix, with question context, to learn precedent."""
import sys
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
c = sqlite3.connect(str(ROOT / '.data' / 'examdata.db'))
c.row_factory = sqlite3.Row

prefix = sys.argv[1]
limit = int(sys.argv[2]) if len(sys.argv) > 2 else 400

rows = c.execute("""
  SELECT tn.code, q.id qid, p.paper_no, d.year, q.number_label, q.marks,
         substr(replace(q.stem_text,char(10),' '),1,140) st
  FROM question_taxonomy qt
  JOIN taxonomy_node tn ON tn.id=qt.node_id
  JOIN question q ON q.id=qt.question_id
  JOIN paper p ON p.id=q.paper_id
  JOIN document d ON d.id=p.document_id
  WHERE tn.code LIKE ?
  ORDER BY tn.code, d.year, p.paper_no, q.display_order
  LIMIT ?""", (prefix + '%', limit)).fetchall()

cur = None
for r in rows:
    if r['code'] != cur:
        cur = r['code']
        print(f"\n########## {cur}")
    print(f"  {r['qid']} {r['paper_no']} {r['year']} #{r['number_label']} {r['marks']}mk | {r['st']}")
