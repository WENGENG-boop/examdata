#!/usr/bin/env python3
"""CIE/CAIE past papers API: fraft (default) + PapaCambridge (full history) + official site.

CLI:
  cie_api.py subjects [--source fraft|papa|official] [--level igcse|as-and-a-level|o-level]
  cie_api.py sessions 0580
  cie_api.py papers 0580,9709 [--source fraft|papa|official] [--year 2022|2020-2023] [--season s,w] [--type qp,ms] [--out f.json]
  cie_api.py download 0580 [same filters] [--dir DIR]
  cie_api.py serve [--port 8765]
HTTP API (serve):
  GET /api/subjects?source=fraft&level=igcse
  GET /api/sessions?syllabus=0580
  GET /api/papers?syllabus=0580,9709&year=2022&season=s&type=qp,ms&source=fraft
  GET /api/download?syllabus=0580&year=2024&season=s&type=qp,ms
source: fraft is the default and falls back to papa on error or empty result
season: m=Feb/March s=May/June w=Oct/Nov (fraft sends Mar/Jun/Nov)
"""
import sys, os, re, json, html, time, argparse, urllib.request, urllib.parse, urllib.error
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15'
OFF = 'https://www.cambridgeinternational.org'
PAPA = 'https://pastpapers.papacambridge.com'
PDF = PAPA + '/directories/CAIE/CAIE-pastpapers/upload/'
FRAFT = 'https://cie.fraft.cn/obj/Common'
FRAFT_PDF = FRAFT + '/Fetch/redir/'
FRAFT_SEASON = {'m': 'Mar', 's': 'Jun', 'w': 'Nov'}
LEVELS = ['igcse', 'as-and-a-level', 'o-level']
CACHE = os.path.expanduser('~/.cache/cie_api')
TTL = 86400
DL_DIR = '/var/minis/workspace/cie_papers'
SEASON = {'m': 'Feb/March', 's': 'May/June', 'w': 'Oct/Nov'}
TYPES = {'qp': 'question_paper', 'ms': 'mark_scheme', 'er': 'examiner_report', 'gt': 'grade_thresholds',
         'in': 'insert', 'ci': 'confidential_instructions', 'pm': 'pre_release', 'sf': 'source_files',
         'ir': 'instructions', 'sp': 'specimen_paper', 'sm': 'specimen_mark_scheme', 'sy': 'syllabus'}
os.makedirs(CACHE, exist_ok=True)


def fetch(url, binary=False, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                b = r.read()
            return b if binary else b.decode('utf-8', 'replace')
        except urllib.error.HTTPError as e:
            if e.code == 404 and not binary:
                return e.read().decode('utf-8', 'replace')
            if i == tries - 1 or e.code < 500:
                raise
        except Exception:
            if i == tries - 1:
                raise
        time.sleep(1 + i)


def post(url, data='', tries=3):
    body = data.encode() if data else b''
    headers = {'User-Agent': UA}
    if body:
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    else:
        headers['Content-Length'] = '0'
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode('utf-8', 'replace'))
        except urllib.error.HTTPError as e:
            if i == tries - 1 or e.code < 500:
                raise
        except Exception:
            if i == tries - 1:
                raise
        time.sleep(1 + i)


def cached(key, fn):
    p = os.path.join(CACHE, re.sub(r'[^\w.-]', '_', key) + '.json')
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < TTL:
        return json.load(open(p))
    d = fn()
    json.dump(d, open(p, 'w'))
    return d


def season_of(s):
    s = s.lower()
    return 'm' if 'mar' in s else 's' if 'jun' in s else 'w' if 'nov' in s else None


def nice(slug, code):
    return slug[:-(len(code) + 1)].replace('-', ' ').title()


# ---------- PapaCambridge (full history) ----------
def papa_subjects(level=None):
    out = []
    for lv in ([level] if level else LEVELS):
        def f(lv=lv):
            pg = fetch(f'{PAPA}/papers/caie/{lv}')
            d = {}
            for slug, code in re.findall(r'papers/caie/([a-z0-9-]+-(\d{4}))"', pg):
                d.setdefault(code, {'code': code, 'level': lv, 'name': nice(slug, code), 'slug': slug,
                                    'url': f'{PAPA}/papers/caie/{slug}'})
            return list(d.values())
        out += cached('papa_subjects_' + lv, f)
    return out


