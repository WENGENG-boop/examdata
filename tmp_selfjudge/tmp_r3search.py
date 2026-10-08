"""Search question stems / MS text for a phrase; print qid, paper, code."""
import sqlite3
import sys

con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
con.row_factory = sqlite3.Row
cur = con.cursor()
pat = sys.argv[1]
limit = int(sys.argv[2]) if len(sys.argv) > 2 else 60
like = f'%{pat}%'
rows = cur.execute(
    'select q.id, q.paper_id, q.number_label, q.marks, substr(q.stem_text,1,160) s, '
    '  (select group_concat(n.code) from question_taxonomy t join taxonomy_node n on n.id=t.node_id where t.question_id=q.id) codes, '
    '  (select count(*) from mark_scheme_entry m where m.question_id=q.id) nms '
    'from question q where q.stem_text like ? order by q.paper_id, q.display_order limit ?', (like, limit)).fetchall()
print(f'--- stem matches for {pat!r}: {len(rows)}')
for r in rows:
    print(f'{r["id"]} p={r["paper_id"]} {r["number_label"]!r} {r["marks"]}mk ms={r["nms"]} [{r["codes"] or "-"}] {r["s"]!r}')
rows = cur.execute(
    'select m.question_id, q.paper_id, m.number_label, substr(m.answer_text,1,220) a, '
    '  (select group_concat(n.code) from question_taxonomy t join taxonomy_node n on n.id=t.node_id where t.question_id=q.id) codes '
    'from mark_scheme_entry m join question q on q.id=m.question_id where m.answer_text like ? limit ?', (like, limit)).fetchall()
print(f'--- MS matches for {pat!r}: {len(rows)}')
for r in rows:
    print(f'{r["question_id"]} p={r["paper_id"]} [{r["codes"] or "-"}] {r["a"]!r}')
con.close()
