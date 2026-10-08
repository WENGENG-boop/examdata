"""通过帮助中心 Zendesk 公共 API 拉取与「考试发放资料」相关的官方问答。"""

import io
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, r"C:/Users/weo/Desktop/api/examdata/src")
from examdata.core.config import Settings
from examdata.core.fetch import Fetcher

OUT = Path(r"C:/Users/weo/Desktop/api/tmp_materials_probe/evidence")
fetcher = Fetcher(Settings())
BASE = "https://help.cambridgeinternational.org/api/v2/help_center"

# 1) 栏目总览
r = fetcher.get_text(f"{BASE}/en-gb/sections.json?per_page=100")
sec = json.loads(r.text or "{}")
print("sections:", sec.get("count"))
for s in sec.get("sections", []):
    print(" ", s.get("id"), s.get("name"), "articles:", s.get("articles_count") if "articles_count" in s else "?")

report = io.open(OUT / "help_center_materials.md", "w", encoding="utf-8")
QUERIES = [
    "formula sheet", "list of formulae", "periodic table", "data booklet",
    "provided in the exam", "materials in the examination", "equation sheet",
    "insert in the question paper", "statistical tables", "additional materials",
]
seen_titles = set()
for q in QUERIES:
    url = f"{BASE}/articles/search.json?query={q.replace(' ', '%20')}&per_page=20"
    rr = fetcher.get_text(url)
    if not rr.text:
        continue
    data = json.loads(rr.text)
    report.write(f"\n######## QUERY: {q} (count={data.get('count')})\n")
    for a in data.get("results", []):
        title = a.get("title", "")
        key = title.lower()
        if key in seen_titles:
            continue
        seen_titles.add(key)
        art_id = a.get("id")
        body = ""
        ar = fetcher.get_text(f"{BASE}/en-gb/articles/{art_id}.json")
        if ar.text:
            try:
                d = json.loads(ar.text)
                body = re.sub(r"<[^>]+>", " ", d.get("article", {}).get("body") or "")
                body = re.sub(r"\s+", " ", body).strip()
            except Exception as exc:
                body = f"[parse error {exc}]"
        report.write(f"\n### {title}\nid={art_id} url={a.get('html_url')}\n{body[:1500]}\n")
report.close()
print("report written")
