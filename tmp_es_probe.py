"""Probe: pack qids -> (paper_id, number_path) mapping + point codes for ial-spanish."""
import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PACKS = ['WSP02-p01', 'WSP02-p02', 'WSP02-p03', 'WSP02-p04', 'WSP04-p01']
QID_RE = re.compile(r'^\[(\d+)\]\s+(\d+)\b', re.M)

con = sqlite3.connect(f'file:{ROOT / ".data" / "examdata.db"}?mode=ro', uri=True)
con.row_factory = sqlite3.Row

# 1. point codes for the subject: find nodes under the subject's units
sub = con.execute("SELECT id, code, slug FROM subject WHERE slug = 'ial-spanish'").fetchone()
print('subject:', dict(sub) if sub else None)
nodes = con.execute("""
    SELECT id, parent_id, code, name, node_type FROM taxonomy_node
    WHERE code LIKE 'WSP02%' OR code LIKE 'WSP04%'
    ORDER BY code
""").fetchall()
print('--- nodes ---')
for r in nodes:
    print(f"{r['id']:6d} | {r['code']:12s} | {r['node_type']:8s} | {r['name']}")

# 2. pack qids
pack_qids = {}
for pack in PACKS:
    txt = (ROOT / 'tmp_selfjudge' / 'unt' / 'ial-spanish' / f'{pack}.txt').read_text(encoding='utf-8')
    qids = [int(m.group(2)) for m in QID_RE.finditer(txt)]
    pack_qids[pack] = qids
    print(f'{pack}: {len(qids)} qids')

all_qids = [q for qs in pack_qids.values() for q in qs]
print('total qids:', len(all_qids), 'unique:', len(set(all_qids)))

# 3. map each qid -> paper_id, number_path, number_label, kind, marks
print('--- qid details by paper ---')
by_paper = defaultdict(list)
missing = []
for qid in all_qids:
    r = con.execute(
        'SELECT id, paper_id, parent_id, number_label, number_path, kind, marks '
        'FROM question WHERE id = ?', (qid,)).fetchone()
    if r is None:
        missing.append(qid)
        continue
    by_paper[r['paper_id']].append((qid, r['number_path'], r['number_label'], r['kind'], r['marks']))
if missing:
    print('MISSING FROM DB:', missing)

for pid in sorted(by_paper):
    items = sorted(by_paper[pid], key=lambda x: x[0])
    qs = defaultdict(int)
    for qid, npath, nlabel, kind, marks in items:
        qnum = re.split(r'[.(]', str(npath))[0]
        qs[qnum] += 1
    print(f'paper {pid}: {len(items)} qids; per-Q: {dict(sorted(qs.items(), key=lambda kv: (len(kv[0]), kv[0])))}')
    if pid in (2140,):
        for qid, npath, nlabel, kind, marks in items:
            print(f'    {qid} path={npath!r} label={nlabel!r} kind={kind} marks={marks}')
