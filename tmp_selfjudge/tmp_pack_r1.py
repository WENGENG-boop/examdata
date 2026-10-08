"""Extract r1 decisions for a pack's qids.

usage: python tmp_pack_r1.py <pack_file> <decisions_dir> <out_file>
"""
import json
import re
import sys
from pathlib import Path

pack = Path(sys.argv[1])
dec_dir = Path(sys.argv[2])
out = Path(sys.argv[3])

qids = []
for ln in pack.read_text(encoding='utf-8').splitlines():
    m = re.match(r'^\[(\d+)\]\s+(\d+)\s', ln)
    if m:
        qids.append(int(m.group(2)))

recs = {}
for f in sorted(dec_dir.glob('batch-*.jsonl')):
    for ln in f.read_text(encoding='utf-8').splitlines():
        if not ln.strip():
            continue
        d = json.loads(ln)
        recs[d['question_id']] = d
ap = dec_dir / 'applied.jsonl'
if ap.exists():
    for ln in ap.read_text(encoding='utf-8').splitlines():
        if not ln.strip():
            continue
        d = json.loads(ln)
        if d['question_id'] not in recs:
            recs[d['question_id']] = d

lines = []
for q in qids:
    d = recs.get(q)
    if d is None:
        lines.append(f"{q} MISSING")
    else:
        code = d.get('code') or '-'
        lines.append(f"{q} {d['decision']} {code} | {d.get('reason', '')}")

out.write_text('\n'.join(lines) + '\n', encoding='utf-8')
missing = sum(1 for l in lines if l.endswith('MISSING'))
print(f"{pack.name}: {len(qids)} qids, {missing} missing -> {out.name}")
