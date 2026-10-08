"""Generate an r2 ans file from a pack: every qid OK, except explicit overrides.

usage: python tmp_mkans.py <pack_file> <ans_file> [qid:CODE ...]
"""
import re
import sys
from pathlib import Path

pack = Path(sys.argv[1])
ans = Path(sys.argv[2])
overrides = {}
for arg in sys.argv[3:]:
    qid, code = arg.split(':', 1)
    overrides[qid] = code

qids = []
for ln in pack.read_text(encoding='utf-8').splitlines():
    m = re.match(r'^\[(\d+)\]\s+(\d+)\s', ln)
    if m:
        qids.append(m.group(2))

assert len(qids) == len(set(qids)), f'duplicate qids in {pack}'

lines = []
for q in qids:
    lines.append(f"{q} {overrides.get(q, 'OK')}")

ans.write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(f"{pack.name}: {len(qids)} questions, {len(overrides)} overrides -> {ans.name}")
