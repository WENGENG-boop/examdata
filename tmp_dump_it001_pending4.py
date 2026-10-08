"""Fourth dump: MS entries 45906-45912, full 13.3.2/13.3.4 text, taxi paper MS."""
import sqlite3

con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
cur = con.cursor()

print('===== MS entries for 45906-45912 (numbers + head)')
for qid in range(45906, 45913):
    rows = cur.execute('select id,question_id,substr(answer_text,1,220) from mark_scheme_entry where question_id=?', (qid,)).fetchall()
    print(f'--- q{qid}: {len(rows)}')
    for r in rows:
        print(f'  {r[0]}:', (r[2] or '').replace('\n', ' / ')[:220])
print()

print('===== full entry 26089 (all chars)')
r = cur.execute('select answer_text from mark_scheme_entry where id=26089').fetchone()
print((r[0] or '')[:4000])
print()

print('===== full name of WIT13-13.3.2 / 13.3.4 / 13.3.3')
for code in ('WIT13-13.3.2', 'WIT13-13.3.4', 'WIT13-13.3.3', 'WIT13-13.3.1'):
    r = cur.execute('select name from taxonomy_node where code=?', (code,)).fetchone()
    print(code, '::')
    print(r[0])
    print()
