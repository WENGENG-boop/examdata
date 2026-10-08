"""Read-only: extract text from a local PDF (artifacts store)."""
import sys
import pymupdf

path = sys.argv[1]
doc = pymupdf.open(path)
for i, page in enumerate(doc):
    print(f'---------- page {i+1} ----------')
    print(page.get_text())
