"""Show question tree (by parent_id) for a paper, with codes and MS presence."""
import sqlite3
import sys

con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
con.row_factory = sqlite3.Row
cur = con.cursor()
paper = int(sys.argv[1])
top = sys.argv[2] if len(sys.argv) > 2 else None  # optional: only print subtree of this id

rows = cur.execute('select id, parent_id, number_label, number_path, marks, depth, kind, display_order, stem_text from question where paper_id=? order by display_order, id', (paper,)).fetchall()
byid = {r['id']: r for r in rows}
kids = {}
for r in rows:
    kids.setdefault(r['parent_id'], []).append(r)


def codes(qid):
    return cur.execute('select group_concat(n.code) from question_taxonomy t join taxonomy_node n on n.id=t.node_id where t.question_id=?', (qid,)).fetchone()[0]


def show(q, ind):
    st = (q['stem_text'] or '')
    st = ' | '.join(l.strip() for l in st.splitlines() if l.strip('.').strip())
    c = codes(q['id'])
    nms = cur.execute('select count(*) from mark_scheme_entry where question_id=?', (q['id'],)).fetchone()[0]
    print(f'{"  " * ind}q{q["id"]} {q["number_label"]!r} {q["marks"]}mk d{q["depth"]} [{c or "-"}] ms={nms} :: {st[:180]}')
    for k in kids.get(q['id'], []):
        show(k, ind + 1)


roots = [r for r in rows if r['parent_id'] is None]
if top:
    t = int(top)
    # print ancestors chain then subtree
    chain = []
    node = byid.get(t)
    while node:
        chain.append(node)
        node = byid.get(node['parent_id']) if node['parent_id'] else None
    for n in reversed(chain):
        c = codes(n['id'])
        print(f'ANCESTOR q{n["id"]} {n["number_label"]!r} {n["marks"]}mk [{c or "-"}]')
        print('   STEM:', ' | '.join(l.strip() for l in (n['stem_text'] or '').splitlines() if l.strip('.').strip())[:600])
    print('--- subtree ---')
    show(byid[t], 0)
else:
    for r in roots:
        show(r, 0)
con.close()
