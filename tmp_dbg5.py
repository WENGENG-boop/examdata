"""Debug: why do 52674 / 52558 miss ref attribution."""
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
con = sqlite3.connect(f"file:{ROOT / '.data' / 'examdata.db'}?mode=ro", uri=True)
c = con.cursor()
c.execute('PRAGMA temp_store=MEMORY')

REF = re.compile(r'\((\d+\.\d+\.\d+\.\d+)\)')

def norm(s):
    s = (s or '').lower()
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()

def toks(s):
    return norm(s).split()

def strip_tail_digits(ts):
    while ts and ts[-1].isdigit():
        ts = ts[:-1]
    return ts

for target in (52674, 52558, 52673, 52672):
    row = c.execute("""
    select q.id, q.paper_id, q.number_label, q.stem_text, p.document_id, doc.year, doc.paper_code
    from question q join paper p on p.id=q.paper_id join document doc on doc.id=p.document_id
    where q.id=?""", (target,)).fetchone()
    if not row:
        print(f"{target}: NOT FOUND as question")
        continue
    qid, pid, num, stem, did, yr, pc = row
    print(f"\n### qid={qid} paper_id={pid} doc={did} {pc} {yr} #{num}")
    print(f"    stem_tail: {toks(stem)[-12:]}")

# find chunks containing (1.3.3.3)
print("\n=== chunks containing (1.3.3.3) ===")
rows = c.execute("""
select mse.question_id, q.paper_id, mse.answer_text, mse.guidance, doc.paper_code, doc.year, doc.id
from mark_scheme_entry mse
join question q on q.id = mse.question_id
join paper p on p.id = q.paper_id
join document d on d.id = p.document_id
join subject s on s.id = d.subject_id
join document doc on doc.id = p.document_id
where s.slug='ial-geography' and mse.question_id is not null
  and ((mse.answer_text like '%(1.3.3.3)%') or (mse.guidance like '%(1.3.3.3)%'))
""").fetchall()
for cqid, pid, ans, guid, pc, yr, did in rows:
    raw = (ans or '') + ' ' + (guid or '')
    for m in REF.finditer(raw):
        if m.group(1) != '1.3.3.3':
            continue
        ctx = norm(raw[:m.start()]).split()[-30:]
        print(f"chunk_qid={cqid} paper_id={pid} {pc} {yr} doc={did}")
        print(f"  ctx_tail: {ctx[-14:]}")
        # best matches in same paper
        qs = c.execute("""
        select q.id, q.number_label, q.stem_text from question q where q.paper_id=?""", (pid,)).fetchall()
        scored = []
        for sqid, snum, sstem in qs:
            st = strip_tail_digits(toks(sstem))
            k = 0
            lim = min(len(ctx), len(st), 30)
            while k < lim and ctx[-1-k] == st[-1-k]:
                k += 1
            if k >= 4:
                scored.append((k, sqid, snum))
        scored.sort(reverse=True)
        print(f"  same-paper candidates k>=4: {scored[:5]}")
        # also check global match: which question's stem tail matches ctx best
        allq = c.execute("""
        select q.id, q.paper_id, q.number_label, q.stem_text, doc.paper_code, doc.year
        from question q join paper p on p.id=q.paper_id join document doc on doc.id=p.document_id
        join subject s on s.id=doc.subject_id where s.slug='ial-geography'""").fetchall()
        gscored = []
        for gqid, gpid, gnum, gstem, gpc, gyr in allq:
            st = strip_tail_digits(toks(gstem))
            k = 0
            lim = min(len(ctx), len(st), 30)
            while k < lim and ctx[-1-k] == st[-1-k]:
                k += 1
            if k >= 6:
                gscored.append((k, gqid, gpid, gnum, gpc, gyr))
        gscored.sort(reverse=True)
        print(f"  global candidates k>=6: {gscored[:5]}")