def papa_subject(code):
    for s in papa_subjects():
        if s['code'] == code:
            return s
    raise KeyError(f'syllabus {code} not found on PapaCambridge')


def papa_sessions(code):
    s = papa_subject(code)
    def f():
        pg = fetch(s['url'])
        d = {}
        for full, y, sfx in re.findall(r'papers/caie/(' + re.escape(s['slug']) + r'-(\d{4})-([a-z-]+))"', pg):
            if 'topical' in sfx:
                continue
            d[full] = {'year': int(y), 'season': season_of(sfx), 'label': f'{y} {sfx}',
                       'url': f'{PAPA}/papers/caie/{full}'}
        return sorted(d.values(), key=lambda x: (x['year'], x['season'] or ''))
    return cached('papa_sessions_' + code, f)


FN = re.compile(r'^(\d{4})_([msw])(\d{2})_([a-z]+)(?:_(\w+))?\.pdf$', re.I)


def parse_file(fn):
    it = {'file': fn, 'url': PDF + fn}
    m = FN.match(fn)
    if not m:
        it['type'] = 'other'
        return it
    code, s, yy, t, comp = m.groups()
    s, t = s.lower(), t.lower()
    it.update(syllabus=code, year=2000 + int(yy), season=s, season_name=SEASON[s],
              type_code=t, type=TYPES.get(t, t), component=comp,
              paper=comp[0] if comp and comp[0].isdigit() else None,
              variant=comp[1:] if comp and comp.isdigit() and len(comp) > 1 else None)
    return it


def papa_papers(code, years=None, seasons=None, types=None):
    sess = [s for s in papa_sessions(code)
            if (not years or s['year'] in years) and (not seasons or s['season'] in seasons)]
    def one(s):
        key = 'papa_files_' + s['url'].rsplit('/', 1)[-1]
        files = cached(key, lambda: sorted(set(re.findall(r'upload/(' + code + r'_[^"/?]+\.pdf)', fetch(s['url'])))))
        return [parse_file(f) for f in files]
    with ThreadPoolExecutor(4) as ex:
        lists = list(ex.map(one, sess))
    return [i for l in lists for i in l
            if (not types or i.get('type_code') in types) and (not years or i.get('year') in years)]


# ---------- fraft (default source) ----------
def fraft_subjects(level=None):
    def f():
        out = []
        for s in post(FRAFT + '/Subject/combo'):
            text = s.get('text') or ''
            after = text.split(' - ', 1)[1] if ' - ' in text else text
            ms = list(re.finditer(r'\(([^()]*)\)', after))
            lv = ms[-1].group(1).strip().upper() if ms else ''
            name = (after[:ms[-1].start()] if ms else after).strip()
            out.append({'code': s.get('value'), 'level': 'igcse' if lv == 'IGCSE' else
                        'as-and-a-level' if lv == 'AS/A2' else lv.lower(),
                        'name': name, 'slug': None, 'url': FRAFT})
        return out
    subs = cached('fraft_subjects', f)
    return [s for s in subs if not level or s['level'] == level]


def fraft_papers(code, years=None, seasons=None, types=None):
    if not years or not seasons:
        raise ValueError('fraft cannot enumerate years/seasons; both --year and --season are required')
    items = []
    for y in sorted(years):
        for s in seasons:
            if s not in FRAFT_SEASON:
                raise ValueError(f'unknown season {s!r} (expected one of {sorted(FRAFT_SEASON)})')
            fs = FRAFT_SEASON[s]
            body = urllib.parse.urlencode({'subject': code, 'year': y, 'season': fs})
            d = cached(f'fraft_files_{code}_{y}_{fs}', lambda b=body: post(FRAFT + '/Fetch/renum', b))
            for row in d.get('rows', []):
                it = parse_file(row['file'])
                it['url'] = FRAFT_PDF + it['file']
                items.append(it)
    return [i for i in items if not types or i.get('type_code') in types]


