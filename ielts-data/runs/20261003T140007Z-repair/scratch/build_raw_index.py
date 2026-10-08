import json, glob, os, re

d = os.path.dirname(os.path.abspath(__file__))
ev = r'C:\Users\weo\Desktop\api\tmp_audit_ielts\completeness_20261003'
req = json.load(open(os.path.join(ev, 'requests.json'), encoding='utf-8'))
url_to_idx = {}
for r in req:
    url_to_idx.setdefault(r['url'], []).append(r['index'])
slug_to_idx = {}
for r in req:
    m = re.search(r'pages\?slug=([^&]+)', r['url'])
    if m:
        slug_to_idx.setdefault(m.group(1), []).append(r['index'])

index = []
for f in sorted(glob.glob(os.path.join(ev, 'pte-*.json'))):
    m = re.match(r'pte-(\d+)-(\d+)-(reading|listening)\.json$', os.path.basename(f))
    if not m:
        continue
    book, test, skill = int(m.group(1)), int(m.group(2)), m.group(3)
    snap = json.load(open(f, encoding='utf-8'))
    url = snap.get('url')
    idxs = slug_to_idx.get(snap.get('slug'), [])
    index.append({
        'book': book, 'test': test, 'skill': skill,
        'ok': bool(snap.get('ok')), 'slug': snap.get('slug'),
        'page_id': snap.get('page_id'), 'title': snap.get('title'),
        'url': url, 'raw_index': idxs[0] if idxs else None,
        'raw_all': idxs,
        'questions': len(snap.get('questions', [])),
        'answer_key': len(snap.get('answer_key', [])),
        'missing': snap.get('questions_missing'),
    })

for f in sorted(glob.glob(os.path.join(ev, 'cam21-*.json'))):
    m = re.match(r'cam21-(\d+)-(reading|listening)\.json$', os.path.basename(f))
    if not m:
        continue
    test, skill = int(m.group(1)), m.group(2)
    snap = json.load(open(f, encoding='utf-8'))
    url = snap.get('url')
    idxs = slug_to_idx.get(snap.get('slug'), [])
    index.append({
        'book': 21, 'test': test, 'skill': skill, 'ok': bool(snap.get('ok')),
        'slug': snap.get('slug'), 'page_id': snap.get('page_id'),
        'title': snap.get('title'), 'url': url,
        'raw_index': idxs[0] if idxs else None, 'raw_all': idxs,
        'questions': len(snap.get('questions', [])),
        'answer_key': len(snap.get('answer_key', [])),
    })

out = os.path.join(r'C:\Users\weo\Desktop\api\ielts-data\runs\20261003T140007Z-repair\evidence', 'S04-raw-index.json')
json.dump(index, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

n_ok = sum(1 for e in index if e['ok'])
n_raw = sum(1 for e in index if e['raw_index'] is not None)
print(f'entries={len(index)} ok={n_ok} with_raw={n_raw}')
by = {}
for e in index:
    by.setdefault((e['book'], e['skill']), []).append((e['test'], e['ok'], e['raw_index']))
missing = [(b, t, s) for b in range(1, 22) for t in range(1, 5) for s in ('reading', 'listening')
           if not any(x[0] == t for x in by.get((b, s), []))]
print('missing job entries:', missing)
no_raw = [(e['book'], e['test'], e['skill']) for e in index if e['raw_index'] is None]
print('entries without raw:', no_raw)
# hub pages: which raw files are not mapped to any snapshot url
mapped = set()
for e in index:
    mapped.update(e['raw_all'])
unmapped = [r['index'] for r in req if r['index'] not in mapped]
print('unmapped raw count:', len(unmapped))
for i in unmapped[:10]:
    print('  raw', i, req[i]['url'])
