"""Verify one pack ans file against its pack file.

Mirrors tmp_selfjudge_ingest.parse_answers exactly (skip blank/# lines,
split() must give exactly 2 tokens, first token all digits), then checks
the qid set/order against the pack's [n] qid list and prints non-OK lines.

usage: python tmp_check_ans.py <pack_file> <ans_file>
"""
import re
import sys
from pathlib import Path

pack = Path(sys.argv[1])
ans = Path(sys.argv[2])

qids = []
for ln in pack.read_text(encoding='utf-8').splitlines():
    m = re.match(r'^\[(\d+)\]\s+(\d+)\s', ln)
    if m:
        qids.append(m.group(2))

errors = []
answers = []
for ln, raw in enumerate(ans.read_text(encoding='utf-8').splitlines(), 1):
    line = raw.strip()
    if not line or line.startswith('#'):
        continue
    parts = line.split()
    if len(parts) != 2 or not parts[0].isdigit():
        errors.append(f'{ans.name}:{ln}: bad line {raw!r}')
        continue
    answers.append((parts[0], parts[1]))

ans_qids = [a[0] for a in answers]
if len(set(ans_qids)) != len(ans_qids):
    seen, dupes = set(), []
    for q in ans_qids:
        if q in seen:
            dupes.append(q)
        seen.add(q)
    errors.append(f'duplicate qids: {sorted(set(dupes))}')
if ans_qids != qids:
    errors.append(f'qid list mismatch: pack={len(qids)} ans={len(ans_qids)}')
    for i, (a, b) in enumerate(zip(ans_qids, qids)):
        if a != b:
            errors.append(f'first mismatch at verdict #{i + 1}: ans={a} pack={b}')
            break
    missing = set(qids) - set(ans_qids)
    extra = set(ans_qids) - set(qids)
    if missing:
        errors.append(f'missing from ans: {sorted(missing)}')
    if extra:
        errors.append(f'extra in ans: {sorted(extra)}')

non_ok = [(q, c) for q, c in answers if c != 'OK']
print(f'{ans.name}: {len(answers)} verdicts, {len(non_ok)} non-OK, {len(errors)} errors')
for e in errors:
    print('  ERROR', e)
for q, c in non_ok:
    print(f'  CHANGE {q} -> {c}')
sys.exit(1 if errors else 0)
