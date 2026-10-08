"""验证 MF19 独立 PDF + 官方帮助中心文章 + 2028 版 syllabus 公式表版本。"""

import hashlib
import io
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, r"C:/Users/weo/Desktop/api/examdata/src")
from examdata.core.config import Settings
from examdata.core.fetch import Fetcher
import pymupdf

OUT = Path(r"C:/Users/weo/Desktop/api/tmp_materials_probe")
EV = OUT / "evidence"
fetcher = Fetcher(Settings())

# 1) 独立 MF19
mf19_url = "https://www.cambridgeinternational.org/Images/417318-list-of-formulae-and-statistical-tables.pdf"
r = fetcher.get(mf19_url, expect_binary=True, follow_redirects=False)
print("MF19 standalone: HTTP", r.status, "bytes", len(r.content or b""), "err", r.error)
if r.content:
    (OUT / "downloads" / "MF19_417318.pdf").write_bytes(r.content)
    sha = hashlib.sha256(r.content).hexdigest()
    doc = pymupdf.open(stream=r.content, filetype="pdf")
    text = "\n".join(p.get_text() for p in doc)
    (EV / "MF19_417318.txt").write_text(text, encoding="utf-8")
    print("  sha256:", sha, "pages:", len(doc))
    print("  head:", re.sub(r"\s+", " ", text[:400]))

# 2) 官方帮助文章
art = "https://help.cambridgeinternational.org/hc/en-gb/articles/20756798012562-Which-list-of-formulae-do-candidates-use-for-the-AS-A-Level-examinations"
r2 = fetcher.get_text(art)
(EV / "help_mf19_article.html").write_text(r2.text or "", encoding="utf-8")
print("help article: HTTP", r2.status, "bytes", len(r2.text or ""), "err", r2.error)
if r2.text:
    m = re.search(r'<article[^>]*>(.*?)</article>', r2.text, re.S)
    body = m.group(1) if m else r2.text
    body = re.sub(r"<script.*?</script>", "", body, flags=re.S)
    body = re.sub(r"<style.*?</style>", "", body, flags=re.S)
    body = re.sub(r"<[^>]+>", " ", body)
    body = re.sub(r"\s+", " ", body)
    print("  body:", body[:700])

# 3) 帮助中心搜索 API（Zendesk 公共接口）
for q in ["formulae", "periodic table", "additional materials"]:
    url = f"https://help.cambridgeinternational.org/api/v2/help_center/articles/search.json?query={q.replace(' ', '%20')}&per_page=10"
    rr = fetcher.get_text(url)
    info = {"query": q, "http": rr.status}
    if rr.text:
        try:
            data = json.loads(rr.text)
            info["count"] = data.get("count")
            info["results"] = [{"title": a.get("title"), "url": a.get("html_url")} for a in data.get("results", [])[:10]]
        except Exception as e:
            info["parse_error"] = str(e)
    print(json.dumps(info, ensure_ascii=False, indent=1))
