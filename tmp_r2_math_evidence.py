"""Read-only evidence extractor for ial18-mathematics r2 review.

Writes per-unit compact TSV + full jsonl:
  tmp_r2_math_scratch/<UNIT>.tsv : qid, num, cur, prev, jev_conf, reason, stem(240)
  tmp_r2_math_scratch/all.jsonl  : qid, unit, num, cur, prev, reason, stem(full)
"""
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'tmp_r2_math_scratch'
OUT.mkdir(exist_ok=True)
db = (ROOT / '.data' / 'examdata.db').as_posix()
con = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
c = con.cursor()

# 1) round-1 apply log: changed questions with previous label + reason
prev = {}
for line in open(ROOT / 'tmp_jev_full_decisions' / 'ial18-mathematics' / 'applied.jsonl', encoding='utf-8'):
    line = line.strip()
    if not line:
        continue
    e = json.loads(line)
    if e.get('decision') == 'change' and e.get('status') == 'applied':
        m = re.search(r'原标签[（(]([^）)]*)[）)]', e.get('reason') or '')
        prev[int(e['question_id'])] = {
            'code': e.get('code'),
            'old': m.group(1) if m else '',
            'reason': e.get('reason') or '',
        }

# 2) r2 batch rows (unit, number, current, stem)
rows = []
import glob
for f in sorted(glob.glob(str(ROOT / 'tmp_jev_full_batches_r2' / 'ial18-mathematics' / 'batches' / 'batch-*.jsonl'))):
    for line in open(f, encoding='utf-8'):
        r = json.loads(line)
        rows.append(r)

print('batch rows', len(rows), 'prev-changed', len(prev))

by_unit = {}
with open(OUT / 'all.jsonl', 'w', encoding='utf-8') as fh:
    for r in rows:
        qid = r['question_id']
        unit = r['unit_code']
        cur = r['current'][0]['code'] if r['current'] else None
        p = prev.get(qid, {})
        rec = {
            'qid': qid, 'unit': unit, 'number': r['number_label'],
            'cur': cur, 'old': p.get('old', ''), 'reason': p.get('reason', ''),
            'stem': r['stem'],
        }
        fh.write(json.dumps(rec, ensure_ascii=False) + '\n')
        by_unit.setdefault(unit, []).append(rec)

for unit, recs in by_unit.items():
    with open(OUT / f'{unit}.tsv', 'w', encoding='utf-8') as fh:
        for rec in recs:
            stem = ' '.join((rec['stem'] or '').split())[:240]
            fh.write(f"{rec['qid']}\t{rec['number']}\t{rec['cur']}\t{rec['old']}\t{stem}\n")
print('units:', {u: len(v) for u, v in sorted(by_unit.items())})
