"""Build jj index: 考满分「机经真题」板块 (/jj/order/27..30) -> 条目与详情页 URL。

Crawls public jj list pages of toefl.kmf.com (robots.txt allows all except /admin/ and /record),
one request per second, and writes metadata-only JSON (labels + URLs + lock state, no question content).

Boards: 27=阅读 read, 28=听力 listen, 29=口语 speak, 30=写作 write；各 5 页（/jj/order/{id}/{1..5}/0）。
时间维度：机经期数 batch 1..25（25 最新）；站点未提供发布日/年份。

Usage: python build_jj_index.py   (run from toefl-api/ dir or anywhere)
Output: ../data/jj-index.json  (relative to this script: <repo>/toefl-api/data/jj-index.json)
"""
import re, json, os, subprocess, time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'data', 'jj-index.json')
CACHE = os.path.join(HERE, '..', '.data', 'jj-list-cache')
os.makedirs(CACHE, exist_ok=True)
os.makedirs(os.path.dirname(OUT), exist_ok=True)

UA = 'toefl-api-research/1.0 (+educational aggregation; contact: local)'

BOARDS = [('read', 27), ('listen', 28), ('speak', 29), ('write', 30)]
PAGES = [1, 2, 3, 4, 5]

ITEM_RE = re.compile(r'<div class="practice-lists([^"]*)"([^>]*)>')


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


def parse_items(html, section, page):
    """Return list of item dicts from one jj list page."""
    items = []
    for m in ITEM_RE.finditer(html):
        cls, attrs = m.group(1), m.group(2)
        title = re.search(r'data-title="([^"]+)"', attrs)
        if not title:
            continue
        label = title.group(1).replace('&amp;', '&').strip()
        detail = re.search(r'data-detail="(/detail/(?:read|listen|speak|write)/[^"]+)"', attrs)
        did = re.search(r'data-id="(\d+)"', attrs)
        locked = 'js-lock-jj' in cls
        b = re.search(r'机经真题\s*(\d+)', label)
        k = re.search(r'(Passage|Set|Q|Task)\s*(\d+)', label)
        items.append({
            'section': section,
            'url': ('https://toefl.kmf.com' + detail.group(1)) if detail else None,
            'label': label,
            'batch': int(b.group(1)) if b else None,
            'kind': k.group(1) if k else None,
            'num': int(k.group(2)) if k else None,
            'item': f'{k.group(1)} {k.group(2)}' if k else None,
            'locked': locked,
            'data_id': did.group(1) if did else None,
            'page': page,
        })
    return items


def main():
    items = []
    per = {}
    for section, oid in BOARDS:
        print(f'== {section} (jj/order/{oid}) ==')
        seen = set()
        for p in PAGES:
            url = f'https://toefl.kmf.com/jj/order/{oid}/{p}/0'
            html = fetch(url)
            if not html:
                print(f'  {url} -> FAIL')
                continue
            page_items = parse_items(html, section, p)
            for it in page_items:
                key = (it['section'], it['label'])
                if key in seen:
                    continue
                seen.add(key)
                items.append(it)
            print(f'  {url} -> {len(page_items)} items')
        per[section] = len(seen)
        print(f'  => {section} unique: {len(seen)}')

    items.sort(key=lambda x: (
        ['read', 'listen', 'speak', 'write'].index(x['section']),
        -(x['batch'] or 0),
        (x['num'] or 0),
    ))

    free = sum(1 for it in items if not it['locked'])
    locked = sum(1 for it in items if it['locked'])
    per_section = {}
    for sec in ['read', 'listen', 'speak', 'write']:
        sub = [it for it in items if it['section'] == sec]
        per_section[sec] = {
            'total': len(sub),
            'free': sum(1 for it in sub if not it['locked']),
            'locked': sum(1 for it in sub if it['locked']),
            'batches_free': sorted({it['batch'] for it in sub if not it['locked'] and it['batch']}),
            'batches_locked': sorted({it['batch'] for it in sub if it['locked'] and it['batch']}),
        }

    doc = {
        'source': 'toefl.kmf.com (考满分) 机经真题板块 /jj/order/27..30',
        'robots': 'Allow: all except /admin/ and /record (checked 2026-10-05)',
        'crawl': 'public jj list pages (4 boards x 5 pages), 1 req/s, metadata only (labels + URLs + lock state)',
        'time_dimension': '机经期数 batch 1..25（25 最新）；站点未提供发布日/年份，批次即时间维度',
        'exam_form': 'section = TOEFL 四科（read/listen/speak/write）；item 为科内条目（Passage/Set/Q/Task）',
        'built_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'counts': {
            'total': len(items),
            **per,
            'free': free,
            'locked': locked,
            'per_section': per_section,
        },
        'lock_note': 'locked=true 的条目无 data-detail（需站点会员解锁），无公开详情 URL；免费条目可抓取',
        'items': items,
    }
    json.dump(doc, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('wrote', OUT)
    print('total', len(items), 'free', free, 'locked', locked)
    for sec, c in per_section.items():
        print(f"  {sec}: {c['total']} (free {c['free']} / locked {c['locked']}) free_batches={c['batches_free']} locked_batches={c['batches_locked']}")


if __name__ == '__main__':
    main()
