#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Health scan for *.ans.txt files: report data lines that are not clean 2-token lines.

Clean data line: `qid CODE` or `qid OK` or `qid ?` (exactly 2 whitespace-separated tokens).
Dirty = trailing comment / extra tokens — will break tmp_selfjudge_ingest.py.
Usage: python tmp_ans_health.py [root ...]  (default: tmp_selfjudge/unt tmp_selfjudge/r2)
"""
import sys
from pathlib import Path

roots = sys.argv[1:] or ['tmp_selfjudge/unt', 'tmp_selfjudge/r2']
files = []
for r in roots:
    p = Path(r)
    files.extend(sorted(p.glob('*/*.ans.txt')))

dirty_total = 0
n_ok = 0
for f in files:
    try:
        lines = f.read_text(encoding='utf-8').splitlines()
    except Exception as e:
        print(f'ERR {f}: {e}')
        continue
    data = [l for l in lines if len(l) > 6 and l[:5].isdigit() and l[5] == ' ']
    dirty = [l for l in data if len(l.split()) != 2]
    if dirty:
        dirty_total += len(dirty)
        print(f'DIRTY {f}: data={len(data)} dirty={len(dirty)}')
        for l in dirty[:3]:
            print(f'   e.g. {l[:120]!r}')
    else:
        n_ok += 1
print(f'scanned {len(files)} files; clean={n_ok}; dirty lines total = {dirty_total}')
