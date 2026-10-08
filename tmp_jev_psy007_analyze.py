"""Compare Jev run1 vs run2 for psy batch-007 and propose decisions."""
import json
import sys

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

sys.path.insert(0, r'C:/Users/weo/Desktop/api/examdata')
from examdata.core import models as m

DB = 'sqlite:///C:/Users/weo/Desktop/api/examdata/.data/examdata.db'
eng = create_engine(DB)
s = Session(eng)

names = {n.code: n.name for n in s.execute(
    select(m.TaxonomyNode).where(m.TaxonomyNode.code.like('WPS%'))).scalars()}


def load(path):
    out = {}
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            rec = json.loads(line)
            out[rec['question_id']] = rec
    return out


v1 = load(r'C:/Users/weo/Desktop/api/examdata/tmp_jev_psy007.v1.jsonl')
v2 = load(r'C:/Users/weo/Desktop/api/examdata/tmp_jev_psy007.jsonl')

print(f"{'qid':>6} {'cur':>22} | {'run1':>18} | {'run2':>18} | decision")
low = []
for qid in sorted(v2):
    r2 = v2[qid]
    r1 = v1.get(qid, {})
    cur = ','.join(r2['current_tags'])
    c1 = f"{r1.get('choice')} {r1.get('confidence')}"
    c2 = f"{r2.get('choice')} {r2.get('confidence')}"
    ch = r2.get('choice')
    if ch in r2['current_tags']:
        dec = 'keep'
    else:
        dec = f'change->{ch}'
    if (r2.get('confidence') or 0) < 0.6:
        low.append(qid)
    print(f"{qid:>6} {cur:>22} | {c1:>18} | {c2:>18} | {dec}")

print()
print('--- top-3 probabilities for low-confidence (<0.6) run2 ---')
for qid in low:
    r2 = v2[qid]
    probs = sorted((r2.get('probabilities') or {}).items(),
                   key=lambda kv: -kv[1])[:3]
    pretty = ', '.join(f'{c}:{p:.2f}' for c, p in probs)
    print(f"{qid} conf={r2.get('confidence')} cur={r2['current_tags']}")
    print(f"   {pretty}")
    for c, _ in probs[:3]:
        print(f"      {c} = {names.get(c)}")
