import json, sys
want = set()
for a in sys.argv[1:]:
    if '-' in a:
        lo, hi = a.split('-')
        want.update(range(int(lo), int(hi) + 1))
    else:
        want.add(int(a))
rows = []
for l in open('tmp_r2_math_scratch/all.jsonl', encoding='utf-8'):
    r = json.loads(l)
    if r.get('qid') in want:
        rows.append(r)
print('found', len(rows))
for r in sorted(rows, key=lambda x: x['qid']):
    print('===', r['qid'], r.get('number'), 'old=', repr(r.get('old')), 'cur=', r.get('cur'))
    print('   reason:', (r.get('reason') or '')[:400])
    stem = (r.get('stem') or '')[:200].replace('\n', ' ')
    print('   stem:', stem)
