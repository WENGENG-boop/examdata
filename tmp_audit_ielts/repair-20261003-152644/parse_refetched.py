# -*- coding: utf-8 -*-
"""parse_refetched.py — I3 裁决证据: 独立解析重抓的 pte 页面答案区.

不依赖被测代码: 纯 regex + 号码链. 输出 extracted_answers.json 供比对.
"""
import json
import pathlib
import re
import html as htmlmod

DIR = pathlib.Path('C:/Users/weo/Desktop/api/tmp_audit_ielts/repair-20261003-152644/evidence/i3/pte_refetch_20261003-163918')
OUT = DIR / 'extracted_answers.json'


def extract_answers(content_html):
    t = re.sub(r'<[^>]+>', ' ', content_html)
    t = htmlmod.unescape(t)
    t = re.sub(r'[ \t\r\n]+', ' ', t)
    idx = t.rfind('Show Answers')
    seg = t[idx:] if idx >= 0 else t
    answers = {}
    pos = 0
    for q in range(1, 41):
        m = re.search(rf'(?<![0-9]){q}\.\s*', seg[pos:])
        if not m:
            continue
        start = pos + m.end()
        if q < 40:
            m2 = re.search(rf'(?<![0-9]){q + 1}\.\s*', seg[start:])
            end = start + m2.start() if m2 else len(seg)
        else:
            end = len(seg)
        answers[q] = seg[start:end].strip()
        pos = start
    return answers


def main():
    out = {}
    for f in sorted(DIR.glob('*_slug*.json')):
        key = f.name.split('_slug')[0]
        d = json.loads(f.read_text(encoding='utf-8'))
        if not d:
            out[key] = {'error': 'empty json'}
            continue
        page = d[0]
        ans = extract_answers(page['content']['rendered'])
        out[key] = {
            'slug': page.get('slug'),
            'title': page.get('title', {}).get('rendered'),
            'count': len(ans),
            'answers': {str(k): v for k, v in ans.items()},
        }
        print(f"{key:>5} {page.get('slug'):<28} count={len(ans)}")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print('saved', OUT)


if __name__ == '__main__':
    main()
