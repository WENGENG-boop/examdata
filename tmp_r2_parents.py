"""For each parent row in given packs: show children (with labels/marks) and majority-rule expectation."""
import sqlite3, sys, re
from pathlib import Path
from collections import Counter

con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
c = con.cursor()

def code(qid):
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

for packpath in sys.argv[1:]:
    pack = Path(packpath)
    qids = []
    cur = {}
    for ln in pack.read_text(encoding='utf-8').splitlines():
        m = re.match(r'^\[(\d+)\]\s+(\d+)\s+#(\S+)\s+(\S+)mk\s+cur=(\S+)', ln)
        if m:
            qids.append(int(m.group(2)))
            cur[int(m.group(2))] = m.group(5)
    print(f'#### {pack.name}')
    for q in qids:
        kids = c.execute("SELECT id, number_label FROM question WHERE parent_id=? ORDER BY id", (q,)).fetchall()
        if not kids:
            continue
        votes = Counter()
        detail = []
        for k in kids:
            km = total_marks(k[0])
            kl = code(k[0])
            detail.append(f'{k[0]} #{k[1]} {km}mk {kl}')
            for x in kl:
                votes[x] += km
        maj = votes.most_common()
        exp = maj[0][0] if maj else '?'
        if len(maj) > 1 and maj[0][1] == maj[1][1]:
            # tie: first part's label
            first = kids[0][0]
            fl = code(first)
            exp = fl[0] if fl else '?'
        flag = '' if exp == cur[q] else '  <<< MISMATCH'
        print(f'  {q} cur={cur[q]} exp={exp}{flag}')
        for d in detail:
            print(f'      {d}')
