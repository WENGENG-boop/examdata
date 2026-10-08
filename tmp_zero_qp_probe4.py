import sqlite3, json, os
from collections import Counter
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
con.row_factory = sqlite3.Row

q = """
SELECT d.id, d.year, d.paper_code, d.title, d.status, d.current_revision_id
FROM document d WHERE d.doc_type='question_paper' AND d.board_id=2
"""
zero = [dict(r) for r in con.execute(q).fetchall()
        if con.execute("SELECT COUNT(*) FROM paper p JOIN question qq ON qq.paper_id=p.id WHERE p.document_id=?", (r['id'],)).fetchone()[0] == 0]
stored = [r for r in zero if r['status'] == 'stored']

fails = []
for r in stored:
    rev = con.execute("SELECT parse_status, parse_error, artifact_id, source_url FROM document_revision WHERE id=?", (r['current_revision_id'],)).fetchone()
    if rev and rev['parse_status'] == 'failed':
        fails.append((r, dict(rev)))

print(f"failed={len(fails)}")
c = Counter()
for r, rev in fails:
    pc = (r['paper_code'] or '').lower()
    unit = pc.split('-')[0] if '-' in pc else pc
    c[(unit, r['year'])] += 1
print("=== failed by unit x year ===")
for k in sorted(c):
    print(f"  {k[0]} {k[1]}: {c[k]}")

# check alternatives: same paper_code other documents that DID parse
print("\n=== alternative same-code docs parsed? ===")
for r, rev in fails[:15]:
    pc = r['paper_code']
    alt = con.execute("""
        SELECT d.id, d.year, d.status, (SELECT COUNT(*) FROM paper p JOIN question qq ON qq.paper_id=p.id WHERE p.document_id=d.id) nq
        FROM document d WHERE d.paper_code=? AND d.id != ?""", (pc, r['id'])).fetchall()
    alt_s = "; ".join(f"[{a['id']}]y{a['year']}{a['status']}nq={a['nq']}" for a in alt) or "NONE"
    print(f"  {pc} y{r['year']} -> alt: {alt_s}")

# artifact storage check
print("\n=== artifact disk check (sample 3) ===")
for r, rev in fails[:3]:
    art = con.execute("SELECT id, storage_key, kind, mime FROM artifact WHERE id=?", (rev['artifact_id'],)).fetchone()
    if art:
        sk = art['storage_key']
        found = []
        for base in ['.data', '.']:
            p = os.path.join(base, sk) if not os.path.isabs(sk) else sk
            if os.path.exists(p):
                found.append(p)
        print(f"  doc{r['id']} artifact={dict(art)} disk={found}")
    else:
        print(f"  doc{r['id']} artifact missing")
con.close()
