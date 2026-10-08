#!/usr/bin/env python3
"""Download the PDFs listed in testdata/manifest.json.

Source order: fraft (small, fast) -> PapaCambridge (full history).
Files land in testdata/pdf/<syllabus>/<file>. Existing non-empty files are
skipped, so the script is safe to re-run. Concurrency is capped at 4 and every
download is retried at most 3 times; a response that does not start with %PDF
is treated as a failure rather than written to disk.

Usage:
  python tools/fetch_testdata.py                # everything in the manifest
  python tools/fetch_testdata.py 0580 9709      # only these syllabuses
  python tools/fetch_testdata.py --workers 4
"""
import json, os, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, 'testdata', 'manifest.json')
PDFDIR = os.path.join(ROOT, 'testdata', 'pdf')
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15'
SOURCES = [
    'https://cie.fraft.cn/obj/Common/Fetch/redir/{f}',
    'https://pastpapers.papacambridge.com/directories/CAIE/CAIE-pastpapers/upload/{f}',
]


def fetch(url, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=90) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last = f'HTTP {e.code}'
            if e.code < 500:
                break
        except Exception as e:
            last = f'{type(e).__name__}: {e}'
        if i < tries - 1:
            time.sleep(1 + i)
    raise RuntimeError(last or 'download failed')


def one(job):
    code, fn = job
    dest = os.path.join(PDFDIR, code, fn)
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return code, fn, 'skip', ''
    errs = []
    for tmpl in SOURCES:
        try:
            b = fetch(tmpl.format(f=fn))
            if not b.startswith(b'%PDF'):
                raise ValueError('response is not a PDF')
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            tmp = dest + '.part'
            with open(tmp, 'wb') as fh:
                fh.write(b)
            os.replace(tmp, dest)
            return code, fn, 'ok', f'{len(b)} B'
        except Exception as e:
            errs.append(str(e))
    return code, fn, 'error', ' | '.join(errs)


def main():
    argv = sys.argv[1:]
    workers = 4
    if '--workers' in argv:
        i = argv.index('--workers')
        workers = int(argv[i + 1])
        del argv[i:i + 2]
    want = set(argv)
    man = json.load(open(MANIFEST, encoding='utf-8'))
    jobs = [(code, s['file']) for code, sub in man['subjects'].items()
            if not want or code in want for s in sub['samples']]
    print(f'{len(jobs)} files from manifest, {workers} workers', flush=True)
    counts = {'ok': 0, 'skip': 0, 'error': 0}
    failures = []
    with ThreadPoolExecutor(workers) as ex:
        for code, fn, status, detail in ex.map(one, jobs):
            counts[status] += 1
            if status == 'error':
                failures.append(f'{code}/{fn}: {detail}')
                print(f'  ERR {code}/{fn}: {detail}', flush=True)
    print(f"ok={counts['ok']} skip={counts['skip']} error={counts['error']}")
    if failures:
        print('failed files:')
        for f in failures:
            print(' ', f)
        sys.exit(1)


if __name__ == '__main__':
    main()
