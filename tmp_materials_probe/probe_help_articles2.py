"""抓取 4 篇关键帮助文章正文 + 搜索 June/November 附加材料清单链接（Zendesk 公共 API）。

输出：evidence/help_center_articles_content.json
"""

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

ARTICLE_IDS = {
    "which_additional_materials": 115004393925,
    "general_materials": 203545642,
    "component_specific_materials": 203545612,
    "mc_answer_sheets": 29566949506322,
}

out = {"articles": {}, "searches": {}, "urls_found": {}}

for name, art_id in ARTICLE_IDS.items():
    ar = fetcher.get_text(f"{BASE}/en-gb/articles/{art_id}.json")
    rec = {"id": art_id, "http_error": ar.error}
    if ar.text:
        d = json.loads(ar.text)
        a = d.get("article", {})
        body_html = a.get("body") or ""
        body = re.sub(r"<[^>]+>", " ", body_html)
        body = re.sub(r"\s+", " ", body).strip()
        rec.update(
            {
                "title": a.get("title"),
                "html_url": a.get("html_url"),
                "updated_at": a.get("updated_at"),
                "body_text": body,
            }
        )
        rec["urls_in_body"] = sorted(set(re.findall(r"https?://[^\s\"'<>]+", body_html)))
    out["articles"][name] = rec
    print(f"article {name}: len={len(rec.get('body_text') or '')} urls={len(rec.get('urls_in_body') or [])}")

for q in ["additional exam materials", "additional materials list", "june 2026 materials"]:
    rr = fetcher.get_text(f"{BASE}/articles/search.json?query={q.replace(' ', '%20')}&per_page=25")
    rec = {"error": rr.error, "results": []}
    if rr.text:
        d = json.loads(rr.text)
        rec["count"] = d.get("count")
        for a in d.get("results", []):
            rec["results"].append(
                {"id": a.get("id"), "title": a.get("title"), "html_url": a.get("html_url")}
            )
    out["searches"][q] = rec
    print(f"search '{q}': count={rec.get('count')} err={rr.error}")

# 汇总所有正文/搜索结果中出现的 URL（含 Images/ 链接）
urls = {}
for name, rec in out["articles"].items():
    for u in rec.get("urls_in_body") or []:
        urls.setdefault(u, []).append(f"article:{name}")
for q, rec in out["searches"].items():
    for item in rec.get("results", []):
        if item.get("html_url"):
            urls.setdefault(item["html_url"], []).append(f"search:{q}")
out["urls_found"] = urls

OUT.joinpath("help_center_articles_content.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8"
)
print("wrote help_center_articles_content.json")

# 直接打印 Materials/Images 链接便于立即判断
print("\n=== Images/ links ===")
for u in sorted(urls):
    if "/Images/" in u or "materials" in u.lower():
        print(u, "  <-", urls[u][0])
