# -*- coding: utf-8 -*-
"""Per-unit coverage: batch rows vs ans-file directives for an r2 subject."""
import argparse
import collections
import glob
import json
import os
import re

ap = argparse.ArgumentParser()
ap.add_argument('--slug', required=True)
ap.add_argument('--batch-root', default='tmp_jev_full_batches_r2')
ap.add_argument('--set', default='r2')
args = ap.parse_args()

rows = collections.Counter()
for f in glob.glob(f'{args.batch_root}/{args.slug}/batches/batch-*.jsonl'):
    for line in open(f, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        rows[rec.get('unit_code')] += 1

dirs = collections.Counter()
files_per_unit = collections.defaultdict(list)
for f in sorted(glob.glob(f'tmp_selfjudge/{args.set}/{args.slug}/*.ans.txt')):
    m = re.match(r'([A-Z]+\d+)-p(\d+)\.ans\.txt$', os.path.basename(f))
    if not m:
        continue
    unit = m.group(1)
    n = 0
    for line in open(f, encoding='utf-8'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        n += 1
    dirs[unit] += n
    files_per_unit[unit].append((os.path.basename(f), n))

total_rows = total_dirs = 0
for u in sorted(set(rows) | set(dirs)):
    r, d = rows.get(u, 0), dirs.get(u, 0)
    total_rows += r
    total_dirs += d
    flag = 'OK' if r == d else f'GAP={r - d}'
    print(f'{u}: rows={r} directives={d} {flag}')
print(f'TOTAL rows={total_rows} directives={total_dirs} gap={total_rows - total_dirs}')
print('--- files ---')
for u in sorted(files_per_unit):
    for name, n in files_per_unit[u]:
        print(f'  {name}: {n}')
