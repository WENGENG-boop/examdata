# -*- coding: utf-8 -*-
"""Build 0472/2026/Jun/21 obs_final.jsonl: 92 regions (49 qp + 43 ms) in index order.
Source priority: reverify obs (post-fix, new bbox) > old obs (unchanged regions) matched by (label,role,page)."""
import json, re, sys

BR = 'C:/Users/weo/Desktop/api/cie-location-batch'

def norm_label(lab):
    m = re.match(r'^[QM](?=\d)', lab)
    return lab[1:] if m else lab

idx = json.load(open(f'{BR}/indexes/0472/2026-Jun-21/cie-index.json', encoding='utf-8'))
assert idx['identity'] == {'subject': '0472', 'year': 2026, 'season': 'Jun', 'paper': '21'}, idx['identity']

expected = []
for q in idx['questions']:
    for r in q.get('qp', []):
        expected.append((q['question'], 'qp', r['page'], tuple(r['bbox'])))
for q in idx['questions']:
    for r in q.get('ms', []):
        expected.append((q['question'], 'ms', r['page'], tuple(r['bbox'])))
print('expected regions:', len(expected))
assert len(expected) == 92, len(expected)

def load_regions(path):
    regs = []
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        fr = json.loads(line)
        for r in fr.get('regions', []):
            regs.append({'frame': fr['frame'], 'sheet': fr['sheet'], 'label': r['label'],
                         'role': r['role'], 'page': r['page'], 'bbox': tuple(r['bbox']), 'obs': r['obs']})
    return regs

rev_regions = load_regions(f'{BR}/work/0472_2026_21_obs_reverify.jsonl')
old_regions = load_regions(f'{BR}/work/0472_2026_21_obs.jsonl')
print('reverify regions:', len(rev_regions), 'old regions:', len(old_regions))

out = []
missing = []
used = {'reverify': 0, 'old': 0}
for (label, role, page, bbox) in expected:
    found = None
    for r in rev_regions:
        if norm_label(r['label']) == label and r['role'] == role and r['page'] == page and r['bbox'] == bbox:
            found = ('reverify', r)
            break
    if found is None:
        cands = [r for r in old_regions if norm_label(r['label']) == label and r['role'] == role and r['page'] == page]
        if len(cands) == 1:
            found = ('old', cands[0])
        elif len(cands) > 1:
            exact = [r for r in cands if r['bbox'] == bbox]
            if len(exact) == 1:
                found = ('old', exact[0])
            else:
                print(f'AMBIGUOUS old match for {label}/{role}/p{page}: {len(cands)} cands, {len(exact)} exact')
    if found is None:
        missing.append((label, role, page, bbox))
        continue
    src, r = found
    used[src] += 1
    out.append({'label': label, 'role': role, 'page': page, 'bbox': list(bbox), 'obs': r['obs'],
                'source': src, 'frame': r['frame']})

print('matched:', len(out), 'from reverify:', used['reverify'], 'from old:', used['old'])
if missing:
    print('MISSING:', len(missing))
    for m in missing:
        print('  ', m)
    sys.exit(1)
assert len(out) == 92

with open(f'{BR}/work/0472_2026_21_obs_final.jsonl', 'w', encoding='utf-8') as f:
    for r in out:
        f.write(json.dumps(r, ensure_ascii=False) + '\n')
print('wrote work/0472_2026_21_obs_final.jsonl')
