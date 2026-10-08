"""List qids in the 4 flagged clusters with old/new/reason from applied.jsonl, per pack."""
import json, re, sys
from pathlib import Path

APPLIED = Path('tmp_jev_full_decisions/ial18-physics/applied.jsonl')
CLUSTERS = {('WPH12-43','WPH12-42'), ('WPH12-52','WPH12-51'), ('WPH12-48','WPH12-45'), ('WPH12-79','WPH12-76')}

info = {}
for line in open(APPLIED, encoding='utf-8'):
    e = json.loads(line)
    if e.get('status') != 'applied' or e.get('decision') != 'change':
        continue
    m = re.search(r'与原标签（(.+?)）不符', e.get('reason') or '')
    old = m.group(1) if m else None
    info[e['question_id']] = (old, e.get('code'), e.get('reason'))

for packpath in sys.argv[1:]:
    pack = Path(packpath)
    qids = []
    for ln in pack.read_text(encoding='utf-8').splitlines():
        m = re.match(r'^\[(\d+)\]\s+(\d+)\s', ln)
        if m:
            qids.append(int(m.group(2)))
    print(f'#### {pack.name}')
    for q in qids:
        o = info.get(q)
        if not o: continue
        old, new, reason = o
        if old and any(old.startswith(c[0]) and new == c[1] for c in CLUSTERS):
            print(f'  {q} old={old} new={new}')
            print(f'     reason: {reason[:300]}')
