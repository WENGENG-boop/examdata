"""WME02 final evidence batch 3: KE-lost full list, children of 58695/58526/40735/59876, stems 40735/35681/59877/59271, MS for 59873-75/59877/58527/58528/58696/58697."""
import re
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / 'wme02_q3.txt'
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


# 1) full 'kinetic energy lost' list
p('##### KE LOST FULL LIST')
rows = q("""select q.id, tn.code, q.stem_text from question q
    join question_taxonomy qt on qt.question_id=q.id
    join taxonomy_node tn on tn.id=qt.node_id
    where tn.code like 'WME02-%' and q.stem_text like '%kinetic energy lost%' order by q.id""")
for qid, cd, stem in rows:
    p(f'  {qid} [{cd}] {norm(stem)[:150]}')
p('')

# 2) children labels
p('##### CHILDREN')
for root in (58695, 58526, 40735, 59876):
    for r in q("""select q.id, q.number_label, q.parent_id, coalesce(tn.code,'-'),
        substr(replace(q.stem_text,char(10),' '),1,140)
        from question q left join question_taxonomy qt on qt.question_id=q.id
        left join taxonomy_node tn on tn.id=qt.node_id
        where q.parent_id=? order by q.id""", (root,)):
        p(f'  {r[0]} p={r[2]} #{r[1]} [{r[3]}] {r[4]}')
    p('')

# 3) stems
p('##### STEMS')
for qid in (40735, 35681, 59877, 59876, 59271, 58527, 58696, 58697):
    r = q("select replace(stem_text,char(10),' ') from question where id=?", (qid,))
    if r:
        p(f'-- {qid}: {r[0][0][:700]}')
    else:
        p(f'-- {qid}: NOT FOUND')
    p('')

# 4) MS
p('##### MS')
for qid in (59873, 59874, 59875, 59877, 58527, 58528, 58696, 58697, 40735, 35681):
    ms = q("""select number_path, marks, replace(answer_text,char(10),' | ')
        from mark_scheme_entry where question_id=? order by id limit 4""", (qid,))
    p(f'-- MS {qid}:')
    for path, mk, txt in ms:
        p(f'   [{path}] {mk}mk: {txt[:500]}')
    p('')

log.close()
print('done ->', OUT)
