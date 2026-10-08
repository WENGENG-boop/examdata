import sqlite3, os
from collections import Counter
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
con.row_factory = sqlite3.Row

q = "SELECT d.id, d.year, d.paper_code, d.title, d.status, d.current_revision_id, d.subject_id FROM document d WHERE d.doc_type='question_paper' AND d.board_id=2"
allqp = [dict(r) for r in con.execute(q).fetchall()]
zero = [r for r in allqp if con.execute("SELECT COUNT(*) FROM paper p JOIN question qq ON qq.paper_id=p.id WHERE p.document_id=?", (r['id'],)).fetchone()[0] == 0]
print(f"total Edexcel QP docs={len(allqp)}  zero-question={len(zero)}")

by_status = Counter(r['status'] for r in zero)
print("by status:", dict(by_status))

disc = [r for r in zero if r['status'] == 'discovered']
print("discovered by year:", dict(Counter(r['year'] for r in disc)))

stored = [r for r in zero if r['status'] == 'stored']
norev = [r for r in stored if not r['current_revision_id']]
revd = [r for r in stored if r['current_revision_id']]
print(f"stored: {len(stored)}  no-revision={len(norev)}  with-revision={len(revd)}")
print("stored no-rev by year:", dict(Counter(r['year'] for r in norev)))
print("stored no-rev by code:", dict(Counter((r['paper_code'] or '?') for r in norev)))

fails = []
for r in revd:
    rev = con.execute("SELECT parse_status, parse_error FROM document_revision WHERE id=?", (r['current_revision_id'],)).fetchone()
    if rev and rev['parse_status'] == 'failed':
        fails.append((r, rev['parse_error']))
print(f"failed parse: {len(fails)}")

subs = {}
for r in con.execute("SELECT id, slug FROM subject").fetchall():
    subs[r['id']] = r['slug']

noalt = []
for r, err in fails:
    alt = con.execute("""SELECT d.id, d.year, d.status, (SELECT COUNT(*) FROM paper p JOIN question qq ON qq.paper_id=p.id WHERE p.document_id=d.id) nq
        FROM document d WHERE d.paper_code=? AND d.id != ? AND d.doc_type='question_paper'""", (r['paper_code'], r['id'])).fetchall()
    good = [a for a in alt if a['nq'] > 0]
    if not good:
        noalt.append(r)
print(f"\nfailed with NO alternative parsed: {len(noalt)}")
c = Counter()
for r in noalt:
    c[(subs.get(r['subject_id']), (r['paper_code'] or '?').split('-')[0].lower(), r['year'])] += 1
for k in sorted(c, key=str):
    print(f"  {k}: {c[k]}")

# also: failed WITH alternative, by unit
withalt = [r for r, e in fails if r not in noalt]
print(f"\nfailed WITH alternative: {len(withalt)}")
c2 = Counter()
for r in withalt:
    c2[(subs.get(r['subject_id']), (r['paper_code'] or '?').split('-')[0].lower())] += 1
for k in sorted(c2, key=str):
    print(f"  {k}: {c2[k]}")
con.close()
