"""探测D-2：历届 Zone 5 时间表存档路径 —— portfolio 页 + Wayback CDX。"""

import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, r"C:/Users/weo/Desktop/api/examdata/src")
from examdata.core.config import Settings
from examdata.core.fetch import Fetcher

BASE = "https://www.cambridgeinternational.org"
OUT = Path(r"C:/Users/weo/Desktop/api/tmp_materials_probe")
EV = OUT / "evidence"
fetcher = Fetcher(Settings())

# 1) portfolio-of-evidence/june-2026
url = f"{BASE}/exam-administration/cambridge-exams-officers-guide/portfolio-of-evidence/june-2026"
r = fetcher.get_text(url)
print(f"== portfolio june-2026: HTTP {r.status} bytes {len(r.text or '')} robots_blocked={r.robots_blocked} err={r.error}")
if r.text:
    (EV / "guide_portfolio_june2026.html").write_text(r.text, encoding="utf-8")
    hrefs = re.findall(r'href="([^"]+)"', r.text)
    for h in dict.fromkeys(hrefs):
        if "timetable" in h.lower() or "Images" in h:
            print("   ", h)

# 2) Wayback CDX for exam-timetables page
cdx_url = ("http://web.archive.org/cdx/search/cdx?url="
           + quote("cambridgeinternational.org/exam-administration/cambridge-exams-officers-guide/phase-1-preparation/timetabling-exams/exam-timetables", safe="")
           + "&matchType=prefix&output=json&fl=timestamp,original,statuscode&collapse=digest&limit=200")
r2 = fetcher.get_text(cdx_url)
print(f"\n== CDX page snapshots: HTTP {r2.status} robots_blocked={r2.robots_blocked} err={r2.error}")
if r2.text:
    (EV / "cdx_exam_timetables.json").write_text(r2.text, encoding="utf-8")
    try:
        rows = json.loads(r2.text)
        print("   rows:", len(rows))
        for row in rows[:60]:
            print("   ", row)
    except Exception as e:
        print("   parse fail:", e, r2.text[:300])
else:
    print("   error:", r2.error)

# 3) Wayback availability API for a known historical zone5 PDF naming pattern? 先看 CDX 能否查图片路径前缀
cdx2 = ("http://web.archive.org/cdx/search/cdx?url="
        + quote("cambridgeinternational.org/Images/", safe="")
        + "&matchType=prefix&output=json&fl=timestamp,original&filter=original:.*zone-5.*&collapse=urlkey&limit=300")
r3 = fetcher.get_text(cdx2)
print(f"\n== CDX zone-5 images: HTTP {r3.status} robots_blocked={r3.robots_blocked} err={r3.error}")
if r3.text:
    (EV / "cdx_zone5_images.json").write_text(r3.text, encoding="utf-8")
    try:
        rows = json.loads(r3.text)
        print("   rows:", len(rows))
        for row in rows[:100]:
            print("   ", row)
    except Exception as e:
        print("   parse fail:", e, r3.text[:500])
else:
    print("   error:", r3.error)
