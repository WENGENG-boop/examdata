import sqlite3, json, re
con = sqlite3.connect('.data/examdata.db')
con.row_factory = sqlite3.Row
cur = con.cursor()

def norm(s):
    return re.sub(r'\s+', ' ', s or '').strip()

print("=== A. overlap test p1351 ===")
stems = {r['id']: r['stem_text'] or '' for r in cur.execute("SELECT id, stem_text FROM question WHERE paper_id=1351")}
n05 = norm(stems[45905]); n13 = norm(stems[45913])
for cid in (45906,45907,45908,45909,45910,45911,45912):
    ns = norm(stems[cid]); print(f"child {cid} in 45905: {ns in n05} (len {len(ns)})")
for cid in (45914,45915,45916,45917,45918,45919,45920):
    ns = norm(stems[cid]); print(f"child {cid} in 45913: {ns in n13} (len {len(ns)})")

print("\n=== B. overlap test on other papers (question node vs children) ===")
for pid in (1397, 2162, 782, 1197, 889, 1572, 1927):
    rows = cur.execute("SELECT id,parent_id,kind,number_path,stem_text FROM question WHERE paper_id=?", (pid,)).fetchall()
    d = {r['id']: r for r in rows}
    kids = {}
    for r in rows:
        if r['parent_id']: kids.setdefault(r['parent_id'], []).append(r)
    cnt_contain = 0; cnt_total = 0
    for qid, r in d.items():
        if r['kind'] == 'question' and qid in kids:
            cnt_total += 1
            allin = all(norm(k['stem_text']) in norm(r['stem_text']) for k in kids[qid] if norm(k['stem_text']))
            if allin: cnt_contain += 1
    print(f"paper {pid}: question nodes with children={cnt_total}, all-children-contained={cnt_contain}")

print("\n=== C. all flagged H1 nodes (stem contains Total for Question M) ===")
rows = cur.execute("""
SELECT q.id, q.paper_id, p.paper_no, d.slug, q.kind, q.number_label, q.number_path, q.marks, q.stem_text
FROM question q JOIN paper p ON p.id=q.paper_id JOIN document d ON d.id=p.document_id
WHERE q.kind='question' AND q.stem_text LIKE '%Total for Question%'
ORDER BY q.paper_id, q.display_order
""").fetchall()
print("count:", len(rows))
import collections
by_paper = collections.Counter()
for r in rows:
    stem = r['stem_text'] or ''
    totals = re.findall(r'Total for Question (\d+)', stem)
    kids = cur.execute("SELECT number_path FROM question WHERE parent_id=?", (r['id'],)).fetchall()
    kp = [k['number_path'] for k in kids]
    own = r['number_path']
    prev_totals = [t for t in totals if t.isdigit() and int(t) < int(re.sub(r'\D','',own) or 0)]
    by_paper[r['slug']] += 1
    flag = "PREV" if prev_totals else "     "
    print(f"{flag} q={r['id']} paper={r['paper_id']} {r['slug']} {r['paper_no']} label={own!r} marks={r['marks']} kids={kp[:8]}{'...' if len(kp)>8 else ''} totals={totals[:4]} stemlen={len(stem)}")
print("\nby paper:", dict(by_paper))
con.close()
