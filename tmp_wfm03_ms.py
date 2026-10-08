import sqlite3
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
con.row_factory = sqlite3.Row
print("=== documents for WFM03 2015 ===")
for r in con.execute("""SELECT id, identity_key, doc_type, year, paper_code, title, status FROM document
    WHERE paper_code LIKE 'wfm03%' AND year BETWEEN 2014 AND 2016 ORDER BY year, paper_code, doc_type""").fetchall():
    print(f"  [{r['id']}] {r['doc_type']} {r['year']} {r['paper_code']} | {r['title'][:90]} | {r['status']}")
print()
print("=== any mark scheme doc text around Q8? search for 'p + q ln 2' style ===")
for r in con.execute("""SELECT q.id, substr(q.stem_text,1,120) t FROM question q WHERE q.stem_text LIKE '%ln 2%' AND q.stem_text LIKE '%rational%' LIMIT 20""").fetchall():
    print(f"  [{r['id']}] {(r['t'] or '')[:120]}")
con.close()
