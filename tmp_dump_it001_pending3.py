"""Third dump: full WIT13 list, sub-bullets, taxi MS search, sibling parent tags."""
import sqlite3

con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
cur = con.cursor()

print('===== full WIT13 taxonomy')
for r in cur.execute("select code,name from taxonomy_node where code like 'WIT13-%' order by code").fetchall():
    print(r[0], '::', (r[1] or '').replace('\n', ' | '))
print()

print('===== full WIT11 3.3.x + 6.1.x')
for r in cur.execute("select code,name from taxonomy_node where code like 'WIT11-3.3.%' or code like 'WIT11-6.1.%' order by code").fetchall():
    print(r[0], '::', (r[1] or '').replace('\n', ' | '))
print()

print('===== MS entries mentioning audio input (taxi paper)')
for r in cur.execute("select id,question_id,substr(answer_text,1,600) from mark_scheme_entry where answer_text like '%audio input%' or answer_text like '%haptic%'").fetchall():
    print(f'entry {r[0]} q={r[1]}:')
    print('  ', (r[2] or '').replace('\n', ' / ')[:600])
print()

print('===== sibling parent questions in same paper: tags')
for qid in (45905, 45913, 45921, 45924, 45927, 45918, 45926):
    tags = cur.execute('''select n.code,qt.confidence,qt.reviewed,qt.source from question_taxonomy qt join taxonomy_node n on qt.node_id=n.id where qt.question_id=?''', (qid,)).fetchall()
    q = cur.execute('select number_path,marks from question where id=?', (qid,)).fetchone()
    print(qid, q, '->', [(t[0], t[1], t[2], t[3]) for t in tags])
print()

print('===== q45518 (parent of 45520) full stem')
q = cur.execute('select id,number_path,marks,stem_text from question where id=45518').fetchone()
print(q[0], '|', q[1], '| m=', q[2])
print((q[3] or '')[:3000])
