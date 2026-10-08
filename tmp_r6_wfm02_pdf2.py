"""Read-only: extract + de-shift (+29 ASCII) text from a local PDF."""
import sys
import pymupdf

SHIFT = 29

def decode(s):
    out = []
    for ch in s:
        o = ord(ch)
        n = o + SHIFT
        if n <= 0x7E and 0x20 <= o:
            out.append(chr(n))
        else:
            out.append(ch)
    return ''.join(out)

path = sys.argv[1]
doc = pymupdf.open(path)
for i, page in enumerate(doc):
    print(f'---------- page {i+1} ----------')
    print(decode(page.get_text()))
