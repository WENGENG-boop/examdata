"""Pre-ingest sanity check for ial-maths self-judge answer files.

Cross-checks the three *.ans.txt files against the batch queue:
coverage, duplicates, unit prefix match, per-unit code ranges, counts.
"""
import glob
import json
import re
import sys
from pathlib import Path

SLUG = 'ial-maths'
BATCH_GLOB = f'tmp_jev_untagged_batches/{SLUG}/batches/batch-*.jsonl'
ANS_DIR = Path(f'tmp_selfjudge/unt/{SLUG}')

EXPECTED_COUNTS = {'WDM01': 28, 'WMA01': 75, 'WMA02': 69}
MAX_POINT = {'WDM01': 6, 'WMA01': 7, 'WMA02': 9}

qid_unit = {}
dup_batch = []
n_rows = 0
for f in sorted(glob.glob(BATCH_GLOB)):
    for line in open(f, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        n_rows += 1
        qid = r['question_id']
        if qid in qid_unit:
            dup_batch.append(qid)
        qid_unit[qid] = r['unit_code']

print(f'batch rows={n_rows} unique_qids={len(qid_unit)} batch_dupes={len(dup_batch)}')

errors = []
ans = {}
for f in sorted(ANS_DIR.glob('*.ans.txt')):
    for ln, raw in enumerate(f.read_text(encoding='utf-8').splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.split()
        if len(parts) != 2 or not parts[0].isdigit():
            errors.append(f'{f.name}:{ln}: bad answer line: {line!r}')
            continue
        qid = int(parts[0])
        code = parts[1]
        if qid in ans:
            errors.append(f'{f.name}:{ln}: duplicate qid {qid} (first in {ans[qid][0]})')
            continue
        ans[qid] = (f.name, code)

print(f'answers parsed={len(ans)}')

missing = sorted(set(qid_unit) - set(ans))
extra = sorted(set(ans) - set(qid_unit))
if missing:
    errors.append(f'missing answers for {len(missing)} qids: {missing[:20]}')
if extra:
    errors.append(f'answers for {len(extra)} qids not in queue: {extra[:20]}')

counts = {}
for qid in sorted(set(qid_unit) & set(ans)):
    unit = qid_unit[qid]
    fname, code = ans[qid]
    counts[unit] = counts.get(unit, 0) + 1
    m = re.fullmatch(r'([A-Z]+\d+)-(\d+)', code)
    if not m:
        errors.append(f'{fname}: qid {qid}: malformed code {code!r}')
        continue
    cunit, pt = m.group(1), int(m.group(2))
    if cunit != unit:
        errors.append(f'{fname}: qid {qid}: code unit {cunit} != batch unit {unit}')
    if unit in MAX_POINT and not (1 <= pt <= MAX_POINT[unit]):
        errors.append(f'{fname}: qid {qid}: point {pt} out of range 1..{MAX_POINT[unit]}')

print('counts:', {u: counts.get(u, 0) for u in EXPECTED_COUNTS})
for u, n in EXPECTED_COUNTS.items():
    if counts.get(u, 0) != n:
        errors.append(f'count mismatch {u}: got {counts.get(u, 0)}, expected {n}')

if errors:
    print(f'FAIL: {len(errors)} error(s)')
    for e in errors[:40]:
        print(' -', e)
    sys.exit(1)
print('OK: all checks passed')
