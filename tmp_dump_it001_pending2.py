"""Second dump: 45831 stem, Q1 structure, MS entries, full point texts."""
import sqlite3

con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
cur = con.cursor()

print('===== q45831')
q = cur.execute('select id,number_path,marks,stem_text,parent_id from question where id=45831').fetchone()
print(q[0], '|', q[1], '| m=', q[2], '| parent=', q[4])
print((q[3] or '')[:2500])
print()

print('===== paper of 45903: all questions')
pid = cur.execute('select paper_id from question where id=45903').fetchone()[0]
rows = cur.execute('select id,number_path,marks,parent_id,substr(stem_text,1,120) from question where paper_id=? order by id', (pid,)).fetchall()
for r in rows:
    print(r[0], '|', r[1], '| m=', r[2], '| p=', r[3], '|', (r[4] or '').replace('\n', ' ')[:110])
print()

print('===== MS entries for target questions')
for qid in (45520, 45732, 45830, 45831, 45903, 45904, 45910):
    rows = cur.execute('select id,question_id,substr(answer_text,1,1500) from mark_scheme_entry where question_id=?', (qid,)).fetchall()
    print(f'--- q{qid}: {len(rows)} entries')
    for r in rows:
        print(f'  entry {r[0]}:')
        print('   ', (r[2] or '').replace('\n', '\n    ')[:1500])
    print()
