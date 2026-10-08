import json
from urllib.parse import quote
import httpx

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
ORIGIN = "https://qualifications.pearson.com"
SERVLET = ORIGIN + "/services/pearson/algolia/GET.servlet"

def q(fq, hits=1000, label=""):
    url = f"{SERVLET}?fq={quote(fq)}&hitsPerPage={hits}"
    with httpx.Client(follow_redirects=True, timeout=40, headers={"User-Agent": UA}) as c:
        r = c.get(url)
    if r.status_code != 200:
        print(f"[{label}] HTTP {r.status_code}")
        return []
    try:
        recs = (r.json().get("searchResults") or {}).get("algoliaRecords") or []
    except Exception as e:
        print(f"[{label}] JSON err {e}: {r.text[:200]}")
        return []
    print(f"[{label}] {len(recs)} recs")
    return recs

# 1. OR 语法是否被 servlet 支持？
fq_or = ('(category:"Pearson-UK:Qualification-Subject/Economics" '
         'OR category:"Pearson-UK:Specification-Code/ial18-economics") AND '
         'category:"Pearson-UK:Exam-Series/June-2024"')
r_or = q(fq_or, label="OR-syntax")
fq_and = ('category:"Pearson-UK:Qualification-Subject/Economics" AND '
          'category:"Pearson-UK:Exam-Series/June-2024"')
r_and = q(fq_and, label="AND-subject")
fq_spec = ('category:"Pearson-UK:Specification-Code/ial18-economics" AND '
           'category:"Pearson-UK:Exam-Series/June-2024"')
r_spec = q(fq_spec, label="AND-speccode")

for rec in (r_and or r_or)[:60]:
    cats = rec.get("category") or []
    dt = [c for c in cats if "Document-Type" in c]
    print("   ", rec.get("extension"), "|", (rec.get("title") or "")[:70], "|", (dt[0].split("/")[-1] if dt else "?"), "|", (rec.get("url") or "")[:95])
