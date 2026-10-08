# -*- coding: utf-8 -*-
"""G14 book11: per-number mismatch dump for remapped pairs + cross-book matching for anomalies."""
import json, re, sys, io, glob, os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
R = 'ielts-data/runs/20261003T140007Z-repair'
OUT = []
def p(*a):
    OUT.append(' '.join(str(x) for x in a))

def load(f):
    return json.load(open(f, encoding='utf-8'))

def norm(s):
    if s is None: return ''
    return re.sub(r'\s+', ' ', str(s).strip().lower())

def loose(s):
    if s is None: return ''
    return re.sub(r'[^0-9a-z]+', '', str(s).lower())

def hit(a, b):
    if a is None or b is None: return False
    if norm(a) == norm(b): return True
    return loose(a) == loose(b) and loose(a) != ''

# remap: official tN <-> pte-M
REMAP = {1: 2, 2: 3, 3: 4, 4: 1}

off = {}
for t in (1, 2, 3, 4):
    for s in ('listening', 'reading'):
        off[(t, s)] = load(f'{R}/official-keys/book_11/test_{t}_{s}.json')

pte = {}
for m in (1, 2, 3, 4):
    for s in ('listening', 'reading'):
        pte[(m, s)] = load(f'tmp_audit_ielts/completeness_20261003/pte-11-{m}-{s}.json')

p('=' * 100)
p('SECTION A: per-number mismatch dump, official tN vs pte-M (remapped pairing)')
for t in (1, 2, 3, 4):
    m = REMAP[t]
    for s in ('listening', 'reading'):
        oe = {e['number']: e.get('value') for e in off[(t, s)]['entries']}
        pq = {q['number']: q.get('answer') for q in (pte[(m, s)].get('questions') or [])}
        p(f'-- off t{t} vs pte-{m} {s}:')
        for n in range(1, 41):
            a, b = oe.get(n), pq.get(n)
            if a is None and b is None: continue
            v = 'HIT' if (a is not None and b is not None and hit(a, b)) else ('DIFF' if (a is not None and b is not None) else 'ONE-SIDED')
            p(f"   {n:>2} | off={str(a)[:45]!r:48} | pte={str(b)[:45]!r:48} | {v}")

p('=' * 100)
p('SECTION B: cross-match — for the anomalous listening pair, search ALL books')
# load all official listening keys
off_all = {}
for f in sorted(glob.glob(f'{R}/official-keys/book_*/*_listening.json')):
    d = load(f)
    bid = d.get('identity', {})
    key = (bid.get('book'), bid.get('test'))
    off_all[key] = {e['number']: e.get('value') for e in d['entries']}

pte_all = {}
for f in sorted(glob.glob('tmp_audit_ielts/completeness_20261003/pte-*-listening.json')):
    d = load(f)
    if d.get('book') is None or d.get('test') is None:
        continue
    key = (d.get('book'), d.get('test'))
    pte_all[key] = {q['number']: q.get('answer') for q in (d.get('questions') or [])}

# (1) book 11 t3 listening (page 121 extraction) vs all pte listening files
tgt = off[(3, 'listening')]
tgtv = {e['number']: e.get('value') for e in tgt['entries']}
p('-- official book11 t3 listening vs ALL pte listening files:')
res = []
for k, pq in sorted(pte_all.items()):
    common = [n for n in tgtv if n in pq]
    h = sum(1 for n in common if hit(tgtv[n], pq[n]))
    if common and h >= 3:
        res.append((h, len(common), k))
for h, c, k in sorted(res, reverse=True):
    p(f'   pte {k}: hits={h}/{c}')

# (2) pte-11-4 listening vs all official listening keys
pq = pte[(4, 'listening')]
pqv = {q['number']: q.get('answer') for q in (pq.get('questions') or [])}
p('-- pte-11-4 listening vs ALL official listening keys:')
res = []
for k, ov in sorted(off_all.items()):
    common = [n for n in pqv if n in ov]
    h = sum(1 for n in common if hit(pqv[n], ov[n]))
    if common and h >= 3:
        res.append((h, len(common), k))
for h, c, k in sorted(res, reverse=True):
    p(f'   official {k}: hits={h}/{c}')

# (3) same for reading: pte-11-1 reading vs all official reading keys; official t4 reading vs all pte reading files
p('-- pte-11-1 reading vs ALL official reading keys (checking t4 anomaly):')
off_all_r = {}
for f in sorted(glob.glob(f'{R}/official-keys/book_*/*_reading.json')):
    d = load(f)
    bid = d.get('identity', {})
    off_all_r[(bid.get('book'), bid.get('test'))] = {e['number']: e.get('value') for e in d['entries']}
pte_all_r = {}
for f in sorted(glob.glob('tmp_audit_ielts/completeness_20261003/pte-*-reading.json')):
    d = load(f)
    pte_all_r[(d.get('book'), d.get('test'))] = {q['number']: q.get('answer') for q in (d.get('questions') or [])}
pqr = pte[(1, 'reading')]
pqrv = {q['number']: q.get('answer') for q in (pqr.get('questions') or [])}
res = []
for k, ov in sorted(off_all_r.items()):
    common = [n for n in pqrv if n in ov]
    h = sum(1 for n in common if hit(pqrv[n], ov[n]))
    if common and h >= 3:
        res.append((h, len(common), k))
for h, c, k in sorted(res, reverse=True):
    p(f'   official {k}: hits={h}/{c}')

p('-- official book11 t4 reading vs ALL pte reading files:')
tgt4 = {e['number']: e.get('value') for e in off[(4, 'reading')]['entries']}
res = []
for k, pq2 in sorted(pte_all_r.items()):
    common = [n for n in tgt4 if n in pq2]
    h = sum(1 for n in common if hit(tgt4[n], pq2[n]))
    if common and h >= 3:
        res.append((h, len(common), k))
for h, c, k in sorted(res, reverse=True):
    p(f'   pte {k}: hits={h}/{c}')

open(f'{R}/scratch/s18/book11-mismatches.txt', 'w', encoding='utf-8').write('\n'.join(OUT))
print('WROTE', f'{R}/scratch/s18/book11-mismatches.txt', 'lines=', len(OUT))
