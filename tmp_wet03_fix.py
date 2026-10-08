"""WET03 administrative-point fix: 90 questions -> WET03-3.4.

WET03 (IAL English Literature Unit 3, Poetry and Prose) has 144 questions, all in paper
wet03-01. Spec nodes: 3.1 "Unit description" / 3.2 "Assessment information" (administrative
sections, not content points), 3.3 "Poetry", 3.4 "Prose".

Structure of every exam session in this paper: Q1 = 20-mark unseen-poem commentary (Poetry ->
WET03-3.3); Q2-Q9 = 30-mark Section B prose comparison essays ("Compare the ways in which the
writers of your two chosen texts ... consider relevant contextual factors"), whose mark schemes
are indicative content over the four prose themes (Growing Up / Colonisation and After / Science
and Society / Women and Society) -> WET03-3.4 Prose.

This script:
  - builds tmp_jev_full_batches_r3/ial-englit/batches/batch-002.jsonl with the 90 questions that
    must move to WET03-3.4 (88 at WET03-3.1/3.2 + 49762/49845 at WET03-3.3);
  - appends the 90 verdicts to tmp_selfjudge/r3/ial-englit/WET03-p01.ans.txt (idempotent: a re-run
    replaces the previous fix block instead of duplicating it).

It only writes the two staging files; ingest/decisions/apply/verify are run separately.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / '.data' / 'examdata.db'
BATCH_DIR = ROOT / 'tmp_jev_full_batches_r3' / 'ial-englit' / 'batches'
ANS = ROOT / 'tmp_selfjudge' / 'r3' / 'ial-englit' / 'WET03-p01.ans.txt'
MARK = '# --- WET03 administrative-point fix'

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
rows = [dict(r) for r in con.execute('''
    SELECT q.id AS qid, q.number_label, q.marks, q.stem_text, d.paper_code,
           tn.code AS cur_code, tn.name AS cur_name,
           qt.assigned_by, qt.confidence, qt.reviewed
    FROM question q
    JOIN paper p ON q.paper_id = p.id
    JOIN document d ON p.document_id = d.id
    LEFT JOIN question_taxonomy qt ON qt.question_id = q.id
    LEFT JOIN taxonomy_node tn ON tn.id = qt.node_id
    WHERE d.paper_code LIKE '%wet03%'
    ORDER BY q.id
''')]
con.close()

assert len(rows) == 144, f'expected 144 WET03 questions, got {len(rows)}'
assert all(r['paper_code'] == 'wet03-01' for r in rows), 'unexpected paper_code'


def target(r: dict) -> str:
    return 'WET03-3.3' if r['marks'] == 20 else 'WET03-3.4'


to_change = [r for r in rows if r['cur_code'] != target(r)]
for r in to_change:
    assert r['cur_code'] in ('WET03-3.1', 'WET03-3.2', 'WET03-3.3'), r
    assert r['qid'] and r['stem_text'], r

from collections import Counter
dist = Counter(r['cur_code'] for r in to_change)
assert len(to_change) == 90, f'expected 90 changes, got {len(to_change)}'
print(f'to_change={len(to_change)} by current tag: {dict(dist)}')
print(f"kept: 3.3 x16 (20-mark Q1s), 3.4 x38")

b1_qids = set()
for line in open(BATCH_DIR / 'batch-001.jsonl', encoding='utf-8'):
    if line.strip():
        b1_qids.add(json.loads(line)['question_id'])
change_qids = {r['qid'] for r in to_change}
overlap = b1_qids & change_qids
assert not overlap, f'overlap with batch-001: {overlap}'

for r in to_change:
    if r['qid'] in (49762, 49845):
        print(f"ANOM {r['qid']} cur={r['cur_code']} mk={r['marks']} num={r['number_label']} "
              f"stem[:140]={r['stem_text'][:140]!r}")

out = BATCH_DIR / 'batch-002.jsonl'
with open(out, 'w', encoding='utf-8') as fh:
    for r in sorted(to_change, key=lambda x: x['qid']):
        rec = {
            'question_id': r['qid'],
            'number_label': r['number_label'] or '',
            'paper_code': r['paper_code'],
            'unit_code': 'WET03',
            'stem': r['stem_text'] or '',
            'current': [{
                'code': r['cur_code'],
                'name': r['cur_name'],
                'confidence': round(r['confidence'], 4) if r['confidence'] is not None else None,
                'assigned_by': r['assigned_by'],
                'reviewed': bool(r['reviewed']),
            }],
        }
        fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + '\n')
print(f'wrote {len(to_change)} rows -> {out}')

kept: list[str] = []
for line in ANS.read_text(encoding='utf-8').splitlines():
    s = line.strip()
    if s.startswith(MARK):
        continue
    if s and not s.startswith('#'):
        first = s.split()[0]
        if first.isdigit() and int(first) in change_qids:
            continue
    kept.append(line)

block = [
    '',
    MARK + ' (2026-10-04) ---',
    '# 88 questions at WET03-3.1/3.2 (administrative spec sections "Unit description" /',
    '# "Assessment information" - not content points) plus 49762/49845 (30-mark prose',
    '# comparison essays mis-tagged as Poetry) -> WET03-3.4 Prose.',
    '# Basis: every 30-mark item is a Section B prose comparison essay; its MS is indicative',
    '# content over the four prose themes (Growing Up / Colonisation and After / Science and',
    '# Society / Women and Society). The only poetry item is the 20-mark unseen-poem commentary,',
    '# always Q1 = WET03-3.3 (kept).',
]
block += [f"{r['qid']} WET03-3.4" for r in sorted(to_change, key=lambda x: x['qid'])]
ANS.write_text('\n'.join(kept + block) + '\n', encoding='utf-8')

data_lines = [l.split()[0] for l in ANS.read_text(encoding='utf-8').splitlines()
              if l.strip() and not l.strip().startswith('#')]
assert len(data_lines) == 109, f'ans data lines = {len(data_lines)}, expected 109'
assert len(set(data_lines)) == 109, 'duplicate qids in ans'
print(f'ans file: {len(data_lines)} data lines (19 old + 90 new), no dupes -> {ANS}')
