"""Build kmf index: Official TPO items -> detail page URLs for reading/listening/speaking/writing.

Crawls public list pages of toefl.kmf.com (robots.txt allows all except /admin/ and /record),
one request per second, and writes metadata-only JSON (labels + URLs, no copyrighted content).

Usage: python build_kmf_index.py   (run from toefl-api/ dir or anywhere)
Output: ../data/kmf-index.json  (relative to this script: <repo>/toefl-api/data/kmf-index.json)
"""
import re, json, os, subprocess, time, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'data', 'kmf-index.json')
CACHE = os.path.join(HERE, '..', '.data', 'kmf-list-cache')
os.makedirs(CACHE, exist_ok=True)
os.makedirs(os.path.dirname(OUT), exist_ok=True)

UA = 'toefl-api-research/1.0 (+educational aggregation; contact: local)'

def fetch(url):
    """Fetch with on-disk cache; 1s polite delay when hitting the network."""
    key = re.sub(r'[^A-Za-z0-9]+', '_', url).strip('_')[:120] + '.html'
    path = os.path.join(CACHE, key)
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return open(path, 'rb').read().decode('utf-8', errors='replace')
    r = subprocess.run(['curl', '-s', '-L', '-A', UA, '-o', path, '-w', '%{http_code}', url],
                       capture_output=True, text=True)
    code = r.stdout.strip()
    time.sleep(1.0)
    if not os.path.exists(path) or os.path.getsize(path) < 1000:
        return None
    return open(path, 'rb').read().decode('utf-8', errors='replace')

ITEM_RE = re.compile(
    r'data-detail="(/detail/(read|listen|speak|write)/[^"]+)"\s+data-title="([^"]+)"')

def parse_items(html):
    """Return list of (section, url, label)."""
    items = []
    for m in ITEM_RE.finditer(html):
        url, sec, label = m.group(1), m.group(2), m.group(3)
        label = label.replace('&amp;', '&').strip()
        if re.match(r'^Official\s+\d+', label):
            items.append((sec, url, label))
    return items

def try_urls(urls):
    got = []
    for u in urls:
        h = fetch(u)
        if h and 'Official' in h:
            items = parse_items(h)
            if items:
                got.extend(items)
                print(f'  {u} -> {len(items)} items')
                return got
        print(f'  miss: {u}')
    return got

def blocks(section, n):
    if section == 'read':
        return [f'https://toefl.kmf.com/read/ets/order/{n}/0', f'https://toefl.kmf.com/read/ets/order/{n}/']
    if section == 'listen':
        return [f'https://toefl.kmf.com/listen/ets/new-order/{n}/0', f'https://toefl.kmf.com/listen/ets/new-order/{n}/']
    if section == 'write':
        return [f'https://toefl.kmf.com/write/ets/order/{n}/', f'https://toefl.kmf.com/write/ets/order/{n}/0']
    if section == 'speak':
        return [f'https://toefl.kmf.com/speak/ets/new-order/{n}/0', f'https://toefl.kmf.com/speak/ets/new-order/{n}/', f'https://toefl.kmf.com/speak/ets/'] if n == 1 else \
               [f'https://toefl.kmf.com/speak/ets/new-order/{n}/0', f'https://toefl.kmf.com/speak/ets/new-order/{n}/']
    raise ValueError(section)

def main():
    all_items = {}
    per = {}
    for sec in ['read', 'listen', 'speak', 'write']:
        print(f'== {sec} ==')
        seen = set()
        for n in range(1, 14):
            for (s, url, label) in try_urls(blocks(sec, n)):
                if url in seen:
                    continue
                seen.add(url)
                all_items[url] = {'section': s, 'url': 'https://toefl.kmf.com' + url, 'label': label}
        per[sec] = len(seen)
        print(f'  => {sec} unique: {len(seen)}')

    items = sorted(all_items.values(), key=lambda x: (
        x['section'],
        -int(re.search(r'Official\s+(\d+)', x['label']).group(1)) if re.search(r'Official\s+(\d+)', x['label']) else 0,
        x['label']))
    # attach official number + parsed extra
    for it in items:
        m = re.search(r'Official\s+(\d+)', it['label'])
        it['official'] = int(m.group(1)) if m else None
        mm = re.search(r'(Passage \d+|Set \d+|Task \d+)', it['label'])
        it['item'] = mm.group(1) if mm else None

    officials = sorted({it['official'] for it in items if it['official']})
    doc = {
        'source': 'toefl.kmf.com (考满分) public ETS Official practice lists',
        'robots': 'Allow: all except /admin/ and /record (checked 2026-10-04)',
        'crawl': 'public list pages, 1 req/s, metadata only (labels + URLs, no question content)',
        'built_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'counts': {'total': len(items), **{k: v for k, v in per.items()}},
        'officials_covered': officials,
        'items': items,
    }
    json.dump(doc, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('wrote', OUT)
    print('total', len(items), 'sections', per)
    print('officials', officials[0] if officials else None, '..', officials[-1] if officials else None, len(officials))

if __name__ == '__main__':
    main()
