import re, sys
import httpx, pymupdf

URL = ("https://qualifications.pearson.com/content/dam/pdf/International-Advanced-Level/"
       "Economics/2018/Exam-materials/wec11-01-que-20240510.pdf")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
out = "tmpwork/probe/wec11.pdf"
with httpx.Client(follow_redirects=False, timeout=60, headers={"User-Agent": UA}) as c:
    r = c.get(URL)
    print("status", r.status_code, "len", len(r.content), "ctype", r.headers.get("content-type"))
    assert r.content[:4] == b"%PDF", r.content[:40]
    open(out, "wb").write(r.content)

doc = pymupdf.open(out)
print("pages", len(doc))
for pno in range(min(3, len(doc))):
    page = doc[pno]
    t = page.get_text()
    alnum = sum(1 for ch in t if ch.isalnum())
    print(f"--- page {pno} rect={page.rect} alnum_ratio={alnum/max(len(t),1):.3f} drawings={len(page.get_drawings())}")
    words = page.get_text("words")
    print("  first 25 words:", [(round(w[1]),round(w[3]),w[4]) for w in words[:25]])
    # tokens that look like question numbers
    cand = [w for w in words if re.fullmatch(r"[1-9][0-9]?|[Qq][1-9][0-9]?|\([a-z]\)|\([ivx]+\)|[a-z]i?|\([a-z]\)|[1-9][0-9]?[a-z]i?", w[4])]
    print("  numbered candidates (x0,y0,w):", [(round(w[0]),round(w[1]),w[4]) for w in cand[:40]])
    print("  heights:", round(page.rect.height))
