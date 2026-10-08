import sqlite3, json
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
con.row_factory = sqlite3.Row

q = """
SELECT d.id, d.year, d.paper_code, d.title, d.status, d.attrs,
       (SELECT COUNT(*) FROM paper p JOIN question qq ON qq.paper_id=p.id WHERE p.document_id=d.id) AS nq,
       (SELECT COUNT(*) FROM paper p WHERE p.document_id=d.id) AS npaper
FROM document d WHERE d.doc_type='question_paper' AND d.board_id=2
"""
rows = con.execute(q).fetchall()
zero = [r for r in rows if r['nq'] == 0]

from collections import Counter
print("=== status x year ===")
cross = Counter((r['status'], r['year']) for r in zero)
for (st, y) in sorted(cross, key=lambda x: (x[0], x[1])):
    print(f"  {st:10s} {y}: {cross[(st,y)]}")

print("\n=== 'stored' 0-q docs (85) ===")
for r in zero:
    if r['status'] != 'stored': continue
    a = json.loads(r['attrs'] or '{}')
    keys = [k for k in a.keys()]
    print(f"  [{r['id']}] y={r['year']} {r['paper_code']} npaper={r['npaper']} attrs_keys={keys} | {r['title'][:75]}")
con.close()
