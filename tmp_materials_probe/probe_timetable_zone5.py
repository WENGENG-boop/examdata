"""探测D：CIE Zone 5 时间表 PDF 下载 + 结构分析。"""

import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, r"C:/Users/weo/Desktop/api/examdata/src")
from examdata.core.config import Settings
from examdata.core.fetch import Fetcher

import fitz

BASE = "https://www.cambridgeinternational.org"
OUT = Path(r"C:/Users/weo/Desktop/api/tmp_materials_probe")
EV = OUT / "evidence"
DL = OUT / "downloads"
fetcher = Fetcher(Settings())

PDFS = {
    "zone5_june2026": "/Images/745760-june-2026-zone-5-timetable.pdf",
    "zone5_nov2026": "/Images/757650-november-2026-zone-5-timetable.pdf",
}
meta = {}
for key, path in PDFS.items():
    rr = fetcher.get(BASE + path, expect_binary=True, follow_redirects=False)
    print(f"== {key}: HTTP {rr.status} bytes {len(rr.content or b'')} err={rr.error}")
    if not rr.content:
        continue
    fp = DL / f"{key}.pdf"
    fp.write_bytes(rr.content)
    sha = hashlib.sha256(rr.content).hexdigest()
    doc = fitz.open(stream=rr.content, filetype="pdf")
    text = "\n".join(p.get_text() for p in doc)
    (EV / f"{key}.txt").write_text(text, encoding="utf-8")
    toc = doc.get_toc()
    meta[key] = {
        "url": BASE + path, "status": rr.status, "bytes": len(rr.content),
        "sha256": sha, "pages": len(doc), "toc_len": len(toc),
        "first_page": doc[0].get_text()[:1200],
    }
    print("   sha256", sha, "pages", len(doc), "toc", len(toc))
    print("   --- page1 ---")
    print(doc[0].get_text()[:900])
    if len(doc) > 1:
        print("   --- page2 ---")
        print(doc[1].get_text()[:900])
    # 结构探测：日期 / 场次 / 试卷代码模式
    pats = {
        "dates": re.findall(r"\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\b", text)[:8],
        "sessions": sorted(set(re.findall(r"\b(AM|PM)\b", text))),
        "papercodes": re.findall(r"\b\d{4}/\d{2}\b", text)[:15],
        "times": re.findall(r"\b\d{1,2}[.:]\d{2}\b", text)[:15],
    }
    print("   dates:", pats["dates"])
    print("   sessions:", pats["sessions"])
    print("   papercodes:", pats["papercodes"])
    print("   times:", pats["times"])

(EV / "zone5_downloads.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
print("saved evidence/zone5_downloads.json")
