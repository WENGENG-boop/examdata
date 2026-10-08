"""Audit r6 WMA13 ans file against batch current labels. Read-only, no DB.

Usage:
  ./.venv/Scripts/python.exe -X utf8 tmp_r6_audit_wma13.py
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BATCH = ROOT / 'tmp_jev_full_batches_r6' / 'ial18-mathematics' / 'batches'
ANS = ROOT / 'tmp_selfjudge' / 'r6' / 'ial18-mathematics' / 'WMA13-p01.ans.txt'

rows: dict[int, dict] = {}
for f in sorted(glob.glob(str(BATCH / 'batch-*.jsonl'))):
    for line in open(f, encoding='utf-8'):
        rec = json.loads(line)
        if rec.get('unit_code') == 'WMA13':
            rows[rec['question_id']] = rec

answers: dict[int, str] = {}
for raw in ANS.read_text(encoding='utf-8').splitlines():
    line = raw.strip()
    if not line or line.startswith('#'):
        continue
    qid, code = line.split()
    answers[int(qid)] = code

ok, conv, over = [], [], []
for qid in sorted(answers):
    code = answers[qid]
    cur = [c.get('code') for c in (rows[qid].get('current') or [])]
    if code == 'OK':
        ok.append((qid, cur))
    elif code in cur:
        conv.append((qid, code, cur))
    else:
        over.append((qid, code, cur))

print(f'total={len(answers)} ok={len(ok)} explicit_in_current={len(conv)} '
      f'explicit_override={len(over)}')
print('-- OK rows (current must be exactly 1):')
for qid, cur in ok:
    print(f'  {qid}  current={cur}')
print('-- converged (explicit code is one of current):')
for qid, code, cur in conv:
    print(f'  {qid}  {code}  <- current={cur}')
print('-- override (explicit code differs from all current):')
print('  qids:', ' '.join(str(q) for q, _, _ in over))
print('-- anomalies:')
anom = 0
for qid, cur in ok:
    if len(cur) != 1:
        print(f'  OK with {len(cur)} current rows: {qid}')
        anom += 1
for qid, code, cur in over:
    if not cur:
        print(f'  override with empty current: {qid}')
        anom += 1
print(f'  anomalies={anom}')
