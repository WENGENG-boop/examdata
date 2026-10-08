"""Build coverage.json (FindSimilarTPO item inventory) and ddy-index.json (structured reading index).

Reads the probe clones under probe/repos/ (not committed) and writes metadata-only JSON
(item presence, char counts, duplicate map, titles, kmf links) to data/.
No copyrighted text is written.
"""
import json, os, re, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
DATA = os.path.join(ROOT, 'data')
PROBE = os.path.join(ROOT, 'probe', 'repos')

def read_text(p):
    return open(p, 'rb').read().decode('utf-8', errors='replace')

# ---------- FindSimilarTPO ----------
base = os.path.join(PROBE, 'FindSimilarTPO', 'data', 'TPO')
items = []
dups = {}
content_by_key = {}
for n in range(1, 55):
    for k in range(1, 4):
        fn = f'{n}-{k}.txt'
        p = os.path.join(base, fn)
        exists = os.path.isfile(p)
        text = read_text(p).strip() if exists else ''
        items.append({'tpo': n, 'section': 'reading', 'item': f'passage-{k}', 'file': fn,
                      'present': bool(text), 'chars': len(text)})
        content_by_key[('reading', n, k)] = text
    for k in range(1, 5):
        fn = f'L{n}-{k}.txt'
        p = os.path.join(base, fn)
        exists = os.path.isfile(p)
        text = read_text(p).strip() if exists else ''
        items.append({'tpo': n, 'section': 'listening', 'item': f'lecture-{k}', 'file': fn,
                      'present': bool(text), 'chars': len(text)})
        content_by_key[('listening', n, k)] = text
    for k in range(1, 3):
        fn = f'C{n}-{k}.txt'
        p = os.path.join(base, fn)
        exists = os.path.isfile(p)
        text = read_text(p).strip() if exists else ''
        items.append({'tpo': n, 'section': 'listening', 'item': f'conversation-{k}', 'file': fn,
                      'present': bool(text), 'chars': len(text)})
        content_by_key[('listening', n, 100 + k)] = text

# duplicates: same section, same non-empty content, different (tpo,item)
groups = collections.defaultdict(list)
for key, text in content_by_key.items():
    if text:
        groups[text].append(key)
for text, keys in groups.items():
    if len(keys) > 1:
        keys = sorted(keys)
        first = keys[0]
        for other in keys[1:]:
            dups[f"{other[0][:4]}-{other[1]}-{other[2]}"] = f"{first[0][:4]}-{first[1]}-{first[2]}"

per = collections.Counter()
for it in items:
    if it['present']:
        per[it['section']] += 1

cov = {
    'source': 'SAOHPRWHG/FindSimilarTPO (GitHub)',
    'raw_base': 'https://raw.githubusercontent.com/SAOHPRWHG/FindSimilarTPO/master/',
    'path': 'data/TPO/<file>',
    'checked_at': '2026-10-04',
    'content_type': 'reading passages + listening transcripts (no questions/answers)',
    'tpo_range': '1-54',
    'counts': {'reading_passages': per['reading'], 'listening_items': per['listening'],
               'reading_expected': 54 * 3, 'listening_expected': 54 * 6},
    'empty_tpos': sorted({it['tpo'] for it in items if not it['present']}),
    'duplicates': dups,
    'items': items,
}
json.dump(cov, open(os.path.join(DATA, 'coverage.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('coverage.json:', cov['counts'], 'empty:', cov['empty_tpos'], 'dups:', len(dups))

# ---------- ddy-ddy ----------
ddy_dir = os.path.join(PROBE, 'TOEFL-TPO', 'data', 'json')
ddy_items = []
for fn in sorted(os.listdir(ddy_dir)):
    if not fn.endswith('.json') or fn == 'example.json':
        continue
    arr = json.loads(read_text(os.path.join(ddy_dir, fn)))
    for e in arr:
        if not re.match(r'^tpo-\d+-\d+$', str(e.get('id', ''))):
            continue
        url = e.get('link') or ''
        kmf = re.search(r'toefl\.kmf\.com/detail/read/([^"/.]+)', url)
        arts = e.get('article') or []
        ddy_items.append({
            'id': e.get('id'), 'title': e.get('title'), 'file': fn,
            'link': url, 'kmf_hash': kmf.group(1) if kmf else None,
            'paragraphs': len(arts), 'chars': sum(len(x) for x in arts),
        })
ddy = {
    'source': 'ddy-ddy/TOEFL-TPO (GitHub)',
    'raw_base': 'https://raw.githubusercontent.com/ddy-ddy/TOEFL-TPO/master/',
    'path': 'data/json/tpo-30-35.json … tpo-51-54.json',
    'checked_at': '2026-10-04',
    'content_type': 'structured reading passages (title + paragraphs + source link)',
    'counts': {'total': len(ddy_items), 'tpo_min': 30, 'tpo_max': 54},
    'items': ddy_items,
}
json.dump(ddy, open(os.path.join(DATA, 'ddy-index.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
by_tpo = collections.Counter(i['id'].split('-')[1] for i in ddy_items if i['id'])
print('ddy-index.json:', len(ddy_items), 'tpos:', len(by_tpo))
