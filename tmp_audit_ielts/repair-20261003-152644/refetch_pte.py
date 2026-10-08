# -*- coding: utf-8 -*-
"""refetch_pte.py — I3 裁决用: 独立重抓 practicepteonline 页面原文 (单次请求, 无重试).

与 ielts-api/pte.mjs 不同源: 用 Python urllib 直接拉 WP REST API 原文, 原样保存,
不经过被测代码的 jsToJson / 解析逻辑. 遇 403/404/409/502 或网络错误立即停止后续请求
(规范第 5 节: 上游失败即记录并停止新上游请求).

用法:
  PYTHONUTF8=1 python refetch_pte.py            # 全部 15 个 slug
"""
import json
import pathlib
import ssl
import sys
import time
import urllib.request

BASE = pathlib.Path('C:/Users/weo/Desktop/api/tmp_audit_ielts')
OUT = BASE / 'repair-20261003-152644' / 'evidence' / 'i3'

SLUGS = [
    ('4-1', 'ielts-listening-test-165'), ('4-3', 'ielts-listening-test-167'),
    ('5-1', 'ielts-listening-test-161'), ('5-2', 'ielts-listening-test-162'),
    ('5-3', 'ielts-listening-test-163'), ('5-4', 'ielts-listening-test-164'),
    ('6-1', 'ielts-listening-test-157'), ('6-2', 'ielts-listening-test-158'),
    ('6-3', 'ielts-listening-test-159'), ('6-4', 'ielts-listening-test-160'),
    ('7-2', 'ielts-listening-test-154'), ('7-3', 'ielts-listening-test-155'),
    ('7-4', 'ielts-listening-test-156'),
    ('12-1', 'ielts-listening-test-89'), ('17-4', 'ielts-listening-test-192'),
]

STOP_STATUS = {403, 404, 409, 502}

ctx = ssl.create_default_context()


def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) diagnostic-refetch/1.0',
        'Accept': 'application/json',
    })
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            body = r.read()
            hdrs = {k.lower(): v for k, v in r.getheaders()}
            return r.status, hdrs, body, time.time() - t0, None
    except urllib.error.HTTPError as e:
        body = b''
        try:
            body = e.read()
        except Exception:
            pass
        return e.code, {}, body, time.time() - t0, None
    except Exception as e:  # noqa: BLE001
        return None, {}, b'', time.time() - t0, repr(e)


def main():
    stamp = time.strftime('%Y%m%d-%H%M%S')
    day = OUT / f'pte_refetch_{stamp}'
    day.mkdir(parents=True, exist_ok=True)
    summary = {'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'), 'dir': str(day), 'items': []}
    stopped_at = None
    for key, slug in SLUGS:
        url = ('https://practicepteonline.com/wp-json/wp/v2/pages'
               f'?slug={slug}&_fields=id,slug,title,content')
        status, hdrs, body, secs, err = fetch(url)
        rec = {'key': key, 'slug': slug, 'url': url, 'status': status,
               'bytes': len(body), 'secs': round(secs, 2), 'error': err,
               'content_type': hdrs.get('content-type'), 'server': hdrs.get('server')}
        if body:
            fn = day / f'{key}_slug{slug}.json'
            fn.write_bytes(body)
            rec['file'] = str(fn)
        summary['items'].append(rec)
        print(f"{key:>5} slug={slug:>4} status={status} bytes={len(body):>8} {secs:5.2f}s {err or ''}")
        sys.stdout.flush()
        if status in STOP_STATUS or status is None:
            stopped_at = key
            print(f'!! stop: {key} returned {status} {err or ""} — no further requests')
            break
        time.sleep(0.9)
    summary['stopped_at'] = stopped_at
    sp = day / 'summary.json'
    sp.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'saved {sp}')


if __name__ == '__main__':
    main()
