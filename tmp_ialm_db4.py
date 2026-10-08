import sqlite3
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
cur = con.cursor()
for t in ('document','subject'):
    try:
        cols = cur.execute(f"PRAGMA table_info({t})").fetchall()
        print(t, [c[1] for c in cols])
    except Exception as e: print(t, 'ERR', e)
print('docs for papers 1964, 2022, 2083:')
for pid in (1964,2022,2083):
    r = cur.execute("select p.id, p.document_id, p.attrs, d.* from paper p left join document d on d.id=p.document_id where p.id=?", (pid,)).fetchone()
    print(r[:3])
    print('   ', r[3:])
