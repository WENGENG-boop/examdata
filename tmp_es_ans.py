"""Generate self-judgment answer files for unt/ial-spanish (WSP02 688 + WSP04 127).

WSP02: one code per main question (Q1..Q9) per paper, applied to all subparts.
WSP04: per-qid decisions in tmp_es_check2.DEC.

Verifies coverage/uniqueness/code validity/batch parity before writing.
Usage: python tmp_es_ans.py [--dry]
"""
from __future__ import annotations

import ast
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ANS_DIR = ROOT / 'tmp_selfjudge' / 'unt' / 'ial-spanish'
QID_RE = re.compile(r'^\[(\d+)\]\s+(\d+)\b', re.M)
DRY = '--dry' in sys.argv

# Final WSP02 table: paper_id -> code per Q1..Q9 (None = no such question)
WSP02_TABLE = {
    2123: [1, 3, 3, 4, 4, 3, 2, 2, 1],
    2127: [2, 4, 3, 4, 2, 1, 3, 3, 4],
    2128: [3, 4, 1, 3, 2, 4, 1, 1, 3],
    2130: [1, 3, 4, 2, 1, 3, 4, 4, 1],
    2132: [2, 3, 1, 4, 3, 4, 3, 3, 1],
    2134: [1, 4, 2, 3, 3, 4, 3, 3, 4],
    2135: [2, 4, 3, 1, 2, 3, 1, 1, 4],
    2138: [3, 1, 4, 2, 3, 1, 4, 4, 3],
    2140: [2, 3, 1, 4, 4, 3, 1, 3, None],
    2141: [3, 1, 4, 2, 3, 4, 1, 1, 2],
    2143: [1, 3, 4, 2, 1, 2, 1, 1, 3],
    2144: [2, 1, 3, 4, 2, 4, 3, 3, 1],
    2146: [4, 3, 1, 3, 2, 1, 4, 4, 3],
    2149: [3, 3, 1, 4, 4, 2, 3, 3, 2],
}

# Extract DEC (qid -> code) from tmp_es_check2.py without executing it
_tree = ast.parse((ROOT / 'tmp_es_check2.py').read_text(encoding='utf-8'))
DEC: dict[int, str] = {}
for _node in _tree.body:
    if isinstance(_node, ast.Assign) and any(
            getattr(t, 'id', '') == 'DEC' for t in _node.targets):
        DEC = ast.literal_eval(_node.value)
assert DEC, 'DEC dict not found'

con = sqlite3.connect(f'file:{ROOT / ".data" / "examdata.db"}?mode=ro', uri=True)
con.row_factory = sqlite3.Row

errors: list[str] = []

# --- load packs ---
packs: dict[str, list[int]] = {}
for f in sorted(ANS_DIR.glob('WSP0*-p*.txt')):
    if '.ans' in f.name:
        continue
    qids = [int(m.group(2)) for m in QID_RE.finditer(f.read_text(encoding='utf-8'))]
    packs[f.name] = qids

all_qids = [q for v in packs.values() for q in v]
if len(all_qids) != len(set(all_qids)):
    errors.append('duplicate qids across packs')
print(f'packs: {[(k, len(v)) for k, v in packs.items()]}')
print(f'total pack qids: {len(all_qids)}, unique: {len(set(all_qids))}')

# --- load batch rows for parity + unit check ---
bdir = ROOT / 'tmp_jev_untagged_batches' / 'ial-spanish' / 'batches'
batch_qids: dict[int, str] = {}
for f in sorted(bdir.glob('batch-*.jsonl')):
    for line in f.read_text(encoding='utf-8').splitlines():
        rec = json.loads(line)
        batch_qids[rec['question_id']] = rec.get('unit_code') or ''
sp, sb = set(all_qids), set(batch_qids)
if sp - sb:
    errors.append(f'pack-only qids: {sorted(sp - sb)[:10]}')
if sb - sp:
    errors.append(f'batch-only qids: {sorted(sb - sp)[:10]}')

# --- resolve codes per qid ---
info: dict[int, tuple[int, str]] = {}
for q in all_qids:
    r = con.execute(
        'SELECT paper_id, number_path FROM question WHERE id=?', (q,)).fetchone()
    if r is None:
        errors.append(f'{q}: not in DB')
        continue
    info[q] = (r['paper_id'], r['number_path'] or '')

