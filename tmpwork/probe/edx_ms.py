import json
from urllib.parse import quote
import httpx, pymupdf

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
ORIGIN = "https://qualifications.pearson.com"
SERVLET = ORIGIN + "/services/pearson/algolia/GET.servlet"
fq = ('category:"Pearson-UK:Qualification-Family/International-Advanced-Level" AND '
      'category:"Pearson-UK:Qualification-Subject/Economics" AND '
      'category:"Pearson-UK:Exam-Series/June-2024"')
with httpx.Client(timeout=40, headers={"User-Agent": UA}) as c:
    r = c.get(f"{SERVLET}?fq={quote(fq)}&hitsPerPage=1000")
recs = (r.json().get("searchResults") or {}).get("algoliaRecords") or []
print("recs:", len(recs))
for rec in recs:
    dt = [c for c in (rec.get("category") or []) if "Document-Type" in c]
    print(f"  {dt[0].split('/')[-1]:26} {rec.get('url')}")

ms = [r_ for r_ in recs if any("Mark-scheme" in c for c in (r_.get("category") or []))
      and "WEC11" in (r_.get("title") or "")]
if not ms:
    print("no WEC11 ms found"); raise SystemExit
url = ORIGIN + ms[0]["url"]
print("\nMS url:", url)
with httpx.Client(follow_redirects=False, timeout=60, headers={"User-Agent": UA}) as c:
    rr = c.get(url)
print("status", rr.status_code, "len", len(rr.content), rr.content[:4])
open("tmpwork/probe/wec11_rms.pdf","wb").write(rr.content)

doc = pymupdf.open("tmpwork/probe/wec11_rms.pdf")
print("pages", len(doc))
for pno in range(min(4, len(doc))):
    page = doc[pno]
    t = page.get_text()
    alnum = sum(1 for ch in t if ch.isalnum())
    print(f"--- ms page {pno} alnum={alnum/max(len(t),1):.3f} drawings={len(page.get_drawings())}")
    print("   ", repr(t[:300]))
