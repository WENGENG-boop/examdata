"""Write WST03-p01.ans.txt (r2 math) from the confirmed override table.

Source: agent-834's finalized review (15 overrides + 134 OK), recorded in
its output.log (tasks/agent-1x5n7cor/output.log); this script materializes
the ans file mechanically, in pack order.
"""
import re
from pathlib import Path

root = Path('tmp_selfjudge/r2/ial18-mathematics')
pack_path = root / 'WST03-p01.txt'
pack = pack_path.read_text(encoding='utf-8')

qids = re.findall(r'^\[(\d+)\]\s+(\d+)', pack, re.M)
assert len(qids) == 149, f'expected 149 pack rows, got {len(qids)}'

overrides = {
    '37168': 'WST03-3.8', '37170': 'WST03-3.8', '37172': 'WST03-3.8',
    '39360': 'WST03-3.8', '39361': 'WST03-3.8', '35945': 'WST03-3.8',
    '35946': 'WST03-3.8', '38566': 'WST03-3.8',
    '35923': 'WST03-3.8', '35927': 'WST03-3.8',
    '39091': 'WST03-4.1', '38268': 'WST03-4.1',
    '39109': 'WST03-4.1', '40858': 'WST03-4.1',
    '37818': 'WST03-2.2',
}
assert len(overrides) == 15

pack_qids = [q for _, q in qids]
missing = set(overrides) - set(pack_qids)
assert not missing, f'override qids not in pack: {missing}'

header = [
    '# WST03-p01 r2 selfjudge answers (149 questions)',
    '# 本轮共改写 15 题（其余维持现标签）：',
    '#   37168/37170/37172/39360/39361/35945/35946/38566 -> 3.8（两样本大样本 s² 检验，σ 未知）',
    '#   35923/35927 -> 3.8（单样本 n=100，s² 估计 σ²；同型先例 58031(a)=3.8）',
    '#   39091/38268/39109/40858 -> 4.1（"show sample mean" 属检验流程；先例 59755(a)/58035(a)/37177(b)=4.1）',
    '#   37818 -> 2.2（容器三子题全 2.2）',
]

lines = [f'{q} {overrides[q]}' if q in overrides else f'{q} OK' for q in pack_qids]

ref = (root / 'WST01-p01.ans.txt').read_bytes()
nl = '\r\n' if b'\r\n' in ref else '\n'
data = ('\n'.join(header + lines) + '\n').replace('\n', nl).encode('utf-8')
out = root / 'WST03-p01.ans.txt'
out.write_bytes(data)
print(f'wrote {out}: {len(lines)} verdicts, {len(overrides)} overrides, newline={"CRLF" if nl == chr(13) + chr(10) else "LF"}')

for n, q in qids:
    if q in overrides:
        m = re.search(rf'^\[{n}\]\s+{q}\s.*?cur=(\S+)', pack, re.M)
        print(f'  {q}: cur={m.group(1) if m else "?"} -> {overrides[q]}')
