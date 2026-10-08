"""WME01 r2 probe: dump full stems + MS + code listings for suspect qids (read-only, retries)."""
import re
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = Path(__file__).resolve().parent / 'wme01_probe.txt'
log = open(OUT, 'w', encoding='utf-8')


def q(sql, args=()):
    last = None
    for i in range(60):
        try:
            con = sqlite3.connect(f'file:{ROOT / ".data" / "examdata.db"}?mode=ro',
                                  uri=True, timeout=30)
            try:
                return con.execute(sql, args).fetchall()
            finally:
                con.close()
        except sqlite3.OperationalError as e:
            last = e
            time.sleep(6)
    raise SystemExit(f'db fail {last}')


def p(*a):
    print(*a, file=log, flush=True)


BOILER = re.compile(r'(leave blank|question \d+ continued|do not write|total \d+ marks|turn over|_+)')


def norm(t):
    t = (t or '').lower()
    t = BOILER.sub(' ', t)
    t = re.sub(r'[^a-z0-9]+', ' ', t)
    return ' '.join(t.split())


def dump(qid, full=True):
    row = q('select id, parent_id, number_label, marks, stem_text from question where id=?',
            (qid,))
    if not row:
        p(f'Q {qid} NOT FOUND'); return
    r = row[0]
    p(f'===== Q {r[0]} parent={r[1]} #{r[2]} {r[3]}mk')
    if full:
        p((r[4] or '')[:1400])
    for ms in q('select number_path, answer_text from mark_scheme_entry where question_id=? order by id limit 8',
                (qid,)):
        p(f'  MS[{ms[0]}]: {(ms[1] or "")[:700]}')
    p('')


def listing(code_like):
    rows = q('''select q.id, q.parent_id, tn.code, q.stem_text from question q
      join question_taxonomy qt on qt.question_id=q.id join taxonomy_node tn on tn.id=qt.node_id
      where tn.code like ? and q.stem_text is not null order by q.id''', (code_like,))
    p(f'##### LISTING {code_like}: {len(rows)}')
    for qid, par, cd, stem in rows:
        ns = norm(stem)
        p(f'  {qid} p={par} [{cd}] {ns[:115]}')
    p('')


p('### families')
for qid in (56799, 60535, 60534, 57834, 57835, 57836, 60086, 60084, 60085,
            57837, 58823, 58822, 60678, 60675, 60676, 57943, 57944, 57945,
            57550, 60525, 60526, 60527, 60536, 60537, 60538, 60539, 60540,
            58537, 58538, 58539, 56809, 56810, 56811):
    dump(qid)

p('### 5.2 vs 5.3')
listing('WME01-5.2')
listing('WME01-5.3')
p('### 4.4 listing')
listing('WME01-4.4')
p('### 4.3 sample (first 15)')
rows = q('''select q.id, tn.code, q.stem_text from question q
  join question_taxonomy qt on qt.question_id=q.id join taxonomy_node tn on tn.id=qt.node_id
  where tn.code='WME01-4.3' and q.stem_text is not null order by q.id limit 15''')
for qid, cd, stem in rows:
    p(f'  {qid} [{cd}] {norm(stem)[:110]}')

log.close()
print('done ->', OUT)
