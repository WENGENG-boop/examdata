"""探测B：官网各科页面里的「公式表/周期表/数据手册」类链接。"""

import re
import sys
from pathlib import Path

sys.path.insert(0, r"C:/Users/weo/Desktop/api/examdata/src")
from examdata.core.config import Settings
from examdata.core.fetch import Fetcher

BASE = "https://www.cambridgeinternational.org"
OUT = Path(r"C:/Users/weo/Desktop/api/tmp_materials_probe/evidence")
fetcher = Fetcher(Settings())

PAGES = {
    "9709_home": f"{BASE}/programmes-and-qualifications/cambridge-international-as-and-a-level-mathematics-9709/",
    "9709_past": f"{BASE}/programmes-and-qualifications/cambridge-international-as-and-a-level-mathematics-9709/past-papers",
    "9701_home": f"{BASE}/programmes-and-qualifications/cambridge-international-as-and-a-level-chemistry-9701/",
    "0620_past": f"{BASE}/programmes-and-qualifications/cambridge-igcse-chemistry-0620/past-papers",
    "9702_home": f"{BASE}/programmes-and-qualifications/cambridge-international-as-and-a-level-physics-9702/",
}

KEY = re.compile(r"formula|formulae|mf19|periodic|data\s*booklet|booklet|insert|support|material|handbook|specimen", re.I)
anchor_re = re.compile(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)

for key, url in PAGES.items():
    r = fetcher.get_text(url)
    (OUT / f"official_{key}.html").write_text(r.text or "", encoding="utf-8")
    print(f"== {key} HTTP {r.status} bytes {len(r.text or '')} robots_blocked={r.robots_blocked}")
    if not r.text:
        print("   error:", r.error)
        continue
    seen = set()
    for href, text in anchor_re.findall(r.text):
        clean = re.sub(r"<[^>]+>", " ", text)
        clean = re.sub(r"\s+", " ", clean).strip()
        if KEY.search(href) or KEY.search(clean):
            item = (href, clean[:110])
            if item in seen:
                continue
            seen.add(item)
            print("   ", href, "|", clean[:110])
