import sqlite3
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
con.row_factory = sqlite3.Row
for eid, tag in [(40600,'Q1'),(40602,'Q2a'),(40607,'Q3d'),(40609,'Q4b'),(40610,'Q5a'),(40616,'Q7b'),(40617,'Q8a'),(40618,'Q8b')]:
    r = con.execute("SELECT answer_text, guidance, raw FROM mark_scheme_entry WHERE id=?", (eid,)).fetchone()
    print(f"\n############### {tag} entry {eid}")
    print((r['answer_text'] or '')[:1800])
    if r['guidance']: print("--- GUIDANCE:", (r['guidance'] or '')[:400])
con.close()
