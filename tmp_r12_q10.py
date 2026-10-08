"""q68440 stem + paper1407 Q4 + annual-cost precedents + Jun2016 MS Q4."""
import sqlite3, re
from pathlib import Path
import fitz

ROOT = Path(__file__).resolve().parent
con = sqlite3.connect(ROOT / '.data/examdata.db'); con.row_factory = sqlite3.Row
cur = con.cursor()
out = []

out.append("### paper 1407 all questions")
for r in cur.execute("""
  SELECT q.id, q.number_path, q.page_from, q.marks, substr(q.stem_text,1,220) as st,
         group_concat(tn.code || '(' || qt.source || ',' || printf('%.3f',qt.confidence) || ')') as tags
  FROM question q
  LEFT JOIN question_taxonomy qt ON qt.question_id = q.id
  LEFT JOIN taxonomy_node tn ON tn.id = qt.node_id
  WHERE q.paper_id = 1407 GROUP BY q.id ORDER BY q.display_order"""):
    out.append(f"  q{r['id']} {r['number_path']} p{r['page_from']} m={r['marks']} :: {r['tags']}")
    out.append(f"      {(r['st'] or '')!r}")

out.append("### WAC papers: stems with 'annual cost' or 'security'")
for r in cur.execute("""
  SELECT q.id, d.paper_code, d.year, q.number_path, substr(q.stem_text,1,200) as st,
         group_concat(tn.code || '(' || qt.source || ')') as tags
  FROM question q
  JOIN paper p ON p.id = q.paper_id JOIN document d ON d.id = p.document_id
  LEFT JOIN question_taxonomy qt ON qt.question_id = q.id
  LEFT JOIN taxonomy_node tn ON tn.id = qt.node_id
  WHERE d.paper_code LIKE 'wac%' AND (q.stem_text LIKE '%annual cost%' OR q.stem_text LIKE '%security%')
  GROUP BY q.id ORDER BY d.year LIMIT 60"""):
    out.append(f"  q{r['id']} {r['paper_code']} {r['year']} {r['number_path']} :: {r['tags']} :: {(r['st'] or '')!r}")

out.append("### WAC11: stems with 'Evaluate whether' (see node pattern)")
for r in cur.execute("""
  SELECT q.id, d.paper_code, d.year, q.number_path, substr(q.stem_text,1,160) as st,
         group_concat(tn.code || '(' || qt.source || ')') as tags
  FROM question q
  JOIN paper p ON p.id = q.paper_id JOIN document d ON d.id = p.document_id
  LEFT JOIN question_taxonomy qt ON qt.question_id = q.id
  LEFT JOIN taxonomy_node tn ON tn.id = qt.node_id
  WHERE d.paper_code LIKE 'wac11%' AND q.stem_text LIKE '%valuate whether%'
  GROUP BY q.id ORDER BY d.year LIMIT 80"""):
    out.append(f"  q{r['id']} {r['paper_code']} {r['year']} {r['number_path']} :: {r['tags']} :: {(r['st'] or '')!r}")

# Jun 2016 MS Q4
row = cur.execute("""SELECT a.storage_key FROM document d JOIN document_revision dr ON dr.id=d.current_revision_id
  JOIN artifact a ON a.id=dr.artifact_id WHERE d.id=1664""").fetchone()
path = ROOT / '.data' / 'artifacts' / row['storage_key']
out.append(f"\n===== Jun2016 MS doc1664 {path}")
doc = fitz.open(path)
out.append(f"  pages={doc.page_count}")
for pno in range(doc.page_count):
    text = doc[pno].get_text()
    if re.search(r'Question 4|4\s*\(e\)|depreciation', text, re.I):
        out.append(f"\n----- PAGE {pno+1} -----")
        for l in text.splitlines():
            s = l.strip()
            if s:
                out.append(s[:150])
con.close()
(ROOT / "tmp_r12_q10_out.txt").write_text("\n".join(out), encoding="utf-8")
print("written", len(out))
