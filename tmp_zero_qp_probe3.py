import sqlite3, json
from collections import Counter
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
con.row_factory = sqlite3.Row

q = """
SELECT d.id, d.year, d.paper_code, d.title, d.status, d.current_revision_id,
       (SELECT COUNT(*) FROM paper p JOIN question qq ON qq.paper_id=p.id WHERE p.document_id=d.id) AS nq
FROM document d WHERE d.doc_type='question_paper' AND d.board_id=2
"""
zero = [dict(r) for r in con.execute(q).fetchall() if r['nq'] == 0]
stored = [r for r in zero if r['status'] == 'stored']
disc = [r for r in zero if r['status'] == 'discovered']
print(f"stored={len(stored)} discovered={len(disc)}")

print("\n=== stored: revision parse_status ===")
c = Counter()
det = {}
for r in stored:
    rev = con.execute("SELECT parse_status, parse_error, source_url, status FROM document_revision WHERE id=?", (r['current_revision_id'],)).fetchone()
    key = (rev['status'], rev['parse_status']) if rev else ('NO_REV', None)
    c[key] += 1
    det.setdefault(key, []).append((r['id'], r['year'], r['paper_code'], (rev['parse_error'] or '')[:80] if rev else 'no-rev'))
for k, v in c.items():
    print(f"  {k}: {v}")
    for item in det[k][:6]:
        print("      ", item)

print("\n=== discovered: sample ===")
for r in disc[:8]:
    rev = con.execute("SELECT status, parse_status, source_url FROM document_revision WHERE id=?", (r['current_revision_id'],)).fetchone()
    print(f"  [{r['id']}] y={r['year']} {r['paper_code']} rev={dict(rev) if rev else None}")
con.close()
