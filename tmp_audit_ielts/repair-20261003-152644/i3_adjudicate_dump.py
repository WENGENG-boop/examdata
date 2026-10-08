# -*- coding: utf-8 -*-
"""i3_adjudicate_dump.py — I3 答案差异裁决辅助: 答案页行级/字符级/渲染转储 (诊断脚本, 不改被测代码)

用法 (examdata venv python):
  python i3_adjudicate_dump.py lines --book 17 --page 125 [--grep 38] [--win 3] [--cols]
  python i3_adjudicate_dump.py raw   --book 17 --page 125 --rect x0,y0,x1,y1 [--find steam]
  python i3_adjudicate_dump.py png   --book 17 --page 125 --rect x0,y0,x1,y1 --out out.png [--zoom 4]
  python i3_adjudicate_dump.py find  --book 17 --text "Questions 31" [--regex] [--icase]
"""
import argparse
import re
import sys

import pymupdf

BASE = 'C:/Users/weo/Desktop/api/tmp_audit_ielts'
DOWN = BASE + '/downloads'


def open_book(book):
    return pymupdf.open(f'{DOWN}/book_{book}.pdf')


def row_groups(ws, tol=3.0):
    rows = []
    for w in sorted(ws, key=lambda w: (w[1], w[0])):
        if rows and w[1] - rows[-1][0][1] <= tol:
            rows[-1].append(w)
        else:
            rows.append([w])
    return rows


def parse_rect(s):
    x0, y0, x1, y1 = (float(v) for v in s.split(','))
    return pymupdf.Rect(x0, y0, x1, y1)


def cmd_lines(args):
    doc = open_book(args.book)
    page = doc[args.page - 1]
    words = [tuple(w[:5]) for w in page.get_text('words')]
    rows = row_groups(words)
    pat = re.compile(re.escape(args.grep), re.I) if args.grep else None
    hits = set()
    if pat:
        for i, r in enumerate(rows):
            text = ' '.join(w[4] for w in r)
            if pat.search(text):
                hits.add(i)
    if args.grep:
        shown = set()
        for i in hits:
            for j in range(max(0, i - args.win), min(len(rows), i + args.win + 1)):
                shown.add(j)
    else:
        shown = set(range(len(rows)))
    print(f'# book{args.book} page {args.page} (1-based)  W={page.rect.width:.1f} H={page.rect.height:.1f}  rows={len(rows)}')
    for i in sorted(shown):
        r = rows[i]
        text = ' '.join(w[4] for w in sorted(r, key=lambda w: (w[1], w[0])))
        mark = '>>' if i in hits else '  '
        y0 = min(w[1] for w in r)
        y1 = max(w[3] for w in r)
        x0 = min(w[0] for w in r)
        x1 = max(w[2] for w in r)
        print(f'{mark}[{i:03d}] y={y0:7.1f}..{y1:7.1f} x={x0:6.1f}..{x1:6.1f} | {text}')
        if args.cols:
            for w in sorted(r, key=lambda w: (w[1], w[0])):
                print(f'      tok x={w[0]:6.1f}..{w[2]:6.1f} y={w[1]:7.1f} {w[4]!r}')
    doc.close()


def cmd_raw(args):
    doc = open_book(args.book)
    page = doc[args.page - 1]
    rect = parse_rect(args.rect) if args.rect else None
    d = page.get_text('rawdict', clip=rect)
    find = args.find
    for b in d.get('blocks', []):
        for l in b.get('lines', []):
            for s in l.get('spans', []):
                text = ''.join(ch['c'] for ch in s.get('chars', []))
                if find and find.lower() not in text.lower():
                    continue
                print(f'--- span font={s["font"]!r} size={s["size"]:.2f} bbox={[round(v,1) for v in s["bbox"]]} text={text!r}')
                for ch in s.get('chars', []):
                    print(f'    ch {ch["c"]!r} U+{ord(ch["c"]):04X} origin=({ch["origin"][0]:.1f},{ch["origin"][1]:.1f}) bbox={[round(v,1) for v in ch["bbox"]]}')
    doc.close()


def cmd_png(args):
    doc = open_book(args.book)
    page = doc[args.page - 1]
    rect = parse_rect(args.rect)
    mat = pymupdf.Matrix(args.zoom, args.zoom)
    pix = page.get_pixmap(matrix=mat, clip=rect)
    pix.save(args.out)
    print(f'saved {args.out}  {pix.width}x{pix.height}px  rect={rect}')
    doc.close()


def cmd_find(args):
    doc = open_book(args.book)
    pat = re.compile(args.text if args.regex else re.escape(args.text), re.I if args.icase else 0)
    n = 0
    for i in range(doc.page_count):
        t = doc[i].get_text()
        if pat.search(t):
            n += 1
            lines = t.splitlines()
            ctx = [ln.strip() for ln in lines if pat.search(ln)]
            print(f'p{i + 1}: {len(ctx)} hit(s)')
            for ln in ctx[:4]:
                print(f'    | {ln[:200]}')
    print(f'# total pages with hit: {n}')
    doc.close()


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('lines')
    p.add_argument('--book', type=int, required=True)
    p.add_argument('--page', type=int, required=True)
    p.add_argument('--grep', default=None)
    p.add_argument('--win', type=int, default=3)
    p.add_argument('--cols', action='store_true')
    p.set_defaults(func=cmd_lines)
    p = sub.add_parser('raw')
    p.add_argument('--book', type=int, required=True)
    p.add_argument('--page', type=int, required=True)
    p.add_argument('--rect', default=None)
    p.add_argument('--find', default=None)
    p.set_defaults(func=cmd_raw)
    p = sub.add_parser('png')
    p.add_argument('--book', type=int, required=True)
    p.add_argument('--page', type=int, required=True)
    p.add_argument('--rect', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--zoom', type=float, default=4.0)
    p.set_defaults(func=cmd_png)
    p = sub.add_parser('find')
    p.add_argument('--book', type=int, required=True)
    p.add_argument('--text', required=True)
    p.add_argument('--regex', action='store_true')
    p.add_argument('--icase', action='store_true')
    p.set_defaults(func=cmd_find)
    args = ap.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
