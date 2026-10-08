"""Dump all questions + MS in a paper, optionally filtered by order range."""
import sqlite3
import sys

con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
con.row_factory = sqlite3.Row
cur = con.cursor()
paper = int(sys.argv[1])
lo = int(sys.argv[2]) if len(sys.argv) > 2 else 0
hi = int(sys.argv[3]) if len(sys.argv) > 3 else 10**9

qs = cur.execute('select id, number_label, marks, display_order, stem_text from question where paper_id=? order by display_order, id', (paper,)).fetchall()
for q in qs:
    if not (lo <= (q['display_order'] or 0) <= hi):
        continue
    codes = cur.execute('select group_concat(n.code) from question_taxonomy t join taxonomy_node n on n.id=t.node_id where t.question_id=?', (q['id'],)).fetchone()[0]
    print('#' * 100)
    print(f'## q{q["id"]} ord={q["display_order"]} {q["number_label"]!r} {q["marks"]}mk [{codes or "-"}]')
    st = (q['stem_text'] or '')
    st = '\n'.join(l for l in st.splitlines() if l.strip('.').strip())
    print(st[:1400])
    for r in cur.execute('select number_label, answer_text, guidance from mark_scheme_entry where question_id=? order by id', (q['id'],)):
        at = (r['answer_text'] or '')
        at = '\n'.join(l for l in at.splitlines() if l.strip('.').strip())
        print(f'  -- MS[{r["number_label"]}]: {at[:1800]}')
        if r['guidance']:
            g = '\n'.join(l for l in r['guidance'].splitlines() if l.strip('.').strip())
            print(f'     GUID: {g[:800]}')
con.close()
