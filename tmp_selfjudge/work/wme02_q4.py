"""Mixed-family precedent: WME02 parents whose children span 2.x and 5.x codes."""
import re
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / 'wme02_q4.txt'


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


# all WME02 questions that have children; list parent code + children codes
rows = q("""select p.id, coalesce(pn.code,'-'), c.id, coalesce(cn.code,'-'), c.number_label
    from question p
    join question c on c.parent_id = p.id
    left join question_taxonomy pt on pt.question_id = p.id
    left join taxonomy_node pn on pn.id = pt.node_id
    left join question_taxonomy ct on ct.question_id = c.id
    left join taxonomy_node cn on cn.id = ct.node_id
    where pn.code like 'WME02-%'
    order by p.id, c.id""")
from collections import defaultdict
fam = defaultdict(lambda: {'pcode': set(), 'kids': []})
for pid, pcode, cid, ccode, num in rows:
    fam[pid]['pcode'].add(pcode)
    fam[pid]['kids'].append((cid, ccode, num))

p('##### FAMILIES WITH CHILDREN (WME02)')
mixed = []
for pid, d in sorted(fam.items()):
    codes = {cc for _, cc, _ in d['kids'] if cc != '-'}
    groups = {c.split('-')[1][0] for c in codes if c != '-'}
    pcs = '/'.join(sorted(d['pcode']))
    kidstr = ' '.join(f"{cid}[{cc}]{num}" for cid, cc, num in d['kids'])
    mark = ''
    if len(groups) > 1:
        mark = '  <== MIXED'
        mixed.append((pid, pcs, kidstr))
    p(f'  P{pid} [{pcs}] :: {kidstr}{mark}')
p('')
p('##### MIXED FAMILIES ONLY')
for pid, pcs, kidstr in mixed:
    p(f'  P{pid} [{pcs}] :: {kidstr}')

log.close()
print('done ->', OUT)
