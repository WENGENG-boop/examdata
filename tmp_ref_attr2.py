"""Attribute MS refs (x.y.z.w) to geography questions via suffix matching. v2.

Fixes vs v1:
- strip '(Total for Question N = M marks)' footer from stems before tokenizing
- lower candidate threshold to k>=5, report top candidates
- print ctx fragment (last 14 tokens before ref) for eyeballing
- flag node mismatch vs current label

Usage: python tmp_ref_attr2.py > tmp_ref_attr2.txt
"""
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
con = sqlite3.connect(f"file:{ROOT / '.data' / 'examdata.db'}?mode=ro", uri=True)
c = con.cursor()
c.execute('PRAGMA temp_store=MEMORY')

REF = re.compile(r'\((\d+\.\d+\.\d+\.\d+)\)')
FOOTER = re.compile(r'\(\s*Total\s+for\s+Question[^)]*\)', re.I)


def norm(s):
    s = (s or '').lower()
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def stem_tokens(s):
    s = FOOTER.sub(' ', s or '')
    ts = norm(s).split()
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
qinfo = {}
for qid, pid, num, stem in qs:
    by_paper.setdefault(pid, []).append((qid, num, stem_tokens(stem)))
    qinfo[qid] = (pid, num)

paper_doc = {}
for pid in by_paper:
    row = c.execute("select doc.year, doc.paper_code from paper p join document doc on doc.id=p.document_id where p.id=?", (pid,)).fetchone()
    paper_doc[pid] = (row[1], row[0])

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

occ = []
for pid, chunks in paper_ms.items():
    for cqid, raw in chunks:
        for m in REF.finditer(raw):
            ctx = norm(raw[:m.start()]).split()[-30:]
            occ.append((pid, cqid, m.group(1), ctx))

print(f'ref occurrences: {len(occ)}')

# per-question best attribution
best_per_q = {}
unattributed = []
for pid, cqid, ref, ctx in occ:
    cands = []
    for qid, num, st in by_paper.get(pid, []):
        if not st:
            continue
        k = 0
        lim = min(len(ctx), len(st), 30)
        while k < lim and ctx[-1 - k] == st[-1 - k]:
            k += 1
        if k >= 5:
            cands.append((k, qid, num))
    cands.sort(reverse=True)
    pc, yr = paper_doc[pid]
    if not cands:
        unattributed.append((pc, yr, cqid, ref, ctx))
        continue
    k, qid, num = cands[0]
    cur = best_per_q.get(qid)
    if cur is None or k > cur[0]:
        best_per_q[qid] = (k, ref, cqid, cands[1:4], pc, yr)

print(f'\nattributed questions: {len(best_per_q)}  unattributed occurrences: {len(unattributed)}')

# group by paper
papers = {}
for qid, (k, ref, cqid, alts, pc, yr) in best_per_q.items():
    papers.setdefault((pc, yr), []).append((qid, k, ref, cqid, alts))

for (pc, yr), items in sorted(papers.items()):
    print(f"\n===== {pc} {yr} =====")
    for qid, k, ref, cqid, alts in sorted(items):
        labels = [r[0] for r in c.execute(
            "select tn.code from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id "
            "where qt.question_id=? order by tn.code", (qid,))]
        num = qinfo[qid][1]
        node = '.'.join(ref.split('.')[:3])
        labnodes = [l.split('-')[-1] for l in labels]
        flag = '' if node in labnodes else '  <<< MISMATCH'
        alt_s = '; '.join(f'k={k2} q={q2}#{n2}' for k2, q2, n2 in alts)
        print(f"q={qid} #{num} label={labels} ref=({ref})->{node} k={k} chunk={cqid}{flag}")
        if alt_s:
            print(f"      alts: {alt_s}")

# unattributed occurrences with context
print('\n\n########## UNATTRIBUTED ##########')
for pc, yr, cqid, ref, ctx in unattributed:
    cnum = qinfo.get(cqid, (None, '?'))[1]
    print(f"\n{pc} {yr} chunk={cqid}#{cnum} ref=({ref})")
    print(f"    ctx_tail: {' '.join(ctx[-18:])}")
