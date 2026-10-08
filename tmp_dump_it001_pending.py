"""Dump full stems + point texts for the 5 pending questions of ial18-it batch-001."""
import json
import sqlite3

con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
cur = con.cursor()

def stem(qid, limit=4000):
    q = cur.execute('select id,number_path,marks,stem_text,parent_id from question where id=?', (qid,)).fetchone()
    if not q:
        print(qid, 'NOT FOUND'); return
    print(f"===== q{q[0]} | {q[1]} | marks={q[2]} | parent={q[4]}")
    print((q[3] or '')[:limit])
    print()

for qid in (45520, 45732, 45830, 45903, 45910):
    stem(qid)

print('===== children of 45903')
rows = cur.execute("select id,number_path,marks,substr(stem_text,1,200) from question where parent_id=45903 order by id").fetchall()
for r in rows:
    print(r[0], '|', r[1], '| m=', r[2], '|', (r[3] or '').replace('\n', ' ')[:200])
print()

print('===== WIT13-12.1.x point texts')
for r in cur.execute("select code,name from taxonomy_node where code like 'WIT13-12.1.%' order by code").fetchall():
    print(r[0], '::', r[1])
print()
print('===== WIT13-13.3.x point texts')
for r in cur.execute("select code,name from taxonomy_node where code like 'WIT13-13.3.%' order by code").fetchall():
    print(r[0], '::', r[1])
print()
print('===== WIT11-3.3.x point texts')
for r in cur.execute("select code,name from taxonomy_node where code like 'WIT11-3.3.%' order by code").fetchall():
    print(r[0], '::', r[1])
