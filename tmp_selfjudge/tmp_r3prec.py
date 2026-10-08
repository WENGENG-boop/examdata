"""List questions labeled with a given code (precedents)."""
import sqlite3
import sys

con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
con.row_factory = sqlite3.Row
cur = con.cursor()
for code in sys.argv[1:]:
    rows = cur.execute(
        'select q.id, q.paper_id, q.number_label, q.marks, substr(q.stem_text,1,150) s, '
        '  (select count(*) from mark_scheme_entry m where m.question_id=q.id) nms '
        'from question q join question_taxonomy t on t.question_id=q.id '
        'join taxonomy_node n on n.id=t.node_id where n.code=? order by q.paper_id, q.display_order', (code,)).fetchall()
    print('=' * 100)
    print(f'=== code {code}: {len(rows)} questions')
    for r in rows:
        print(f'  {r["id"]} p={r["paper_id"]} {r["number_label"]!r} {r["marks"]}mk ms={r["nms"]} {r["s"]!r}')
con.close()
