"""q46886 MS + Jun2021 WAC11 paper Qs + 1.6.2-family checks."""
import sqlite3
from pathlib import Path
ROOT = Path(__file__).resolve().parent
con = sqlite3.connect(ROOT / '.data/examdata.db'); con.row_factory = sqlite3.Row
cur = con.cursor()
out = []

out.append("### q46886 (Cachi invest machinery) + MS")
r = cur.execute("SELECT q.id, q.paper_id, q.number_path, q.stem_text FROM question q WHERE q.id=46886").fetchone()
out.append(f"  q46886 paper{r['paper_id']} {r['number_path']} :: {(r['stem_text'] or '')[:250]!r}")
for e in cur.execute("SELECT number_path, answer_text FROM mark_scheme_entry WHERE question_id=46886"):
    out.append(f"  MS {e['number_path']}: {repr((e['answer_text'] or '')[:900])}")

out.append("### paper of doc1757 (Jun 2021 WAC11 QP) questions")
r = cur.execute("SELECT id FROM paper WHERE document_id=1757").fetchone()
if r:
    pid = r['id']
    for q in cur.execute("""SELECT q.id, q.number_path, substr(q.stem_text,1,110) as st,
        group_concat(tn.code || '(' || qt.source || ')') as tags
        FROM question q LEFT JOIN question_taxonomy qt ON qt.question_id=q.id
        LEFT JOIN taxonomy_node tn ON tn.id=qt.node_id
        WHERE q.paper_id=? GROUP BY q.id ORDER BY q.display_order""", (pid,)):
        out.append(f"  q{q['id']} {q['number_path']} :: {q['tags']} :: {(q['st'] or '')!r}")
else:
    out.append("  no paper for doc1757")

out.append("### all 1.6.2/1.6.3 tags on WAC11 'calculate cost' questions")
for q in cur.execute("""SELECT q.id, d.year, q.number_path, substr(q.stem_text,1,130) as st,
    group_concat(tn.code || '(' || qt.source || ')') as tags
    FROM question q JOIN paper p ON p.id=q.paper_id JOIN document d ON d.id=p.document_id
    LEFT JOIN question_taxonomy qt ON qt.question_id=q.id
    LEFT JOIN taxonomy_node tn ON tn.id=qt.node_id
    WHERE d.paper_code LIKE 'wac11%' AND q.stem_text LIKE '%alculate%' AND q.stem_text LIKE '%cost%'
    GROUP BY q.id ORDER BY d.year LIMIT 60"""):
    out.append(f"  q{q['id']} {q['year']} {q['number_path']} :: {q['tags']} :: {(q['st'] or '')!r}")
con.close()
(ROOT / "tmp_r12_q13_out.txt").write_text("\n".join(out), encoding="utf-8")
print("written", len(out))
