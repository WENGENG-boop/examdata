"""Attribute MS refs (x.y.z.w) to geography questions via suffix matching.

For each ref occurrence: take the ~30 tokens before it; for each question in
the same paper, check the longest common suffix between those context tokens
and the question's stem tokens (trailing numeric tokens stripped). Attribute
the ref to the question with the longest suffix match (>= 6 tokens).

Usage: python tmp_ref_attr.py > tmp_ref_attr.txt
"""
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
con = sqlite3.connect(f"file:{ROOT / '.data' / 'examdata.db'}?mode=ro", uri=True)
c = con.cursor()
c.execute('PRAGMA temp_store=MEMORY')

REF = re.compile(r'\((\d+\.\d+\.\d+\.\d+)\)')


def norm(s: str) -> str:
    s = (s or '').lower()
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def toks(s: str):
    return norm(s).split()


def strip_tail_digits(ts):
    while ts and ts[-1].isdigit():
        ts = ts[:-1]
    return ts


qs = c.execute("""
select q.id, q.paper_id, q.number_label, q.stem_text
from question q
join paper p on p.id = q.paper_id
join document d on d.id = p.document_id
join subject s on s.id = d.subject_id
where s.slug = 'ial-geography'
""").fetchall()

by_paper = {}
for qid, pid, num, stem in qs:
    by_paper.setdefault(pid, []).append((qid, num, strip_tail_digits(toks(stem))))

ms_rows = c.execute("""
select q.paper_id, mse.question_id, mse.answer_text, mse.guidance
from mark_scheme_entry mse
join question q on q.id = mse.question_id
join paper p on p.id = q.paper_id
join document d on d.id = p.document_id
join subject s on s.id = d.subject_id
where s.slug = 'ial-geography' and mse.question_id is not null
""").fetchall()

paper_ms = {}
for pid, qid, ans, guid in ms_rows:
    paper_ms.setdefault(pid, []).append((qid, (ans or '') + ' ' + (guid or '')))

# ref occurrences: (paper_id, chunk_qid, ref, context_tokens)
occ = []
for pid, chunks in paper_ms.items():
    for cqid, raw in chunks:
        for m in REF.finditer(raw):
            ctx = norm(raw[:m.start()]).split()[-30:]
            occ.append((pid, cqid, m.group(1), ctx))

print(f'ref occurrences: {len(occ)}')
attr = {}
for pid, cqid, ref, ctx in occ:
    best = None
    for qid, num, st in by_paper.get(pid, []):
        if not st:
            continue
        k = 0
        lim = min(len(ctx), len(st), 30)
        while k < lim and ctx[-1 - k] == st[-1 - k]:
            k += 1
        if k >= 6 and (best is None or k > best[1]):
            best = (qid, k, num)
    if best:
        key = best[0]
        attr.setdefault(key, {}).setdefault(ref, {'k': best[1], 'chunks': set()})['chunks'].add(cqid)

# report
for pid in sorted({p for p in by_paper}):
    items = [(qid, d) for qid, d in attr.items() if qid in {q for q, _, _ in by_paper.get(pid, [])}]
    if not items:
        continue
    d = c.execute("select doc.year, doc.paper_code from paper p join document doc on doc.id=p.document_id where p.id=?", (pid,)).fetchone()
    print(f"\n=== paper {d[1]} {d[0]} ===")
    for qid, refs in sorted(items):
        labels = [r[0] for r in c.execute(
            "select tn.code from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id "
            "where qt.question_id=? order by tn.code", (qid,))]
        num = next(n for q, n, _ in by_paper[pid] if q == qid)
        print(f"{qid} #{num} labels={labels}")
        for ref, info in sorted(refs.items()):
            node = '.'.join(ref.split('.')[:3])
            print(f"    ref=({ref}) -> {node}  k={info['k']} chunks={sorted(info['chunks'])}")
