import json, re
from urllib.parse import quote
import httpx, pymupdf

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

doc = pymupdf.open("tmpwork/probe/wec11.pdf")
page = doc[1]
words = sorted(page.get_text("words"), key=lambda w: (round(w[1]/3), w[0]))
print("=== page1 words with x0<130 (left column), reading order ===")
for w in words:
    if w[0] < 130 and w[1] < 0.90*page.rect.height:
        print(f"  x0={w[0]:6.1f} y0={w[1]:6.1f} y1={w[3]:6.1f} {w[4]!r}")
print()
print("=== page1 raw text (first 1200 chars) ===")
print(page.get_text()[:1200])
