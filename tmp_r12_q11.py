"""Global search: 'annual cost' across all; q46402 context + MS; 1.6.2 tag list."""
import sqlite3, re
from pathlib import Path
ROOT = Path(__file__).resolve().parent
con = sqlite3.connect(ROOT / '.data/examdata.db'); con.row_factory = sqlite3.Row
cur = con.cursor()
out = []

out.append("### ALL questions with 'annual cost' in stem")
for r in cur.execute("""
  SELECT q.id, d.paper_code, d.year, q.number_path, substr(q.stem_text,1,180) as st,
         group_concat(tn.code || '(' || qt.source || ')') as tags
  FROM question q JOIN paper p ON p.id=q.paper_id JOIN document d ON d.id=p.document_id
  LEFT JOIN question_taxonomy qt ON qt.question_id=q.id
  LEFT JOIN taxonomy_node tn ON tn.id=qt.node_id
  WHERE q.stem_text LIKE '%annual cost%' GROUP BY q.id LIMIT 50"""):
    out.append(f"  q{r['id']} {r['paper_code']} {r['year']} {r['number_path']} :: {r['tags']} :: {(r['st'] or '')!r}")

out.append("### q46402 paper + context")
r = cur.execute("""SELECT q.id, q.paper_id, d.paper_code, d.year, q.number_path, q.stem_text FROM question q
  JOIN paper p ON p.id=q.paper_id JOIN document d ON d.id=p.document_id WHERE q.id=46402""").fetchone()
out.append(f"  q46402 paper{r['paper_id']} {r['paper_code']} {r['year']} {r['number_path']}")
out.append(f"  stem: {(r['stem_text'] or '')[:300]!r}")
# q46402 MS
for e in cur.execute("SELECT number_path, answer_text FROM mark_scheme_entry WHERE question_id=46402"):
    out.append(f"  MS {e['number_path']}: {repr((e['answer_text'] or '')[:700])}")
# Also MS of the whole 46402 paper around it
for e in cur.execute("""SELECT question_id, number_path, substr(answer_text,1,300) as a FROM mark_scheme_entry
  WHERE question_id IN (SELECT id FROM question WHERE paper_id=?) AND number_path LIKE '%4(d)%'""", (r['paper_id'],)):
    out.append(f"  MS q{e['question_id']} {e['number_path']}: {repr(e['a'])}")

out.append("### WAC11 questions tagged 1.6.2 (sample)")
for r in cur.execute("""
  SELECT q.id, d.paper_code, d.year, q.number_path, substr(q.stem_text,1,150) as st
  FROM question_taxonomy qt JOIN question q ON q.id=qt.question_id
  JOIN taxonomy_node tn ON tn.id=qt.node_id
  JOIN paper p ON p.id=q.paper_id JOIN document d ON d.id=p.document_id
  WHERE tn.code='WAC11-1.6.2' ORDER BY d.year LIMIT 40"""):
    out.append(f"  q{r['id']} {r['paper_code']} {r['year']} {r['number_path']} :: {(r['st'] or '')!r}")
con.close()
(ROOT / "tmp_r12_q11_out.txt").write_text("\n".join(out), encoding="utf-8")
print("written", len(out))
