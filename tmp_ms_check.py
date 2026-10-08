import sqlite3, re
c = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
c.execute('PRAGMA temp_store=MEMORY')
# find ms text source for paper of 52287
p = c.execute("select paper_id from question where id=52287").fetchone()[0]
print("paper_id:", p)
# what tables hold ms text?
tabs = [r[0] for r in c.execute("select name from sqlite_master where type='table'")]
print([t for t in tabs if 'ms' in t.lower() or 'mark' in t.lower() or 'paper' in t.lower()])
