import sqlite3
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
cur = con.cursor()
for r in cur.execute("select id,code,slug,title from subject where id=16 or code like '%math%' or slug like '%math%'").fetchall():
    print(r)
print()
print('subjects total:', cur.execute('select count(*) from subject').fetchone())
