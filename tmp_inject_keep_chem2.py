# -*- coding: utf-8 -*-
"""Inject 'keep' records for the 3 unresolved chemistry r2 questions.

- 30587: WCH14-12.8 (Mg2Si + HCl equation parent; keep current).
- 30589: WCH14-13.1 (SiH4 shape/bond angle; no WCH14 clause; keep current).
- 29941: WCH15-17.22 (gravimetric chloride test; no WCH15 node fits; keep current).

Note: unit/paper per entry (29941 is WCH15, not the script-1 hardcoded WCH14).
"""
import json
import shutil
from datetime import datetime

SRC = 'tmp_jev_full_r2_ial18-chemistry.jsonl'
BAK = SRC + '.bak2'

KEEP = {
    30587: ('WCH14-12.8', 'WCH14', 'wch14-01'),
    30589: ('WCH14-13.1', 'WCH14', 'wch14-01'),
    29941: ('WCH15-17.22', 'WCH15', 'wch15-01'),
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
for qid, (choice, unit, paper) in KEEP.items():
    if qid in records:
        print(f'qid {qid} already present -> overwrite choice={choice}')
    else:
        order.append(qid)
    records[qid] = {
        'question_id': qid,
        'batch': 'keep-injected',
        'unit': unit,
        'paper_code': paper,
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
