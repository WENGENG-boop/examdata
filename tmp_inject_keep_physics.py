# -*- coding: utf-8 -*-
"""Inject 'keep' records for the 8 unresolved physics questions (no matching spec point found).
Decision: retain current value (minimal intervention); reason recorded in final report + problems file."""
import json
import shutil
from datetime import datetime

SRC = 'tmp_jev_full_r2_ial18-physics.jsonl'
BAK = SRC + '.bak'

KEEP = {
    41672: 'WPH14-93',
    41673: 'WPH14-93',
    41674: 'WPH14-86',
    41675: 'WPH14-86',
    41677: 'WPH14-121',
    41678: 'WPH14-101',
    42362: 'WPH14-98',
    43977: 'WPH14-86',
}

shutil.copyfile(SRC, BAK)
print('backup ->', BAK)

records = {}
order = []
with open(SRC, encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        qid = r['question_id']
        if qid not in records:
            order.append(qid)
        records[qid] = r

ts = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
injected = 0
for qid, choice in KEEP.items():
    if qid in records:
        print(f'qid {qid} already present -> overwrite choice={choice}')
    else:
        order.append(qid)
    records[qid] = {
        'question_id': qid,
        'batch': 'keep-injected',
        'unit': 'WPH14',
        'paper_code': 'wph14-01',
        'current': [choice],
        'choice': choice,
        'confidence': 0.5,
        'top_probs': [[choice, 0.5]],
        'model': 'self-judgment-keep',
        'ts': ts,
    }
    injected += 1

with open(SRC, 'w', encoding='utf-8') as f:
    for qid in order:
        f.write(json.dumps(records[qid], ensure_ascii=False) + '\n')

print(f'injected={injected} total={len(order)}')
