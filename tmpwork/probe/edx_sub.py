import re
import pymupdf

doc = pymupdf.open("tmpwork/probe/wec11.pdf")
print("=== tokens matching sub-question markers anywhere ===")
for pno in range(len(doc)):
    page = doc[pno]
    hits = []
    for w in page.get_text("words"):
        x0,y0,x1,y1,t = w[0],w[1],w[2],w[3],w[4]
        if re.fullmatch(r"\([a-z]\)|\([ivx]+\)|[a-z]i", t):
            hits.append((round(x0),round(y0),t))
    if hits:
        print(f"page {pno}: {hits[:30]}")

print()
print("=== page with '(a)' style: raw text sample ===")
for pno in range(len(doc)):
    t = doc[pno].get_text()
    if "(a)" in t or "(Total" in t:
        print(f"--- page {pno} ---")
        print(t[:900])
        break
