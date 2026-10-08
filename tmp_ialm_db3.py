import sqlite3, json, glob
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
cur = con.cursor()
cols = cur.execute("PRAGMA table_info(paper)").fetchall()
print('paper cols:', [c[1] for c in cols])
print('paper 2083:', cur.execute("select * from paper where id=2083").fetchall())
print()
# questions of paper 2083
rows = cur.execute("select id, number_label, parent_id from question where paper_id=2083 order by display_order").fetchall()
print('paper 2083 questions:', len(rows))
for r in rows[:80]:
    print(' ', r)
