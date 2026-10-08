"""Generate WME01-p01.ans.txt from pack order with overrides + comments.
Format: data lines are exactly `qid TOKEN`; comments are `# ...` lines (skipped by ingest parser).
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # tmp_selfjudge/
pack = ROOT / 'r2' / 'ial18-mathematics-extra' / 'WME01-p01.txt'
out = ROOT / 'r2' / 'ial18-mathematics-extra' / 'WME01-p01.ans.txt'

qids = []
for line in pack.read_text(encoding='utf-8').splitlines():
    m = re.match(r'^\[(\d+)\] (\d+) ', line)
    if m:
        qids.append(int(m.group(2)))
assert len(qids) == 138, len(qids)
assert len(set(qids)) == 138

overrides = {
    56799: 'WME01-5.2',
    58539: 'WME01-5.1',
}
comments = {
    56799: 'CHANGE 4.4 -> 5.2: broom pushed at constant speed, MS solves equilibrium with F=muR. Same type as 58530/58988 (5.2) and DB 35840/40004 (5.2); r1 4.4 (conf 0.64) is the family outlier.',
    58539: 'CHANGE 5.2 -> 5.1: bearing of F2 given resultant; vector addition of forces, no equilibrium. Siblings 58537 whole and 58538 (i) are both 5.1; MS uses cosine rule/resolving. r1 5.2 (conf 0.44) inconsistent.',
    58530: 'dragged at constant speed, find strap tension: equilibrium with F=muR => 5.2 (cf 58988, 35840, 40004).',
    58988: 'sledge pulled at constant speed, find tension: equilibrium with F=muR => 5.2 (cf 58530).',
    58801: 'particle remains at rest under applied force: limiting static friction condition => 5.3.',
    57550: 'vector kinematics in i,j notation => 2.2.',
    60535: 'mu from equations of motion (dynamics, connected particles) => 4.4 (cf 60086).',
    57833: 'whole question mixes sliding (F=ma with mu) and limiting equilibrium; friction theme => 4.4.',
    57834: 'target is speed: suvat after F=ma with mu => 3.1 (cf 40543, 35848).',
    60086: 'mu from dynamics F=ma => 4.4 (cf 60535).',
    57837: 'connected particles, show acceleration 1.4 => 4.2.',
    58823: 'target is distance: suvat => 3.1 (cf 38180, 40543).',
    60678: 'force on pulley by string (sub-part) => 5.1 (cf 37062c, 39259, 41261, 35558b).',
    57943: 'whole: held at rest on rough plane, on point of moving up, find mu; then slides => 5.3 (cf 57557).',
    57944: 'normal reaction in limiting equilibrium => 5.2 (cf 37221).',
    57945: 'mu in limiting equilibrium => 5.3 (cf 37222, 37223).',
    60536: 'whole: force as resultant of two forces => 5.1 (cf 56809, 58537).',
    60538: 'find forces in terms of i and j => 2.2 (10 of 11 such WME01 rows are 2.2).',
    56804: 'use of rod model (beam stays straight) => 1.1 modelling assumption.',
    60551: 'given s, t, u: pure suvat => 3.1.',
    58806: 'acceleration from F=ma with friction (R=6gcos30) => 4.4.',
    56823: 'use of inextensible string (equal accelerations) => 4.2.',
    58552: 'use of inextensible string (equal accelerations) => 4.2.',
    60526: 'magnitude of velocity vector => 2.1 (cf 58999).',
    58999: 'distance between position vectors => 2.1.',
}

header = [
    '# SELFJUDGE r2 WME01 part 1/1 (138 rows)',
    '# r2 review of round-1 changed labels. Each row checked against question text,',
    '# mark scheme, sibling parts and DB precedents. 136 rows accepted as-is;',
    '# 2 rows re-tagged: 56799 -> WME01-5.2, 58539 -> WME01-5.1.',
    '# Notes on non-obvious rows are inline below.',
    '#' + '-' * 78,
]

lines = list(header)
for q in qids:
    if q in comments:
        lines.append(f'# {q}: {comments[q]}')
    lines.append(f'{q} {overrides.get(q, "OK")}')

text = '\n'.join(lines) + '\n'
assert '?' not in text
out.write_text(text, encoding='utf-8')
n_data = sum(1 for l in lines if not l.startswith('#') and l.strip())
print(f'wrote {out.name}: {n_data} data lines, {len(qids)} qids')
