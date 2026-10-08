"""Fifth dump: sub-nodes check, parent-tag precedents, taxi paper MS doc."""
import sqlite3

con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
cur = con.cursor()

print('===== taxonomy_node schema')
print(cur.execute("select sql from sqlite_master where name='taxonomy_node'").fetchone()[0])
print()

print('===== any nodes with 13.3.x sub-level?')
for r in cur.execute("select code,name from taxonomy_node where code like 'WIT13-13.3%' order by code").fetchall():
    print(r[0], '::', (r[1] or '')[:80])
print()

print('===== applied ai-review PARENT tags (precedents)')
rows = cur.execute('''
select q.id, q.number_path, q.marks, n.code, n.name
from question q
join question_taxonomy qt on qt.question_id=q.id and qt.source='ai-review'
join taxonomy_node n on n.id=qt.node_id
where exists (select 1 from question c where c.parent_id=q.id)
order by q.id limit 40
''').fetchall()
for r in rows:
    print(r[0], '|', r[1], '| m=', r[2], '->', r[3], '::', (r[4] or '')[:60])
print()

print('===== taxi paper: find paper of 45831, list its MS entries')
pid = cur.execute('select paper_id from question where id=45831').fetchone()[0]
print('paper_id =', pid)
doc = cur.execute('select document_id from question where id=45831').fetchone()
print('doc row:', doc)
rows = cur.execute('select id,question_id,substr(answer_text,1,150) from mark_scheme_entry where question_id in (select id from question where paper_id=?) order by id', (pid,)).fetchall()
for r in rows:
    print(r[0], 'q=', r[1], '::', (r[2] or '').replace('\n', ' / ')[:150])
