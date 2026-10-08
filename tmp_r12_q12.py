"""Spec docs + full paper 1412 tags + van question children (q48442)."""
import sqlite3
from pathlib import Path
ROOT = Path(__file__).resolve().parent
con = sqlite3.connect(ROOT / '.data/examdata.db'); con.row_factory = sqlite3.Row
cur = con.cursor()
out = []

out.append("### spec/examiner docs")
for r in cur.execute("SELECT id, paper_code, doc_type, year, title FROM document WHERE title LIKE '%pecification%' OR title LIKE '%xaminer%' OR title LIKE '%Issue%' LIMIT 60"):
    out.append(f"  doc{r['id']} {r['paper_code']} {r['doc_type']} {r['year']} :: {r['title']}")

out.append("### paper 1412 (Jan 2021 WAC11) full tags")
for r in cur.execute("""
  SELECT q.id, q.number_path, q.page_from, substr(q.stem_text,1,110) as st,
         group_concat(tn.code || '(' || qt.source || ')') as tags
  FROM question q LEFT JOIN question_taxonomy qt ON qt.question_id=q.id
  LEFT JOIN taxonomy_node tn ON tn.id=qt.node_id
  WHERE q.paper_id=1412 GROUP BY q.id ORDER BY q.display_order"""):
    out.append(f"  q{r['id']} {r['number_path']} p{r['page_from']} :: {r['tags']} :: {(r['st'] or '')!r}")

out.append("### q48442 children (2019 delivery van question)")
for r in cur.execute("""
  SELECT q.id, q.number_path, substr(q.stem_text,1,110) as st,
         group_concat(tn.code || '(' || qt.source || ')') as tags
  FROM question q LEFT JOIN question_taxonomy qt ON qt.question_id=q.id
  LEFT JOIN taxonomy_node tn ON tn.id=qt.node_id
  WHERE q.paper_id=(SELECT paper_id FROM question WHERE id=48442) AND q.number_path LIKE '5%'
  GROUP BY q.id ORDER BY q.display_order"""):
    out.append(f"  q{r['id']} {r['number_path']} :: {r['tags']} :: {(r['st'] or '')!r}")
con.close()
(ROOT / "tmp_r12_q12_out.txt").write_text("\n".join(out), encoding="utf-8")
print("written", len(out))
