"""Parents check with ans override layer: final labels = pack cur overridden by ans file.

usage: python tmp_r2_parents2.py pack1 ans1 pack2 ans2 ...
"""
import sqlite3, sys, re
from pathlib import Path
from collections import Counter

con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
c = con.cursor()

def codes(qid):
    r = c.execute("""SELECT tn.code FROM question_taxonomy qt JOIN taxonomy_node tn ON tn.id=qt.node_id
                     WHERE qt.question_id=?""", (qid,)).fetchall()
    return [x[0] for x in r]

def total_marks(qid, depth=0):
    r = c.execute("SELECT marks FROM question WHERE id=?", (qid,)).fetchone()
    m = r[0] or 0
    kids = c.execute("SELECT id FROM question WHERE parent_id=?", (qid,)).fetchall()
    if kids and depth < 3:
        km = sum(total_marks(k[0], depth+1) for k in kids)
        return km if km else m
    return m

pairs = list(zip(sys.argv[1::2], sys.argv[2::2]))
final = {}
packs = {}
for packpath, anspath in pairs:
    pack = Path(packpath)
    cur, order = {}, []
    for ln in pack.read_text(encoding='utf-8').splitlines():
        m = re.match(r'^\[(\d+)\]\s+(\d+)\s+#(\S+)\s+(\S+)mk\s+cur=(\S+)', ln)
        if m:
            q = int(m.group(2)); cur[q] = m.group(5); order.append(q)
    packs[pack.name] = (order, cur)
    final.update(cur)
    for ln in Path(anspath).read_text(encoding='utf-8').splitlines():
        p = ln.split()
        if len(p) == 2 and p[0].isdigit() and p[1] != 'OK':
            final[int(p[0])] = p[1]

for name, (order, cur) in packs.items():
    print(f'#### {name}')
    for q in order:
        kids = c.execute("SELECT id, number_label FROM question WHERE parent_id=? ORDER BY id", (q,)).fetchall()
        if not kids:
            continue
        votes = Counter(); detail = []
        for k in kids:
            km = total_marks(k[0])
            kl = [final[k[0]]] if k[0] in final else codes(k[0])
            detail.append(f'{k[0]} #{k[1]} {km}mk {kl}')
            for x in kl:
                votes[x] += km
        maj = votes.most_common()
        exp = maj[0][0] if maj else '?'
        if len(maj) > 1 and maj[0][1] == maj[1][1]:
            first = kids[0][0]
            fl = [final[first]] if first in final else codes(first)
            exp = fl[0] if fl else '?'
        curf = final.get(q, cur.get(q))
        flag = '' if exp == curf else '  <<< MISMATCH'
        print(f'  {q} final={curf} exp={exp}{flag}')
        for d in detail:
            print(f'      {d}')
