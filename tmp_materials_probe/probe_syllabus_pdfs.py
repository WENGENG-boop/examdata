"""下载各科 syllabus PDF，用 pymupdf 搜索 MF19/周期表/数据手册等关键词。"""

import re
import sys
from pathlib import Path

sys.path.insert(0, r"C:/Users/weo/Desktop/api/examdata/src")
from examdata.core.config import Settings
from examdata.core.fetch import Fetcher

import fitz  # pymupdf

BASE = "https://www.cambridgeinternational.org"
OUT = Path(r"C:/Users/weo/Desktop/api/tmp_materials_probe")
EV = OUT / "evidence"
fetcher = Fetcher(Settings())

# 1) notation list 链接上下文
html = (EV / "official_9709_home.html").read_text(encoding="utf-8", errors="replace")
i = html.find("420009-mathematics-notation-list")
print("context:", re.sub(r"\s+", " ", html[max(0, i - 700):i + 300]))

# 2) 各科 home 页找 syllabus 链接（0620 页未取，先取）
r = fetcher.get_text(f"{BASE}/programmes-and-qualifications/cambridge-igcse-chemistry-0620/")
(EV / "official_0620_home.html").write_text(r.text or "", encoding="utf-8")

# 3) 下载 syllabus PDF
PDFS = {
    "9709_2023-2025_syllabus": "/Images/597421-2023-2025-syllabus.pdf",
    "9709_2026-2027_syllabus": "/Images/697427-2026-2027-syllabus.pdf",
    "9701_2025-2027_syllabus": "/Images/664563-2025-2027-syllabus.pdf",
    "9709_notation_list": "/Images/420009-mathematics-notation-list-.pdf",
}
for key, path in PDFS.items():
    rr = fetcher.get(BASE + path, expect_binary=True, follow_redirects=False)
    print(f"== {key}: HTTP {rr.status} bytes {len(rr.content or b'')} err={rr.error}")
    if rr.content:
        fp = OUT / "downloads" / f"{key}.pdf"
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_bytes(rr.content)
        doc = fitz.open(stream=rr.content, filetype="pdf")
        text = "\n".join(p.get_text() for p in doc)
        (EV / f"{key}.txt").write_text(text, encoding="utf-8")
        for kw in ["MF19", "MF9", "MF10", "List of formulae", "formulae", "Periodic Table",
                   "Data Booklet", "data booklet", "Periodic", "insert", "Insert"]:
            cnt = text.count(kw)
            if cnt:
                idx = text.find(kw)
                snippet = re.sub(r"\s+", " ", text[max(0, idx - 120):idx + 200])
                print(f"   {kw}: {cnt} | {snippet[:280]}")
        print("   pages:", len(doc))
