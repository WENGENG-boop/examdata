"""0478 核验辅助：打印提案结构 + MS/QP 文字层中的题号标签。"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, 'C:/Users/weo/Desktop/api/cie-location-batch/tools')
import paperlib as P  # noqa: E402
import pymupdf  # noqa: E402

KEY = '0478/2026/Jun/11'
prop = Path('C:/Users/weo/Desktop/api/cie-location-batch/work/proposals/0478/2026-Jun-11.json')
d = json.loads(prop.read_text(encoding='utf-8'))
print('PROPOSAL BYTES', prop.stat().st_size)


def walk(o, pre='', depth=0):
    if depth > 2:
        return
    if isinstance(o, dict):
        for k, v in o.items():
            if isinstance(v, (dict, list)):
                print(f'{pre}{k}: {type(v).__name__}[{len(v)}]')
                walk(v, pre + '  ', depth + 1)
            else:
                print(f'{pre}{k} = {str(v)[:150]}')
    elif isinstance(o, list) and o:
        print(f'{pre}[0] of {len(o)}:')
        walk(o[0], pre + '  ', depth + 1)


walk(d)

tmp = P.paper_tmp(KEY)
pdfs = sorted(tmp.glob('*.pdf'))
print('PDFS', [p.name for p in pdfs])
ms = [p for p in pdfs if '_ms_' in p.name][0]
qp = [p for p in pdfs if '_qp_' in p.name][0]

LAB = re.compile(r'^(?:\(?[a-z]\)?|\(?[ivx]+\)?|[1-9]\d{0,2}|[1-9]\d{0,2}\([a-z]\))$')

with pymupdf.open(ms) as doc:
    for i in range(doc.page_count):
        page = doc[i]
        words = page.get_text('words')
        hits = [w for w in words if LAB.match(w[4]) and (w[2] - w[0]) < 60]
        print(f'--- MS p{i+1} rot={page.rotation} rect={page.rect} words={len(words)} hits={len(hits)}')
        for w in hits[:70]:
            print(f'   {w[4]!r} x0={w[0]:.1f} y0={w[1]:.1f} x1={w[2]:.1f} y1={w[3]:.1f}')
        if i < 4:
            print('   RAW:', ' | '.join(f'{w[4]}' for w in words[:60]))

with pymupdf.open(qp) as doc:
    for i in range(doc.page_count):
        page = doc[i]
        words = page.get_text('words')
        hits = [w for w in words if LAB.match(w[4]) and (w[2] - w[0]) < 60]
        print(f'=== QP p{i+1} rot={page.rotation} words={len(words)} hits={len(hits)}')
        for w in hits[:40]:
            print(f'   {w[4]!r} x0={w[0]:.1f} y0={w[1]:.1f} x1={w[2]:.1f} y1={w[3]:.1f}')
