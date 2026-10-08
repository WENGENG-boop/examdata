import re, sqlite3
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

def toks(s): return norm(s).split()
def strip_tail_digits(ts):
    while ts and ts[-1].isdigit(): ts = ts[:-1]
    return ts

# 2022 paper questions
pid = c.execute("""select p.id from paper p join document d on d.id=p.document_id join subject s on s.id=d.subject_id
where s.slug='ial-geography' and d.paper_code='wge01-01' and d.year=2022 and d.identity_key like 'f7c524%'""").fetchone()[0]
qs = c.execute("select id, number_label, stem_text from question where paper_id=?", (pid,)).fetchall()
qinfo = {q: (n, strip_tail_digits(toks(s))) for q, n, s in qs}

# find all (1.3.3.3) occurrences in 2022 MS chunks
ms = c.execute("""select mse.question_id, mse.answer_text from mark_scheme_entry mse join question q on q.id=mse.question_id
where q.paper_id=?""", (pid,)).fetchall()
for cqid, raw in ms:
    for m in REF.finditer(raw or ''):
        if m.group(1) != '1.3.3.3': continue
        ctx = norm(raw[:m.start()]).split()[-30:]
        print(f"--- ref 1.3.3.3 in chunk {cqid}; ctx tail: {' '.join(ctx[-14:])}")
        scores = []
        for q, (n, st) in qinfo.items():
            if not st: continue
            k = 0; lim = min(len(ctx), len(st), 30)
            while k < lim and ctx[-1-k] == st[-1-k]: k += 1
            if k >= 4: scores.append((k, q, n))
        for k, q, n in sorted(scores, reverse=True)[:6]:
            print(f"     k={k} {q} #{n} stem tail: {' '.join(qinfo[q][1][-14:])}")
