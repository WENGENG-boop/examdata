"""Char-level dump of a region of a PDF page."""
import sys

import pymupdf

path = sys.argv[1]
page_no = int(sys.argv[2])
y0, y1, x0, x1 = (float(v) for v in sys.argv[3:7])

doc = pymupdf.open(path)
page = doc[page_no]
chars = []
for block in page.get_text('rawdict')['blocks']:
    for line in block.get('lines', []):
        for span in line['spans']:
            for ch in span['chars']:
                x, y = ch['origin']
                if y0 <= y <= y1 and x0 <= x <= x1:
                    chars.append((round(y, 2), round(x, 2), ch['c'], round(span['size'], 1)))
chars.sort()
# group into visual rows of 3pt
rows = []
for y, x, c, sz in chars:
    if rows and abs(rows[-1][0] - y) <= 3:
        rows[-1][1].append((x, c, sz))
    else:
        rows.append((y, [(x, c, sz)]))
for y, items in rows:
    items.sort()
    print(f'y={y:7.2f}: ' + ' '.join(f'{c}({x:.0f},{sz})' for x, c, sz in items))
