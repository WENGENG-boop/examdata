import sqlite3, json, os
from collections import Counter, defaultdict
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
con.row_factory = sqlite3.Row
print("artifact cols:", [r[1] for r in con.execute('PRAGMA table_info(artifact)')])
print("subject cols:", [r[1] for r in con.execute('PRAGMA table_info(subject)')])

# failed QP docs
q = """
SELECT d.id, d.year, d.paper_code, d.title, d.status, d.current_revision_id, d.subject_id
FROM document d WHERE d.doc_type='question_paper' AND d.board_id=2
"""
zero = []
for r in con.execute(q).fetchall():
    nq = con.execute("SELECT COUNT(*) FROM paper p JOIN question qq ON qq.paper_id=p.id WHERE p.document_id=?", (r['id'],)).fetchone()[0]
    if nq == 0:
        zero.append(dict(r))
stored = [r for r in zero if r['status'] == 'stored']

subs = {r['id']: r['slug'] for r in con.execute("SELECT id, slug FROM subject")}
fails = []
for r in stored:
    rev = con.execute("SELECT parse_status, parse_error, artifact_id FROM document_revision WHERE id=?", (r['current_revision_id'],)).fetchone()
    if rev and rev['parse_status'] == 'failed':
        fails.append((r, dict(rev)))

# alternative parsed docs for same paper_code
print("\n=== failed docs with alternatives (same code, QP, nq>0) ===")
noalt = []
for r, rev in fails:
    alt = con.execute("""SELECT d.id, d.year, d.status,
        (SELECT COUNT(*) FROM paper p JOIN question qq ON qq.paper_id=p.id WHERE p.document_id=d.id) nq
        FROM document d WHERE d.paper_code=? AND d.id != ? AND d.doc_type='question_paper'""", (r['paper_code'], r['id'])).fetchall()
    good = [a for a in alt if a['nq'] > 0]
    if good:
        print(f"  {r['paper_code']} y{r['year']} [{r['id']}] -> alt good: {[(a['id'], a['year'], a['nq']) for a in good]}")
    else:
        noalt.append(r)
print(f"\nfailed with NO alternative: {len(noalt)}")
for r in noalt:
    print(f"  [{r['id']}] {r['paper_code']} y{r['year']} subj={subs.get(r['subject_id'])} | {r['title'][:70]}")

# artifact disk check
print("\n=== artifact disk check (first 5 failed) ===")
for r, rev in fails[:5]:
    art = con.execute("SELECT id, storage_key, sha256 FROM artifact WHERE id=?", (rev['artifact_id'],)).fetchone()
    if art:
        sk = art['storage_key']
        cands = [sk, os.path.join('.data', sk), os.path.join('.data', 'artifacts', sk)]
        found = [p for p in cands if os.path.exists(p)]
        print(f"  doc{r['id']} key={sk[:60]} disk={found}")
con.close()
