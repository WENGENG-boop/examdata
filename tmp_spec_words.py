"""Dump words with coordinates around a search phrase in a PDF (read-only)."""
import sys

import pymupdf

path = sys.argv[1]
needle = sys.argv[2]
pad = float(sys.argv[3]) if len(sys.argv) > 3 else 120.0

doc = pymupdf.open(path)
for pno in range(len(doc)):
    page = doc[pno]
    hits = page.search_for(needle)
    if not hits:
        continue
    print(f'page {pno} (0-based), hits: {hits}')
    y0 = min(h.y0 for h in hits) - pad
    y1 = max(h.y1 for h in hits) + pad
    for w in page.get_text('words'):
        wx0, wy0, wx1, wy1, text = w[0], w[1], w[2], w[3], w[4]
        if wy0 >= y0 and wy1 <= y1:
            print(f'{wx0:7.1f} {wy0:7.1f} {wx1:7.1f} {wy1:7.1f}  {text}')
    break
