"""Check review-export decisions completeness against batch files (authoritative status)."""
import json
from pathlib import Path

root = Path('.data/tagging/review-export')
items = [l.strip() for l in Path('tmp_review_items.txt').read_text(encoding='utf-8').splitlines() if l.strip()]
print(f'items={len(items)}')

done, bad = [], []
stale = []
item_set = set(items)
for it in items:
    slug, batch = it.split('/')
    bat = root / slug / 'batches' / f'{batch}.jsonl'
    dec = root / slug / 'decisions' / f'{batch}.jsonl'
    if not bat.exists():
        bad.append((it, 'batch-missing')); continue
    B = set()
    for l in bat.read_text(encoding='utf-8').split('\n'):
        l = l.rstrip('\r')
        if l.strip():
            B.add(json.loads(l)['question_id'])
    if not dec.exists():
        bad.append((it, f'no-decisions n={len(B)}')); continue
    lines = [l for l in dec.read_text(encoding='utf-8').split('\n') if l.strip()]
    D = set()
    ok = True
    for l in lines:
        try:
            o = json.loads(l)
        except Exception:
            ok = False; break
        d = o.get('decision')
        if d not in ('keep', 'change', 'drop'):
            ok = False; break
        if d == 'change' and not o.get('code'):
            ok = False; break
        D.add(o.get('question_id'))
    if not ok:
        bad.append((it, f'invalid-lines n_dec={len(lines)} n_bat={len(B)}')); continue
    if D == B and len(lines) == len(B):
        done.append(it)
    else:
        bad.append((it, f'mismatch dec={len(lines)}/{len(D)} bat={len(B)} missing={len(B-D)} extra={len(D-B)}'))

for p in root.glob('*/decisions/*.jsonl'):
    it = f'{p.parent.parent.name}/{p.stem}'
    if it not in item_set:
        stale.append(it)

print(f'done={len(done)} bad={len(bad)} stale={len(stale)}')
Path('tmp_review_done.txt').write_text('\n'.join(done) + '\n', encoding='utf-8')
Path('tmp_review_missing_items.txt').write_text('\n'.join(it for it, _ in bad) + '\n', encoding='utf-8')
Path('tmp_review_bad_detail.txt').write_text('\n'.join(f'{it}\t{why}' for it, why in bad) + '\n', encoding='utf-8')

from collections import Counter
c_miss = Counter(it.split('/')[0] for it, _ in bad)
print('-- missing per slug --')
for slug, n in sorted(c_miss.items()):
    print(f'{slug}\t{n}')
print('-- bad detail --')
for it, why in bad:
    print(it, why)
print('-- stale --')
for it in stale:
    print(it)
