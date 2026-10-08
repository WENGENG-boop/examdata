import sqlite3, re, sys
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
cur = con.cursor()
sub = cur.execute("select id, slug from subject where slug like '%math%'").fetchall()
print('subjects:', sub)
