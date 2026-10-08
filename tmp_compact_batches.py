"""Compact review view for main-agent review of missing batches.

Usage: python tmp_compact_batches.py <slug> [<slug> ...] > tmp_cb_<slug>.txt

Prints: unit point lists (only units referenced by the missing batches),
then one compact line per question:
  qid|number_label|unit|cur:CODE(conf);...|stem-flattened
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

EXPORT = pathlib.Path('.data/tagging/review-export')
MISSING = pathlib.Path('tmp_review_missing_items.txt')


def flatten(text, limit):
    t = text or ''
    t = re.sub(r'\.{6,}', ' [..] ', t)
    t = re.sub(r'[_\-]{6,}', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t[:limit]


def main(slugs):
    missing = {}
    for line in MISSING.read_text(encoding='utf-8').splitlines():
        s, b = line.split('/')
        missing.setdefault(s, []).append(b)
    for slug in slugs:
        batches = sorted(missing.get(slug, []))
        pts = json.loads((EXPORT / slug / f'points-{slug}.json').read_text(encoding='utf-8'))
        units = pts['units']
        used_units = set()
        rows_by_batch = {}
        for b in batches:
            fp = EXPORT / slug / 'batches' / f'{b}.jsonl'
            rows = [json.loads(l) for l in fp.read_text(encoding='utf-8').splitlines() if l.strip()]
            rows_by_batch[b] = rows
            used_units.update(r['unit_code'] for r in rows)
        print(f'##### {slug} · missing {len(batches)} batches · '
              f'{sum(len(v) for v in rows_by_batch.values())} questions')
        for u in sorted(used_units):
            plist = units.get(u) or []
            print(f'== unit {u} ({len(plist)} points)')
            for p in plist:
                print(f'   {p["code"]} = {flatten(p["name"], 70)}')
        for b in batches:
            rows = rows_by_batch[b]
            print(f'--- {slug}/{b} n={len(rows)}')
            for r in rows:
                cur = ';'.join(f'{c["code"]}({c["confidence"]:.2f})' for c in r['current'])
                print(f'{r["question_id"]}|{r.get("number_label","")}|{r["unit_code"]}|{cur}|'
                      f'{flatten(r.get("stem"), 220)}')


if __name__ == '__main__':
    main(sys.argv[1:])
