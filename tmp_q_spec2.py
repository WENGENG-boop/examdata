import sqlite3, json
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
cur = con.cursor()
print('--- all doc types:')
for r in cur.execute("select doc_type, count(*) from document group by 1").fetchall():
    print(r)
print()
print('--- docs with Specification in title:')
for r in cur.execute("select id,subject_id,doc_type,title from document where title like '%pecification%'").fetchall():
    print(r)
print()
print('--- docs for subject 16 (ial-maths):')
for r in cur.execute("select id,doc_type,title from document where subject_id=16 order by doc_type,id").fetchall():
    print(r)