# ---------- Official site (limited, recent only) ----------
def official_subjects():
    def f():
        pg = fetch(OFF + '/programmes-and-qualifications/cambridge-igcse/subjects/')
        d = {}
        for slug, code in re.findall(r'/programmes-and-qualifications/view/([a-z0-9-]+-(\d{4}))/', pg):
            d.setdefault(code, {'code': code, 'name': nice(slug, code), 'slug': slug,
                                'url': f'{OFF}/programmes-and-qualifications/{slug}/past-papers/'})
        return list(d.values())
    return cached('official_subjects', f)


OMON = {'march': 'm', 'february': 'm', 'june': 's', 'november': 'w'}
OTYPE = [('examiner-report', 'er'), ('mark-scheme', 'ms'), ('question-paper', 'qp'), ('insert', 'in'),
         ('grade-threshold', 'gt'), ('confidential', 'ci')]


def official_papers(code, years=None, seasons=None, types=None):
    s = next((x for x in official_subjects() if x['code'] == code), None)
    if not s:
        raise KeyError(f'syllabus {code} not found on official site')
    pg = fetch(s['url'])
    items, seen = [], set()
    for href, txt in re.findall(r'<a[^>]+href="([^"]+\.pdf)"[^>]*>(.*?)</a>', pg, re.S | re.I):
        url = href if href.startswith('http') else OFF + href
        if url in seen:
            continue
        seen.add(url)
        fname = url.rsplit('/', 1)[-1]
        low = fname.lower()
        txt = re.sub(r'<[^>]+>|<!--|-->', '', re.sub(r'<!--.*?-->', '', txt, flags=re.S))
        if 'specimen' in low:
            t = 'sm' if 'mark-scheme' in low else 'sp'
        else:
            t = next((c for k, c in OTYPE if k in low), 'other')
        m = re.search(r'(march|february|june|november)-(\d{4})', low)
        y = re.search(r'(20\d\d)', low)
        p = re.search(r'paper-(\d+)', low)
        comp = p.group(1) if p else None
        sea = OMON[m.group(1)] if m else None
        it = {'file': fname, 'url': url, 'title': ' '.join(html.unescape(txt).split()), 'syllabus': code,
              'year': int(m.group(2)) if m else (int(y.group(1)) if y else None),
              'season': sea, 'season_name': SEASON.get(sea), 'type_code': t, 'type': TYPES.get(t, t),
              'component': comp, 'paper': comp[0] if comp else None,
              'variant': comp[1:] if comp and len(comp) > 1 else None}
        if years and it['year'] not in years:
            continue
        if seasons and it['season'] not in seasons:
            continue
        if types and t not in types:
            continue
        items.append(it)
    return items


# ---------- query / download ----------
def query(codes, source='fraft', years=None, seasons=None, types=None):
    res, total = {}, 0
    for c in codes:
        fallback = None
        try:
            if source == 'official':
                items = official_papers(c, years, seasons, types)
            elif source == 'papa':
                items = papa_papers(c, years, seasons, types)
            else:
                try:
                    items = fraft_papers(c, years, seasons, types)
                    if not items:
                        fallback = 'fraft returned no files'
                except Exception as e:
                    fallback = f'{type(e).__name__}: {e}'
                if fallback:
                    items = papa_papers(c, years, seasons, types)
            rec = {'count': len(items), 'items': items}
            if fallback:
                rec['fallback'] = fallback
            res[c] = rec
            total += len(items)
        except Exception as e:
            res[c] = {'error': f'{type(e).__name__}: {e}'}
    return {'source': source,
            'filters': {'year': sorted(years) if years else None, 'season': seasons, 'type': types},
            'total': total, 'results': res}


