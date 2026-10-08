import sqlite3, re, collections
con = sqlite3.connect('.data/examdata.db'); con.row_factory = sqlite3.Row
cur = con.cursor()

def norm(s): return re.sub(r'\s+', ' ', s or '').strip()

rows = cur.execute("""
SELECT q.id, q.paper_id, p.paper_no, q.kind, q.number_path, q.stem_text, q.display_order
FROM question q JOIN paper p ON p.id=q.paper_id
WHERE q.stem_text LIKE '%Total for Question%'
ORDER BY q.paper_id, q.display_order
""").fetchall()

# build children map
kids = collections.defaultdict(list)
allq = {}
for r in cur.execute("SELECT id, paper_id, parent_id, number_path, stem_text FROM question WHERE stem_text IS NOT NULL"):
    allq[r['id']] = r
    if r['parent_id']: kids[r['parent_id']].append(r['id'])

severe = []
light = []
for r in rows:
    stem = r['stem_text'] or ''
    own = r['number_path'] or ''
    m = re.match(r'^(\d+)', own)
    if not m: continue
    ownN = int(m.group(1))
    nstem = norm(stem)
    markers = [(int(t.group(1)), t.start()) for t in re.finditer(r'Total for Question (\d+)', nstem)]
    others = [(M, pos) for M, pos in markers if M != ownN]
    if not others: continue
    first_other = min(others, key=lambda x: x[1])
    # check descendants (children of this node) positions
    before = []
    for cid in kids.get(r['id'], []):
        cstem = norm(allq[cid]['stem_text'])
        if not cstem: continue
        pos = nstem.find(cstem)
        if pos == -1: pos = None
        if pos is not None and pos < first_other[1]:
            before.append((cid, allq[cid]['number_path'], pos))
    rec = dict(id=r['id'], paper=r['paper_id'], paper_no=r['paper_no'], kind=r['kind'], path=own, ownN=ownN,
               markers=markers, first_other=first_other, before=before, stemlen=len(nstem))
    if before:
        severe.append(rec)
    else:
        light.append(rec)

print(f"TOTAL flagged: {len(severe)+len(light)}; SEVERE nodes: {len(severe)} in papers: {len({s['paper'] for s in severe})}; LIGHT: {len(light)}")
print("\n### SEVERE (kids text before previous-total marker -> sub-parts likely belong to previous question) ###")
byp = collections.defaultdict(list)
for s in severe: byp[s['paper']].append(s)
for pid, lst in sorted(byp.items()):
    print(f"\n-- paper {pid} {lst[0]['paper_no']} ({len(lst)} severe nodes)")
    for s in lst:
        print(f"   q={s['id']} {s['kind']} {s['path']} markers={s['markers'][:5]} before={s['before'][:8]}")
print("\n### LIGHT count by paper (top 20) ###")
lp = collections.Counter(l['paper'] for l in light)
for pid, c in lp.most_common(20):
    r = cur.execute("SELECT paper_no FROM paper WHERE id=?", (pid,)).fetchone()
    print(f"  paper={pid} {r['paper_no']}: {c}")

import json
json.dump({'severe': severe, 'light': light}, open('tmp_r8_classify.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)
print("\nsaved tmp_r8_classify.json")
con.close()
