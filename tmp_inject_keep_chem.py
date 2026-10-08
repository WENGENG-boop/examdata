# -*- coding: utf-8 -*-
"""Inject 'keep' records for the 2 unresolved chemistry questions (no matching
spec point found in WCH14). Decision: retain current value (minimal
intervention); reason recorded in final report.
- 30587: parent row, Mg2Si + HCl equation + SiH4 shape table; current WCH14-12.8.
- 30589: SiH4 shape/bond angle; no WCH14 clause covers molecular shape (Unit 1
  assumed knowledge); current WCH14-13.1.
"""
import json
import shutil
from datetime import datetime

SRC = 'tmp_jev_full_r2_ial18-chemistry.jsonl'
BAK = SRC + '.bak'

KEEP = {
    30587: 'WCH14-12.8',
    30589: 'WCH14-13.1',
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
        'unit': 'WCH14',
        'paper_code': 'wch14-01',
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