ans: dict[int, str] = {}
per_paper: dict[int, Counter] = defaultdict(Counter)
for name, qids in packs.items():
    for q in qids:
        if q not in info:
            continue
        pid, npth = info[q]
        unit = batch_qids.get(q, '')
        if unit == 'WSP02':
            if pid not in WSP02_TABLE:
                errors.append(f'{q}: paper {pid} not in WSP02 table')
                continue
            if not npth[:1].isdigit() or npth[0] == '0':
                errors.append(f'{q}: bad number_path {npth!r}')
                continue
            qi = int(npth[0])
            code_n = WSP02_TABLE[pid][qi - 1] if 1 <= qi <= 9 else None
            if code_n is None:
                errors.append(f'{q}: paper {pid} Q{qi} has no WSP02 code')
                continue
            ans[q] = f'WSP02-{code_n}'
        elif unit == 'WSP04':
            if q not in DEC:
                errors.append(f'{q}: no WSP04 decision')
                continue
            ans[q] = f'WSP04-{DEC[q]}'
        else:
            errors.append(f'{q}: unexpected unit {unit!r} (paper {pid})')
            continue
        per_paper[pid][ans[q]] += 1

# --- validity of codes ---
valid = {'WSP02-1', 'WSP02-2', 'WSP02-3', 'WSP02-4',
         'WSP04-1', 'WSP04-2', 'WSP04-3', 'WSP04-4', 'WSP04-5',
         'WSP04-6', 'WSP04-7', 'WSP04-S1', 'WSP04-S2', 'WSP04-S3', 'WSP04-S4'}
for q, c in ans.items():
    if c not in valid:
        errors.append(f'{q}: invalid code {c!r}')

# --- per-paper Q coverage for WSP02 ---
for pid, row in WSP02_TABLE.items():
    qs = {int(info[q][1][0]) for q in info if info[q][0] == pid}
    for i, v in enumerate(row, 1):
        if (i in qs) != (v is not None):
            errors.append(f'paper {pid}: Q{i} present={i in qs} but table={v}')

print(f'answers built: {len(ans)} (expect 815)')
print('WSP02 count:', sum(1 for v in ans.values() if v.startswith('WSP02')))
print('WSP04 count:', sum(1 for v in ans.values() if v.startswith('WSP04')))
for pid in sorted(per_paper):
    print(f'  paper {pid}: {dict(sorted(per_paper[pid].items()))}')

if len(ans) != 815:
    errors.append(f'answer count {len(ans)} != 815')

if errors:
    print(f'\nERRORS ({len(errors)}):')
    for e in errors[:50]:
        print('  ', e)
    sys.exit(1)

# --- write ans files ---
NOTE_WSP02 = (
    '# notes: uncertain: 2140 Q7=1/Q8=3 (Q8: Granada graffiti-route sightseeing -> travel, '
    '2134 Q8=3 precedent; alt was 1); 2130 Q3=4 (stress topic, alt 2); '
    'urban/rural -> WSP02-3 (official sub-topic text lists "Urban and rural life" under WSP02-2; '
    'prior tags 62965/63525 -> 3)'
)
NOTE_WSP04 = (
    '# notes: Q8 parents 62388[8]=6 62478[8]=4 63940[8]=6 (sentence-source mode); '
    'corrected 62488[8(j)]=4 (source 62468[7]), 62571[8(b)]=5 (source 62547[5]), '
    '63946[8(f)]=3 (source 63926[6]); '
    'uncertain: 62873=1 (music, alt 6), 62993=2 (career, alt 4), 63765=6 (music, alt 1), '
    '63937/63938=1 (politics, alt 6), 62725=6 (sibling (c)=4), 62463=6 (sibling (b)=4)'
)
for name, qids in sorted(packs.items()):
    unit = 'WSP02' if name.startswith('WSP02') else 'WSP04'
    out = ANS_DIR / name.replace('.txt', '.ans.txt')
    lines = [
        f'# unt/ial-spanish {name[:-4]} self-judgment ({len(qids)} questions)',
        f'# qid CODE per line; basis: full-text + mark-scheme + spec sub-topic review, '
        f'cross-checked vs parent/sibling tags',
        NOTE_WSP02 if unit == 'WSP02' else NOTE_WSP04,
    ]
    lines += [f'{q} {ans[q]}' for q in qids]
    if DRY:
        print(f'[dry] would write {out.name}: {len(qids)} lines')
    else:
        out.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        print(f'wrote {out.name}: {len(qids)} lines')
print('OK')
