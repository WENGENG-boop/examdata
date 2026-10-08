import sqlite3, json
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
cur = con.cursor()
# schema
for t in ('question','question_taxonomy','taxonomy_node','mark_scheme_entry'):
    try:
        cols = cur.execute(f"PRAGMA table_info({t})").fetchall()
        print(t, [c[1] for c in cols])
    except Exception as e:
        print(t, 'ERR', e)
print("---- counts")
print(cur.execute("select count(*) from question").fetchone())
