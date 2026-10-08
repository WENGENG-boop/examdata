"""WME02 targeted evidence batch: listings for 1.3/1.4/5.1/5.2 + children labels + keyword precedents."""
import re
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / 'wme02_evidence.txt'
BOILER = re.compile(r'(leave blank|question \d+ continued|do not write|total \d+ marks|turn over|_+)')


def norm(t):
    t = (t or '').lower()
    t = BOILER.sub(' ', t)
    t = re.sub(r'[^a-z0-9]+', ' ', t)
    return ' '.join(t.split())


def q(sql, args=()):
    last = None
    for i in range(80):
        try:
            con = sqlite3.connect(f'file:{ROOT / ".data" / "examdata.db"}?mode=ro',
                                  uri=True, timeout=30)
            try:
                return con.execute(sql, args).fetchall()
            finally:
                con.close()
        except sqlite3.OperationalError as e:
            last = e
            time.sleep(5)
    raise SystemExit(f'db fail {last}')


log = open(OUT, 'w', encoding='utf-8')


def p(*a):
    print(*a, file=log, flush=True)


# 1) listings for 1.3 / 1.4 / 5.1 / 5.2
for code in ('WME02-1.3', 'WME02-1.4', 'WME02-5.1', 'WME02-5.2'):
    p(f'##### {code}')
    for qid, par, num, stem in q('''select q.id, q.parent_id, q.number_label, q.stem_text
        from question q join question_taxonomy qt on qt.question_id=q.id
        join taxonomy_node tn on tn.id=qt.node_id where tn.code=? order by q.id''', (code,)):
        p(f'  {qid} p={par} #{num} | {norm(stem)[:130]}')
    p('')

# 2) children of specific qids with labels
p('##### CHILDREN LABELS')
for root in (60262, 57960, 59873, 58514, 58520, 57118, 59697, 59271, 58525, 58694, 57967, 57474):
    rows = q('''select q.id, q.number_label, q.parent_id, tn.code, substr(replace(q.stem_text,char(10),' '),1,80)
        from question q left join question_taxonomy qt on qt.question_id=q.id
        left join taxonomy_node tn on tn.id=qt.node_id
        where q.parent_id=? order by q.id''', (root,))
    p(f'-- root {root}:')
    for r in rows:
        p(f'   {r[0]} p={r[2]} #{r[1]} [{r[3]}] {r[4]}')

# 3) keyword scans across WME02-labeled candidates
p('##### KEYWORD SCANS')
for kw in ('wire', 'horizontal force', 'kinetic energy lost', 'gain in kinetic', 'freely suspended'):
    rows = q('''select q.id, tn.code, q.stem_text from question q
        join question_taxonomy qt on qt.question_id=q.id
        join taxonomy_node tn on tn.id=qt.node_id
        where tn.code like 'WME02-%' and q.stem_text is not null''')
    hits = [(qid, cd) for qid, cd, stem in rows if norm(kw) in norm(stem)]
    from collections import Counter
    p(f'-- kw {kw!r}: {len(hits)} hits; {dict(Counter(c for _, c in hits).most_common(8))}')
    for qid, cd in hits[:12]:
        stem = next(s for i, c, s in rows if i == qid)
        p(f'   {qid} [{cd}] {norm(stem)[:110]}')

log.close()
print('done ->', OUT)
