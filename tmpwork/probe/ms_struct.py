import re
import pymupdf

doc = pymupdf.open("tmpwork/probe/wec11_rms.pdf")
W = doc[0].rect.width
print("MS page width", W, "pages", len(doc))
print("\n### MS: left-margin question tokens (x0 < 0.20*W = %.0f)" % (0.20*W))
for pno in range(len(doc)):
    page = doc[pno]
    toks = [(round(w[0]), round(w[1]), w[4]) for w in page.get_text("words")
            if w[0] < 0.20*W and w[1] < 0.93*page.rect.height
            and re.fullmatch(r"[1-9][0-9]?|\([a-z]\)|\([ivx]+\)", w[4])]
    if toks:
        print(f"  p{pno} drawings={len(page.get_drawings())}: {toks[:25]}")

print("\n### MS page 3 raw text head")
print(doc[3].get_text()[:800])
print("\n### MS: find 'Section B' page")
for pno in range(len(doc)):
    if "Section B" in doc[pno].get_text():
        print("Section B at page", pno)
        print(doc[pno].get_text()[:600])
        break