def download(result, dest=DL_DIR, workers=4):
    jobs = [(c, i) for c, r in result['results'].items() for i in r.get('items', [])]
    def one(job):
        c, i = job
        p = os.path.join(dest, c, i['file'])
        if os.path.exists(p) and os.path.getsize(p) > 0:
            return {'file': i['file'], 'status': 'exists', 'path': p}
        try:
            b = fetch(i['url'], binary=True)
            if not b.startswith(b'%PDF'):
                raise ValueError('response is not a PDF')
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p + '.part', 'wb') as f:
                f.write(b)
            os.replace(p + '.part', p)
            return {'file': i['file'], 'status': 'ok', 'bytes': len(b), 'path': p}
        except Exception as e:
            return {'file': i['file'], 'status': 'error', 'error': str(e)}
    with ThreadPoolExecutor(workers) as ex:
        out = list(ex.map(one, jobs))
    summ = {k: sum(1 for o in out if o['status'] == k) for k in ('ok', 'exists', 'error')}
    return {'dir': dest, 'summary': summ, 'files': out}


def p_years(v):
    if not v:
        return None
    ys = set()
    for part in str(v).split(','):
        part = part.strip()
        if '-' in part:
            a, b = part.split('-')
            ys.update(range(int(a), int(b) + 1))
        elif part:
            ys.add(int(part))
    return ys


def p_list(v):
    return [x.strip().lower() for x in str(v).split(',') if x.strip()] if v else None


# ---------- HTTP server ----------
class H(BaseHTTPRequestHandler):
    def reply(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False, indent=2).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        src = q.get('source', 'fraft')
        try:
            if u.path in ('/', '/api', '/api/'):
                return self.reply(200, {'usage': __doc__})
            if u.path == '/api/subjects':
                return self.reply(200, fraft_subjects(q.get('level')) if src == 'fraft'
                                  else papa_subjects(q.get('level')) if src == 'papa' else official_subjects())
            if u.path not in ('/api/sessions', '/api/papers', '/api/download'):
                return self.reply(404, {'error': 'unknown endpoint'})
            if 'syllabus' not in q:
                return self.reply(400, {'error': 'missing syllabus'})
            codes = p_list(q['syllabus'])
            if u.path == '/api/sessions':
                return self.reply(200, {c: papa_sessions(c) for c in codes})
            r = query(codes, src, p_years(q.get('year')), p_list(q.get('season')), p_list(q.get('type')))
            if u.path == '/api/papers':
                return self.reply(200, r)
            return self.reply(200, download(r, q.get('dir', DL_DIR)))
        except Exception as e:
            self.reply(500, {'error': f'{type(e).__name__}: {e}'})

    def log_message(self, *a):
        pass


def main():
    ap = argparse.ArgumentParser(description='CIE past papers API')
    sp = ap.add_subparsers(dest='cmd', required=True)
    a = sp.add_parser('subjects'); a.add_argument('--source', default='fraft', choices=['fraft', 'papa', 'official']); a.add_argument('--level')
    a = sp.add_parser('sessions'); a.add_argument('syllabus')
    for name in ('papers', 'download'):
        a = sp.add_parser(name); a.add_argument('syllabus')
        a.add_argument('--source', default='fraft', choices=['fraft', 'papa', 'official'])
        a.add_argument('--year'); a.add_argument('--season'); a.add_argument('--type')
        a.add_argument('--dir', default=DL_DIR)
    for a in sp.choices.values():
        if a.prog.split()[-1] != 'serve':
            a.add_argument('--out')
    a = sp.add_parser('serve'); a.add_argument('--port', type=int, default=8765); a.add_argument('--host', default='127.0.0.1')
    g = ap.parse_args()
    if g.cmd == 'serve':
        print(f'serving on http://{g.host}:{g.port}/api', flush=True)
        ThreadingHTTPServer((g.host, g.port), H).serve_forever()
        return
    if g.cmd == 'subjects':
        r = fraft_subjects(g.level) if g.source == 'fraft' \
            else papa_subjects(g.level) if g.source == 'papa' else official_subjects()
    elif g.cmd == 'sessions':
        r = {c: papa_sessions(c) for c in p_list(g.syllabus)}
    else:
        r = query(p_list(g.syllabus), g.source, p_years(g.year), p_list(g.season), p_list(g.type))
        if g.cmd == 'download':
            r = download(r, g.dir)
    out = json.dumps(r, ensure_ascii=False, indent=2)
    if getattr(g, 'out', None):
        open(g.out, 'w').write(out)
        print('saved', g.out)
    else:
        print(out)


if __name__ == '__main__':
    main()
