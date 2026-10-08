# -*- coding: utf-8 -*-
"""G14 book11 deep dump: official keys vs index vs pte source + page OCR layout."""
import json, re, sys, io, os

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

# ---------- 1. official ----------
off = {}
for t in (1, 2, 3, 4):
    for s in ('listening', 'reading'):
        d = load(f'{R}/official-keys/book_11/test_{t}_{s}.json')
        off[(t, s)] = d

p('=' * 100)
p('SECTION 1: OFFICIAL book_11 entries (from PDF pages)')
for t in (1, 2, 3, 4):
    for s in ('listening', 'reading'):
        d = off[(t, s)]
        ents = d['entries']
        nums = sorted(e['number'] for e in ents if isinstance(e.get('number'), int))
        missing = [n for n in range(1, 41) if n not in nums]
        p(f'-- official t{t} {s}: n={len(ents)} numbers {min(nums) if nums else "-"}..{max(nums) if nums else "-"} missing={missing}')
        for e in sorted(ents, key=lambda x: x['number']):
            p(f"   {e['number']:>2} | {str(e.get('value'))[:70]!r} | ns={e.get('number_source')} vs={e.get('value_source')} conf={e.get('ocr_conf')} vv={e.get('visual_verified')} eo={e.get('either_order')} g={e.get('group_ids')} sec={e.get('section')} y={e.get('y')} col={e.get('col')}")

# ---------- 2. index ----------
idx = {}
for t in (1, 2, 3, 4):
    for s, suff in (('listening', 'listening_shared'), ('reading', 'reading_academic')):
        d = load(f'{R}/scratch/s18/answers/book_11/test_{t}_{suff}.json')
        idx[(t, s)] = d

p('=' * 100)
p('SECTION 2: INDEX answers book_11')
for t in (1, 2, 3, 4):
    for s in ('listening', 'reading'):
        d = idx[(t, s)]
        p(f'-- index t{t} {s}: source={d.get("source")} kind={d.get("kind")} identity={d.get("identity")} stats={d.get("stats")}')
        ents = d.get('entries') or []
        if not ents and isinstance(d.get('values'), list):
            ents = [{'number': d.get('start', 1) + i, 'value': v} for i, v in enumerate(d['values'])]
        for e in sorted(ents, key=lambda x: x.get('number', 0)):
            p(f"   {e.get('number'):>2} | {str(e.get('value'))[:70]!r}")

# ---------- 3. pte ----------
pte = {}
for m in (1, 2, 3, 4):
    for s in ('listening', 'reading'):
        d = load(f'tmp_audit_ielts/completeness_20261003/pte-11-{m}-{s}.json')
        pte[(m, s)] = d

p('=' * 100)
p('SECTION 3: PTE source pte-11-M')
for m in (1, 2, 3, 4):
    for s in ('listening', 'reading'):
        d = pte[(m, s)]
        qs = d.get('questions') or []
        p(f'-- pte-11-{m} {s}: slug={d.get("slug")} url={d.get("url")} q={len(qs)} answer_count={d.get("answer_count")} question_count={d.get("question_count")} missing={d.get("questions_missing")}')
        for q in qs:
            p(f"   {q.get('number'):>2} | {str(q.get('answer'))[:70]!r}")

# ---------- 4. matrices ----------
p('=' * 100)
p('SECTION 4: MATRIX official tN vs pte-11-M (hits/comparable)')
for s in ('listening', 'reading'):
    p(f'--- skill={s}')
    for t in (1, 2, 3, 4):
        oe = {e['number']: e.get('value') for e in off[(t, s)]['entries']}
        row = []
        for m in (1, 2, 3, 4):
            pq = {q['number']: q.get('answer') for q in (pte[(m, s)].get('questions') or [])}
            common = [n for n in oe if n in pq]
            h = sum(1 for n in common if hit(oe[n], pq[n]))
            row.append(f'pte-{m}:{h}/{len(common)}')
        p(f'  off t{t} (n={len(oe)}): ' + '  '.join(row))

p('=' * 100)
p('SECTION 5: MATRIX index tM vs pte-11-M (identical value count / comparable)')
for s in ('listening', 'reading'):
    for t in (1, 2, 3, 4):
        d = idx[(t, s)]
        ents = d.get('entries') or []
        ie = {e['number']: e.get('value') for e in ents}
        pq = {q['number']: q.get('answer') for q in (pte[(t, s)].get('questions') or [])}
        common = [n for n in ie if n in pq]
        h = sum(1 for n in common if hit(ie[n], pq[n]))
        p(f'  {s} index t{t} (n={len(ie)}) vs pte-{t}: identical={h}/{len(common)}')

p('=' * 100)
p('SECTION 6: MATRIX official tN vs index tM (hits/comparable) — cross check')
for s in ('listening', 'reading'):
    p(f'--- skill={s}')
    for t in (1, 2, 3, 4):
        oe = {e['number']: e.get('value') for e in off[(t, s)]['entries']}
        row = []
        for m in (1, 2, 3, 4):
            d = idx[(m, s)]
            ents = d.get('entries') or []
            ie = {e['number']: e.get('value') for e in ents}
            common = [n for n in oe if n in ie]
            h = sum(1 for n in common if hit(oe[n], ie[n]))
            row.append(f'idx-{m}:{h}/{len(common)}')
        p(f'  off t{t} (n={len(oe)}): ' + '  '.join(row))

# ---------- 7. page OCR layout ----------
p('=' * 100)
p('SECTION 7: OCR page layout (book_11.json) pages 117-124 first 60 words + targeted pages full')
ocr = load(f'{R}/official-keys/ocr/book_11.json')
pages = {pg['file_page']: pg for pg in ocr['pages']}
p('ocr pages available:', sorted(pages.keys()))
for fp in (117, 118, 119, 120, 121, 122, 123, 124):
    pg = pages.get(fp)
    if not pg:
        p(f'-- page {fp}: NOT IN OCR')
        continue
    ws = pg['words']
    p(f'-- page {fp}: {len(ws)} words; first 24: ' + ' | '.join(w['text'] for w in ws[:24]))

# targeted: page 123 and 117 full with coordinates, page 121 full
for fp in (123, 117, 121):
    pg = pages.get(fp)
    if not pg: continue
    p('-' * 100)
    p(f'PAGE {fp} FULL WORDS (text | x0 | y0 | conf), sorted as stored:')
    for w in pg['words']:
        p(f"   {w['text']!r:>28} x={w.get('x0')} y={w.get('y0')} c={w.get('conf')}")

open(f'{R}/scratch/s18/book11-deepdump.txt', 'w', encoding='utf-8').write('\n'.join(OUT))
print('WROTE', f'{R}/scratch/s18/book11-deepdump.txt', 'lines=', len(OUT))
