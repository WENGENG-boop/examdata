"""补抓：考试官指南页（寻找 June/Nov 附加材料清单链接 + MC 答题卡表格下载）+ 相关帮助文章。

输出：evidence/help_center_articles_more.json
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

out = {"pages": {}, "articles": {}}

# 1) 指南页面：phase-4（find additional materials list）与 phase-5（MC answer sheet 下载）
PAGES = {
    "guide_phase4_before_exam": "https://www.cambridgeinternational.org/cambridge-for/exams-officers/cambridge-exams-officers-guide/phase-4-before-the-exam/",
    "guide_phase5_running_exams": "https://www.cambridgeinternational.org/cambridge-for/exams-officers/cambridge-exams-officers-guide/phase-5-exam-day/running-exams/",
}
for name, url in PAGES.items():
    r = fetcher.get_text(url)
    rec = {"url": url, "error": r.error, "status": getattr(r, "status_code", None)}
    if r.text:
        rec["final_url"] = getattr(r, "url", None)
        rec["chars"] = len(r.text)
        rec["title"] = (re.search(r"<title[^>]*>(.*?)</title>", r.text, re.S | re.I) or [None, None])[1]
        links = sorted(set(re.findall(r'href="([^"]+)"', r.text)))
        rec["pdf_links"] = [u for u in links if re.search(r"\.pdf|Images/", u, re.I)]
        rec["relevant_links"] = [
            u for u in links
            if re.search(r"material|timetable|answer|form|despatch|test", u, re.I)
        ]
        rec["has_additional"] = bool(re.search(r"additional exam materials", r.text, re.I))
        # 保存正文节选（含关键词周边）
        body = re.sub(r"<script.*?</script>|<style.*?</style>", " ", r.text, flags=re.S | re.I)
        body = re.sub(r"<[^>]+>", " ", body)
        body = re.sub(r"\s+", " ", body).strip()
        rec["body_text"] = body[:4000]
    out["pages"][name] = rec
    print(f"page {name}: err={r.error} status={rec.get('status')} pdf={len(rec.get('pdf_links') or [])}")

# 2) 其它相关帮助文章
MORE_ARTICLES = {
    "periodic_table": 19811608119826,
    "pre_release_distribution": 22999029665554,
    "speaking_materials": 30369309016210,
    "admin_material_despatch": 29566508688402,
    "what_students_use": 115004303689,
}
for name, art_id in MORE_ARTICLES.items():
    ar = fetcher.get_text(f"{BASE}/en-gb/articles/{art_id}.json")
    rec = {"id": art_id, "http_error": ar.error}
    if ar.text:
        d = json.loads(ar.text)
        a = d.get("article", {})
        body_html = a.get("body") or ""
        body = re.sub(r"<script.*?</script>|<style.*?</style>", " ", body_html, flags=re.S | re.I)
        body = re.sub(r"<[^>]+>", " ", body)
        body = re.sub(r"\s+", " ", body).strip()
        rec.update(
            {
                "title": a.get("title"),
                "html_url": a.get("html_url"),
                "updated_at": a.get("updated_at"),
                "body_text": body,
                "urls_in_body": sorted(set(re.findall(r"https?://[^\s\"'<>]+", body_html))),
            }
        )
    out["articles"][name] = rec
    print(f"article {name}: chars={len(rec.get('body_text') or '')}")

OUT.joinpath("help_center_articles_more.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8"
)
print("wrote help_center_articles_more.json")

print("\n=== phase4 relevant links ===")
for u in (out["pages"]["guide_phase4_before_exam"].get("relevant_links") or [])[:40]:
    print(" ", u)
print("=== phase5 relevant links ===")
for u in (out["pages"]["guide_phase5_running_exams"].get("relevant_links") or [])[:40]:
    print(" ", u)
