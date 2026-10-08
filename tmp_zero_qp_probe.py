import sqlite3, json
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
con.row_factory = sqlite3.Row

print("=== board table ===")
for r in con.execute("SELECT * FROM board LIMIT 10"):
    print(" ", dict(r))

# question_paper docs with 0 questions
q = """
SELECT d.id, d.year, d.paper_code, d.title, d.status, d.board_id, d.attrs,
       (SELECT COUNT(*) FROM paper p JOIN question qq ON qq.paper_id=p.id WHERE p.document_id=d.id) AS nq,
       (SELECT COUNT(*) FROM paper p WHERE p.document_id=d.id) AS npaper
FROM document d WHERE d.doc_type='question_paper'
"""
rows = con.execute(q).fetchall()
print(f"\ntotal QP docs: {len(rows)}")
zero = [r for r in rows if r['nq'] == 0]
print(f"0-question QP docs: {len(zero)}")
from collections import Counter
c_year = Counter(r['year'] for r in zero)
print("by year:", dict(sorted(c_year.items())))
c_status = Counter(r['status'] for r in zero)
print("by status:", dict(c_status))
c_board = Counter(r['board_id'] for r in zero)
print("by board_id:", dict(c_board))

# board id -> code map
bmap = {r['id']: r.get('code') for r in con.execute("SELECT * FROM board")}
print("boards:", bmap)

print("\n=== sample 0-q docs (first 40) ===")
for r in zero[:40]:
    attrs = r['attrs'] or '{}'
    try: a = json.loads(attrs)
    except: a = {}
    ps = a.get('parse_status') or a.get('status')
    print(f"  [{r['id']}] y={r['year']} {r['paper_code']} board={bmap.get(r['board_id'])} status={r['status']} npaper={r['npaper']} parse_status={ps} | {r['title'][:70]}")
con.close()
