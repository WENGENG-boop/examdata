"""探测C：Edexcel/Pearson 考试发放资料可得性。

步骤：
1) Algolia servlet 枚举 IAL/IGCSE 科目页（type:"cq:Page"）
2) 抽 facet 标签 → 查该科全部记录 → 统计 Document-Type
3) 关键词过滤（formulae/statistical/periodic/data booklet/insert/equation/resource）
4) 公共 PDF 实际下载 + sha256；silver/secure 记录计数（不触碰）
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, r"C:/Users/weo/Desktop/api/examdata/src")
from examdata.core.config import Settings
from examdata.core.fetch import Fetcher

ORIGIN = "https://qualifications.pearson.com"
SERVLET = "/services/pearson/algolia/GET.servlet"

OUT = Path(r"C:/Users/weo/Desktop/api/tmp_materials_probe")
EV = OUT / "evidence"
DL = OUT / "downloads"
fetcher = Fetcher(Settings())

import hashlib


def servlet_query(fq, hits=1000):
    from urllib.parse import quote
    url = f"{ORIGIN}{SERVLET}?fq={quote(fq)}&hitsPerPage={hits}"
    r = fetcher.get_text(url)
    if not r.text:
        return None, r
    try:
        data = json.loads(r.text)
    except Exception:
        return None, r
    recs = (data.get("searchResults") or {}).get("algoliaRecords") or []
    return recs, r


RE_NG_INIT_FACETS = re.compile(
    r"""data-ng-controller="facetListCtrl"[^>]*data-ng-init="init\('([^']*)',\s*'\[([^\]]*)\]'""",
    re.I | re.S)


def page_tags(slug, family_url):
    url = f"{ORIGIN}/en/qualifications/{family_url}/{slug}.html"
    r = fetcher.get_text(url)
    if not r.text:
        return None, r.status
    m = RE_NG_INIT_FACETS.search(r.text)
    if not m:
        return None, r.status
    tags = [t.strip() for t in m.group(2).split(",") if t.strip()]
    return tags, r.status


def pick_tags(tags):
    family = [t for t in tags if t.startswith("Pearson-UK:Qualification-Family/")]
    subject = [t for t in tags if t.startswith("Pearson-UK:Qualification-Subject/")]
    spec = [t for t in tags if t.startswith("Pearson-UK:Specification-Code/")]
    picked = family + subject
    if spec:
        picked.append(max(spec, key=lambda t: (t.count("/"), -len(t))))
    return picked


# 1) IAL 家族科目页
recs, r = servlet_query('type:"cq:Page" AND category:"Pearson-UK:Qualification-Family/International-Advanced-Level"')
print("IAL cq:Page records:", len(recs or []), "HTTP", r.status)
ial_pages = []
for rec in recs or []:
    u = rec.get("url") or ""
    m = re.match(r"^/en/qualifications/edexcel-international-advanced-levels/([a-z0-9-]+)\.html$", u)
    if m:
        ial_pages.append(m.group(1))
print("IAL 科目页 slugs:", sorted(ial_pages))
(EV / "edexcel_ial_pages.json").write_text(json.dumps(sorted(ial_pages), indent=1), encoding="utf-8")

# IGCSE 家族
recs2, r2 = servlet_query('type:"cq:Page" AND category:"Pearson-UK:Qualification-Family/International-GCSE"')
ig_pages = []
for rec in recs2 or []:
    u = rec.get("url") or ""
    m = re.match(r"^/en/qualifications/edexcel-international-gcses/([a-z0-9-]+)\.html$", u)
    if m:
        ig_pages.append(m.group(1))
print("IGCSE 科目页数:", len(ig_pages))
(EV / "edexcel_igcse_pages.json").write_text(json.dumps(sorted(ig_pages), indent=1), encoding="utf-8")

# 2) 目标科目标签
targets = [
    ("ial", "international-advanced-level-mathematics-2018", "edexcel-international-advanced-levels"),
    ("ial", "international-advanced-level-chemistry-2018", "edexcel-international-advanced-levels"),
    ("ial", "international-advanced-level-physics-2018", "edexcel-international-advanced-levels"),
    ("ig", "international-gcse-mathematics-a-2016", "edexcel-international-gcses"),
    ("ig", "international-gcse-chemistry-2017", "edexcel-international-gcses"),
]
# slug 可能不存在；若 404 再从列表里找近似
seen = {}
for fam_key, slug, fam_url in targets:
    tags, status = page_tags(slug, fam_url)
    print(f"== {slug}: HTTP {status} tags={tags}")
    if tags:
        seen[slug] = {"tags": tags}

# slug 近似匹配（打印含 maths/chem/phys 的候选）
for kw in ("maths", "mathematics", "chemistry", "physics"):
    cand = [s for s in ial_pages if kw in s]
    print(f"   IAL 候选[{kw}]:", cand)

# 3) 对成功科目标签查记录
def query_subject(tags):
    fq = " AND ".join(f'category:{json.dumps(t)}' for t in tags)
    recs, r = servlet_query(fq)
    return recs or [], r

report = {"pages": {}, "doc_types": {}, "keyword_hits": {}, "secure_counts": {}}
for slug, info in seen.items():
    picked = pick_tags(info["tags"])
    recs, r = query_subject(picked)
    print(f"\n== {slug} 记录数 {len(recs)} HTTP {r.status} picked={picked}")
    types = {}
    secure = 0
    kw_hits = []
    for rec in recs:
        cats = rec.get("category") or []
        dt = [c.split("/", 1)[1] for c in cats if c.startswith("Pearson-UK:Document-Type/")]
        for t in dt:
            types[t] = types.get(t, 0) + 1
        url = rec.get("url") or ""
        if "/secure/" in url:
            secure += 1
        title = rec.get("title") or ""
        if re.search(r"formula|statistic|periodic|data booklet|booklet|insert|equation|resource|table", title, re.I):
            kw_hits.append({"title": title, "url": url, "gating": rec.get("gating"), "size": rec.get("size")})
    report["pages"][slug] = {"picked": picked, "n": len(recs)}
    report["doc_types"][slug] = types
    report["keyword_hits"][slug] = kw_hits
    report["secure_counts"][slug] = secure
    print("   Document-Type:", json.dumps(types, ensure_ascii=False))
    print("   secure/silver:", secure)
    for h in kw_hits[:25]:
        print("   *", h["title"], "|", h["url"], "| gating:", h["gating"])

(EV / "edexcel_materials_probe.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
print("\nsaved edexcel_materials_probe.json")
