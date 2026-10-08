"""Build qid -> root-parent map for the ial-french unt batch, dump per-group info."""
from __future__ import annotations

import glob
import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
con = sqlite3.connect(ROOT / '.data' / 'examdata.db')
cur = con.cursor()

rows = []
for f in sorted(glob.glob(str(ROOT / 'tmp_jev_untagged_batches' / 'ial-french' / 'batches' / 'batch-*.jsonl'))):
    for line in open(f, encoding='utf-8'):
        rec = json.loads(line)
        rows.append(rec)
print('batch rows:', len(rows))

qids = [r['question_id'] for r in rows]
qid_set = set(qids)
assert len(qid_set) == len(qids), 'dup qid in batch'

# fetch parent_id for all qids
qmark = ','.join('?' * len(qids))
cur.execute(f'select id, parent_id, number_label, marks, display_order, paper_id from question where id in ({qmark})', qids)
info = {r[0]: {'parent': r[1], 'label': r[2], 'marks': r[3], 'order': r[4], 'paper': r[5]} for r in cur.fetchall()}
missing = [q for q in qids if q not in info]
print('missing from question table:', missing)

# follow parent chain to root
def root_of(q):
    seen = []
    cur_q = q
    while True:
        p = info.get(cur_q, {}).get('parent')
        if p is None:
            # parent not in batch; fetch from DB
            cur.execute('select id, parent_id from question where id = ?', (cur_q,))
            r = cur.fetchone()
            if r is None:
                return cur_q, seen
            if r[1] is None:
                return cur_q, seen
            seen.append(cur_q)
            cur_q = r[1]
        else:
            seen.append(cur_q)
            cur_q = p

groups = defaultdict(list)
for q in qids:
    r, chain = root_of(q)
    groups[r].append(q)

print('n groups:', len(groups))
out = []
for r in sorted(groups):
    gq = sorted(groups[r])
    cur.execute('select number_label, marks from question where id = ?', (r,))
    lab, mk = cur.fetchone()
    cur.execute('''select tn.code from question_taxonomy qt join taxonomy_node tn on tn.id = qt.node_id
                   where qt.question_id = ?''', (r,))
    tags = [x[0] for x in cur.fetchall()]
    cur.execute('select attrs from question where id = ?', (r,))
    out.append(f'root={r} label={lab!r} marks={mk} n={len(gq)} in_batch={r in qid_set} tags={tags} range=[{gq[0]}..{gq[-1]}]')
    out.append('    ' + ' '.join(str(x) for x in gq))
Path(ROOT / 'tmp_fr_map.txt').write_text('\n'.join(out) + '\n', encoding='utf-8')
print('written tmp_fr_map.txt')
