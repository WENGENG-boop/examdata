import sqlite3, re, collections, json
con = sqlite3.connect('.data/examdata.db'); con.row_factory = sqlite3.Row
cur = con.cursor()

rows = cur.execute("""
SELECT q.id, q.paper_id, p.paper_no, p.document_id, q.kind, q.number_label, q.number_path, q.marks, q.stem_text, q.display_order
FROM question q JOIN paper p ON p.id=q.paper_id
WHERE q.stem_text LIKE '%Total for Question%'
ORDER BY q.paper_id, q.display_order
""").fetchall()

flagged = []
for r in rows:
    stem = r['stem_text'] or ''
    totals = re.findall(r'Total for Question (\d+)', stem)
    own = r['number_path'] or ''
    m = re.match(r'^(\d+)', own)
    if not m: continue
    ownN = int(m.group(1))
    other = sorted({int(t) for t in totals if int(t) != ownN})
    if other:
        flagged.append((r, ownN, totals, other))

print("flagged nodes:", len(flagged), "papers:", len({f[0]['paper_id'] for f in flagged}))
by_paper = collections.Counter()
for r, ownN, totals, other in flagged:
    by_paper[r['paper_id']] += 1
    kids = cur.execute("SELECT number_path FROM question WHERE parent_id=? ORDER BY display_order", (r['id'],)).fetchall()
    kp = [k['number_path'] for k in kids]
    kidN = sorted({int(re.match(r'^(\d+)', p).group(1)) for p in kp if re.match(r'^(\d+)', p)})
    kind = 'PREV' if any(t < ownN for t in other) else 'NEXT'
    print(f"{kind} q={r['id']} paper={r['paper_id']} {r['paper_no']} own={ownN} totals={totals} other={other} kidsN={kidN} kids={kp[:9]}{'...' if len(kp)>9 else ''}")

print("\nper-paper counts:")
for pid, c in sorted(by_paper.items()):
    r = cur.execute("SELECT paper_no, document_id FROM paper WHERE id=?", (pid,)).fetchone()
    print(f"  paper={pid} {r['paper_no']} doc={r['document_id']}: {c}")
con.close()
