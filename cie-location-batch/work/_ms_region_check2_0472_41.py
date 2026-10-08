import fitz, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

PDF = 'tmp/0472/2026-Jun-41/0472_s26_ms_41.pdf'
doc = fitz.open(PDF)

print('==== full clip text Q3(a) p11 [124.8,56,308.4,734] ====')
w = doc[10].get_text('words', clip=fitz.Rect(124.8, 56.0, 308.4, 734.0))
txt = ' '.join(x[4] for x in w)
print(txt)
print('OR present:', 'OR' in txt.split() or ' OR ' in txt)
print()

print('==== full clip text Q3(b) p11 [308.4,56,523,734] ====')
w = doc[10].get_text('words', clip=fitz.Rect(308.4, 56.0, 523.0, 734.0))
txt = ' '.join(x[4] for x in w)
print(txt[:700])
print('OR present:', ' OR ' in txt or txt.startswith('OR'))
print()

for pn, x1 in [(12, 377.5), (13, 364.5), (14, 290.5)]:
    page = doc[pn - 1]
    print(f'==== p{pn}: spans with bbox x1 > region x1={x1} (and any span list tail) ====')
    maxx = 0
    n = 0
    for b in page.get_text('dict')['blocks']:
        for l in b.get('lines', []):
            for s in l['spans']:
                if not s['text'].strip():
                    continue
                n += 1
                maxx = max(maxx, s['bbox'][2])
                if s['bbox'][2] > x1:
                    print('  OUT', tuple(round(v, 1) for v in s['bbox']), repr(s['text'][:60]))
    print(f'  spans={n} max_x1={round(maxx,1)}')
    print()

print('==== p8 region [72,56,265,734]: spans x1>265 ====')
for b in doc[7].get_text('dict')['blocks']:
    for l in b.get('lines', []):
        for s in l['spans']:
            if s['text'].strip() and s['bbox'][2] > 265:
                print('  OUT', tuple(round(v, 1) for v in s['bbox']), repr(s['text'][:60]))
print()
print('==== p10 region [72,56,450,734]: spans x1>450 ====')
for b in doc[9].get_text('dict')['blocks']:
    for l in b.get('lines', []):
        for s in l['spans']:
            if s['text'].strip() and s['bbox'][2] > 450:
                print('  OUT', tuple(round(v, 1) for v in s['bbox']), repr(s['text'][:60]))
print()
print('==== p7 region [102,56,358.5,734]: spans x1>358.5 ====')
for b in doc[6].get_text('dict')['blocks']:
    for l in b.get('lines', []):
        for s in l['spans']:
            if s['text'].strip() and s['bbox'][2] > 358.5:
                print('  OUT', tuple(round(v, 1) for v in s['bbox']), repr(s['text'][:60]))
print()
print('==== p9 region [102,56,231,734]: spans x1>231 ====')
for b in doc[8].get_text('dict')['blocks']:
    for l in b.get('lines', []):
        for s in l['spans']:
            if s['text'].strip() and s['bbox'][2] > 231:
                print('  OUT', tuple(round(v, 1) for v in s['bbox']), repr(s['text'][:60]))
