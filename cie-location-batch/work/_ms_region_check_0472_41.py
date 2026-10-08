import fitz, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

PDF = 'tmp/0472/2026-Jun-41/0472_s26_ms_41.pdf'
doc = fitz.open(PDF)
print('pages:', doc.page_count)

regions = [
    ('1', 7, (102.0, 56.0, 358.5, 734.0)),
    ('1', 8, (72.0, 56.0, 265.0, 734.0)),
    ('2', 9, (102.0, 56.0, 231.0, 734.0)),
    ('2', 10, (72.0, 56.0, 450.0, 734.0)),
    ('3', 11, (102.0, 56.0, 523.0, 734.0)),
    ('3', 12, (72.0, 56.0, 377.5, 734.0)),
    ('3', 13, (72.0, 56.0, 364.5, 734.0)),
    ('3', 14, (72.0, 56.0, 290.5, 734.0)),
    ('3(a)', 11, (124.8, 56.0, 308.4, 734.0)),
    ('3(a)', 12, (72.0, 56.0, 377.5, 734.0)),
    ('3(a)', 13, (72.0, 56.0, 364.5, 734.0)),
    ('3(a)', 14, (72.0, 56.0, 290.5, 734.0)),
    ('3(b)', 11, (308.4, 56.0, 523.0, 734.0)),
    ('3(b)', 12, (72.0, 56.0, 377.5, 734.0)),
    ('3(b)', 13, (72.0, 56.0, 364.5, 734.0)),
    ('3(b)', 14, (72.0, 56.0, 290.5, 734.0)),
]

p11 = doc[10]
print('p11 rect', p11.rect, 'rotation', p11.rotation)
print()
print('==== p11 all spans (unrotated bbox x0,y0,x1,y1) ====')
for b in p11.get_text('dict')['blocks']:
    for l in b.get('lines', []):
        for s in l['spans']:
            t = s['text']
            if t.strip():
                print(tuple(round(v, 1) for v in s['bbox']), repr(t[:70]))
print()

print('==== region containment: words with clip ====')
for q, pn, bb in regions:
    page = doc[pn - 1]
    r = fitz.Rect(*bb)
    words = page.get_text('words', clip=r)
    text = ' '.join(w[4] for w in words)
    print(f'== Q{q} p{pn} {bb}: {len(words)} words')
    print(text[:480])
    print()

print('==== boundary-crossing spans (intersect region but not contained) ====')
seen = set()
for q, pn, bb in regions:
    page = doc[pn - 1]
    r = fitz.Rect(*bb)
    for b in page.get_text('dict')['blocks']:
        for l in b.get('lines', []):
            for s in l['spans']:
                if not s['text'].strip():
                    continue
                sb = fitz.Rect(s['bbox'])
                if sb.intersects(r) and not r.contains(sb):
                    key = (q, pn, tuple(round(v, 1) for v in sb), s['text'][:40])
                    if key in seen:
                        continue
                    seen.add(key)
                    print('CROSS', q, pn, tuple(round(v, 1) for v in sb), repr(s['text'][:60]))
