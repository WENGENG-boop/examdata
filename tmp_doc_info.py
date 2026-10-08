import sqlite3
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
con.row_factory = sqlite3.Row
for did in (1772,1773,1732,1720,1774):
    r = con.execute("SELECT id,paper_code,title,doc_type FROM document WHERE id=?",(did,)).fetchone()
    print(dict(r) if r else (did,'NOT FOUND'))
print("--- wac12-01 papers:")
for r in con.execute("SELECT d.id,d.paper_code,d.title,d.doc_type FROM document d WHERE d.paper_code LIKE 'wac12%' ORDER BY d.id"):
    print(dict(r))
print("--- wac02-01 papers:")
for r in con.execute("SELECT d.id,d.paper_code,d.title,d.doc_type FROM document d WHERE d.paper_code LIKE 'wac02%' ORDER BY d.id"):
    print(dict(r))
