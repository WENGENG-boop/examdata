"""Review dump for ref-attribution mismatch candidates (ial-geography)."""
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
con = sqlite3.connect(f"file:{ROOT / '.data' / 'examdata.db'}?mode=ro", uri=True)
c = con.cursor()
c.execute('PRAGMA temp_store=MEMORY')

REF = re.compile(r'\((\d+\.\d+\.\d+\.\d+)\)')
FOOTER = re.compile(r'\(\s*Total\s+for\s+Question[^)]*\)', re.I)

MISMATCH = [52671, 52672, 52678, 52684, 52266, 52267, 52287, 52558, 52570, 52571,
            52171, 52176, 52180, 52181, 52182]


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
select q.id, q.paper_id, q.number_label, q.stem_text, q.marks
from question q
join paper p on p.id = q.paper_id
join document d on d.id = p.document_id
join subject s on s.id = d.subject_id
where s.slug = 'ial-geography'
""").fetchall()

by_paper = {}
qinfo = {}
for qid, pid, num, stem, marks in qs:
    by_paper.setdefault(pid, []).append((qid, num, stem_tokens(stem)))
    qinfo[qid] = (pid, num, stem, marks)

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

for target in MISMATCH:
    pid, num, stem, marks = qinfo[target]
    pc, yr = paper_doc[pid]
    labels = [r[0] for r in c.execute(
        "select tn.code from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id "
        "where qt.question_id=? order by tn.code", (target,))]
    print(f"\n{'='*100}")
    print(f"### q={target} #{num} m={marks} {pc} {yr} labels={labels}")
    print(f"STEM: {stem[:260]}")
    st = stem_tokens(stem)
    print(f"stem tail: {' '.join(st[-16:])}")
    # all occurrences in this paper where this qid is a candidate k>=5
    for cqid, raw in paper_ms.get(pid, []):
        for m in REF.finditer(raw):
            ctx = norm(raw[:m.start()]).split()[-40:]
            k = 0
            lim = min(len(ctx), len(st), 30)
            while k < lim and ctx[-1 - k] == st[-1 - k]:
                k += 1
            if k >= 5:
                cnum = qinfo.get(cqid, (None, '?', '', 0))[1]
                print(f"  occ in chunk={cqid}#{cnum}: ref=({m.group(1)}) k={k}")
                print(f"    ctx_tail: {' '.join(ctx[-24:])}")
                print(f"    after : {raw[m.end():m.end()+120]!r}")
