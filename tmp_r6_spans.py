"""Reconstruct PDF spans with coordinates for a given page (r6 WMA13 Q3 check)."""
import sys

import pymupdf

path = sys.argv[1]
page_no = int(sys.argv[2])
needle = sys.argv[3] if len(sys.argv) > 3 else None

doc = pymupdf.open(path)
page = doc[page_no]
d = page.get_text('dict')
spans = []
for block in d['blocks']:
    for line in block.get('lines', []):
        for span in line['spans']:
            t = span['text']
            if t.strip():
                spans.append((round(span['bbox'][1], 1), round(span['bbox'][0], 1), t, span['size']))
spans.sort()
for y, x, t, size in spans:
    if needle is None or needle in t or True:
        print(f'y={y:7.1f} x={x:6.1f} sz={size:4.1f} | {t!r}')
