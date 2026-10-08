"""离线预检：把 0472 草稿索引的每个 qp 区域与 QP 文字层转储做交叉比对。
不是视觉核验的替代，只用于提前发现明显错位/越界/混入下一题的区域。
"""
import json, re, sys
from pathlib import Path

BR = Path('C:/Users/weo/Desktop/api/cie-location-batch')

def load_dump(path):
    pages = {}
    cur = None
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        m = re.match(r'^--- page (\d+)', line)
        if m:
            cur = int(m.group(1))
            pages[cur] = []
            continue
        m = re.match(r'^  \[([\d., ]+)\] (.*)$', line)
        if m and cur:
            bb = [float(v) for v in m.group(1).split(',')]
            pages[cur].append((bb, m.group(2)))
    return pages

def intersect(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])

qp = load_dump(BR / 'work/logs/0472-qp-text-dump.txt')
idx = json.loads((BR / 'indexes/0472/2024-Jun-11/cie-index.json').read_text(encoding='utf-8'))

for q in idx['questions']:
    for reg in q.get('qp', []):
        pg = reg['page']; bb = reg['bbox']
        hits = [(lb, s) for lb, s in qp.get(pg, []) if intersect(lb, bb)]
        head = ' | '.join(s[:60] for _, s in hits[:6])
        n = len(hits)
        flag = ''
        nums = [s for _, s in hits if re.match(r'^\d+(\.\d+)?$', s.strip())]
        if q['question'] not in [x.strip() for x in nums]:
            flag = '  <<< 区域里未见题号 ' + q['question']
        print(f"Q{q['question']:>4} p{pg} {[round(v,1) for v in bb]} lines={n}{flag}")
        print(f"     {head}")
