"""Sibling tags paper1358 + partnership evaluation precedents."""
import sqlite3, re
from pathlib import Path
ROOT = Path(__file__).resolve().parent
con = sqlite3.connect(ROOT / '.data/examdata.db'); con.row_factory = sqlite3.Row
cur = con.cursor()
out = []

out.append("### paper 1358 all questions with tags")
for r in cur.execute("""
  SELECT q.id, q.number_path, q.page_from, q.marks, substr(q.stem_text,1,120) as st,
         group_concat(tn.code || '(' || qt.source || ',' || printf('%.3f',qt.confidence) || ')') as tags
  FROM question q
  LEFT JOIN question_taxonomy qt ON qt.question_id = q.id
  LEFT JOIN taxonomy_node tn ON tn.id = qt.node_id
  WHERE q.paper_id = 1358 GROUP BY q.id ORDER BY q.display_order"""):
    out.append(f"  q{r['id']} {r['number_path']} p{r['page_from']} m={r['marks']} :: {r['tags']}")
    out.append(f"      {(r['st'] or '')!r}")

out.append("### WAC11 questions mentioning partnership + evaluate (any year)")
for r in cur.execute("""
  SELECT q.id, d.paper_code, d.year, q.number_path, substr(q.stem_text,1,200) as st,
         group_concat(tn.code || '(' || qt.source || ')') as tags
  FROM question q
  JOIN paper p ON p.id = q.paper_id JOIN document d ON d.id = p.document_id
  LEFT JOIN question_taxonomy qt ON qt.question_id = q.id
  LEFT JOIN taxonomy_node tn ON tn.id = qt.node_id
  WHERE d.paper_code LIKE 'wac11%' AND q.stem_text LIKE '%partner%'
    AND (q.stem_text LIKE '%valuate%' OR q.stem_text LIKE '%dvantage%' OR q.stem_text LIKE '%isadvantage%')
  GROUP BY q.id ORDER BY d.year LIMIT 60"""):
    out.append(f"  q{r['id']} {r['paper_code']} {r['year']} {r['number_path']} :: {r['tags']} :: {(r['st'] or '')!r}")

out.append("### WAC11 node 1.6.x + 1.3.9-1.3.13 full titles")
for r in cur.execute("""SELECT code, name FROM taxonomy_node WHERE code LIKE 'WAC11-1.6%' OR code LIKE 'WAC11-1.3.9%' OR code IN ('WAC11-1.3.9','WAC11-1.3.11','WAC11-1.3.12','WAC11-1.3.13')"""):
    out.append(f"  {r['code']} :: {r["name"]}")
con.close()
(ROOT / "tmp_r12_q8_out.txt").write_text("\n".join(out), encoding="utf-8")
print("written", len(out))
