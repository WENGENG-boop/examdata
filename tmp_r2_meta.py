"""Read-only meta: for each qid in given packs, show old (from applied.jsonl) vs current cur= label."""
import json, re, sys
from pathlib import Path
from collections import Counter, defaultdict

ROOT = Path('.')
APPLIED = ROOT / 'tmp_jev_full_decisions' / 'ial18-physics' / 'applied.jsonl'

old_map = {}
for line in open(APPLIED, encoding='utf-8'):
    e = json.loads(line)
    if e.get('status') != 'applied':
        continue
    old = re.search(r'与原标签（(.+?)）不符', e.get('reason') or '')
    conf = re.search(r'置信度 ([\d.]+)', e.get('reason') or '')
    old_map[str(e['question_id'])] = (old.group(1) if old else None,
                                      float(conf.group(1)) if conf else None,
                                      e.get('decision'), e.get('code'))

for packpath in sys.argv[1:]:
    pack = Path(packpath)
    qids = []
    cur = {}
    for ln in pack.read_text(encoding='utf-8').splitlines():
        m = re.match(r'^\[(\d+)\]\s+(\d+)\s+#(\S+)\s+(\S+)mk\s+cur=(\S+)', ln)
        if m:
            qids.append(m.group(2))
            cur[m.group(2)] = m.group(5)
    print(f'#### {pack.name}: {len(qids)} questions')
    pairs = Counter()
    noapplied = []
    for q in qids:
        o = old_map.get(q)
        if o is None:
            noapplied.append(q)
            continue
        old = o[0] or '(none)'
        if old != cur[q]:
            pairs[(old, cur[q])] += 1
        else:
            pairs[(old, cur[q])] += 0  # unchanged
    # print only changed pairs
    changed = {k: v for k, v in pairs.items() if v > 0}
    for (old, new), n in sorted(changed.items(), key=lambda x: -x[1]):
        print(f'  {old} -> {new}: {n}')
    print(f'  unchanged: {sum(1 for q in qids if q in old_map and (old_map[q][0] or "(none)") == cur[q])}')
    print(f'  not in applied.jsonl: {len(noapplied)} -> {noapplied[:20]}')
