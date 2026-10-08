import re
import pymupdf

doc = pymupdf.open("tmpwork/probe/wec11.pdf")
W = doc[0].rect.width
print("page width", W)
print("\n### QP: left-margin tokens (x0 < 0.15*W = %.0f) per page" % (0.15*W))
for pno in range(len(doc)):
    page = doc[pno]
    toks = [(round(w[0]), round(w[1]), w[4]) for w in page.get_text("words")
            if w[0] < 0.15*W and w[1] < 0.93*page.rect.height
            and re.fullmatch(r"[1-9][0-9]?|\([a-z]\)|\([ivx]+\)", w[4])]
    if toks:
        print(f"  p{pno}: {toks}")

print("\n### QP: page 8 & 9 raw text head")
for pno in (8, 9):
    print(f"--- p{pno} ---")
    print(doc[pno].get_text()[:500])
