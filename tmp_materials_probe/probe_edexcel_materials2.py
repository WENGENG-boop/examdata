"""探测C-2：Edexcel 考试发放资料关键词检索（修正 slug）。"""

import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, r"C:/Users/weo/Desktop/api/examdata/src")
from examdata.core.config import Settings
from examdata.core.fetch import Fetcher

ORIGIN = "https://qualifications.pearson.com"
OUT = Path(r"C:/Users/weo/Desktop/api/tmp_materials_probe")
EV, DL = OUT / "evidence", OUT / "downloads"
fetcher = Fetcher(Settings())


def servlet(fq, hits=1000):
    url = f"{ORIGIN}/services/pearson/algolia/GET.servlet?fq={quote(fq)}&hitsPerPage={hits}"
    r = fetcher.get_text(url)
    if not r.text:
        return None, r
    try:
        return json.loads(r.text).get("searchResults", {}).get("algoliaRecords", []), r
    except Exception:
        return None, r


RE_NG_INIT_FACETS = re.compile(
    r"""data-ng-controller="facetListCtrl".*?data-ng-init="init\('([^']*)',\s*'\[([^\]]*)\]'""",
    re.I | re.S)


def page_tags(family_url, slug):
    url = f"{ORIGIN}/en/qualifications/{family_url}/{slug}.html"
    r = fetcher.get_text(url)
    if not r.text:
        return None
    m = RE_NG_INIT_FACETS.search(r.text)
    if not m:
        return None
    return [t.strip() for t in m.group(2).split(",") if t.strip()]


def pick(tags):
    fam = [t for t in tags if t.startswith("Pearson-UK:Qualification-Family/")]
    subj = [t for t in tags if t.startswith("Pearson-UK:Qualification-Subject/")]
    spec = [t for t in tags if t.startswith("Pearson-UK:Specification-Code/")]
    out = fam + subj
    if spec:
        out.append(max(spec, key=lambda t: (t.count("/"), -len(t))))
    return out


KW = re.compile(r"formula|statistic|periodic|data booklet|booklet|insert|equation|mol|table", re.I)

TARGETS = [
    ("IAL", "edexcel-international-advanced-levels", "mathematics-2018"),
    ("IAL", "edexcel-international-advanced-levels", "chemistry-2018"),
    ("IAL", "edexcel-international-advanced-levels", "physics-2018"),
    ("IAL", "edexcel-international-advanced-levels", "biology-2018"),
    ("IGCSE", "edexcel-international-gcses", "international-gcse-mathematics-a-2016"),
    ("IGCSE", "edexcel-international-gcses", "international-gcse-chemistry-2017"),
]

out = {}
kw_all = {}
for fam, family_url, slug in TARGETS:
    tags = page_tags(family_url, slug)
    print(f"== {fam} {slug}: tags={'ok' if tags else None}")
    if not tags:
        continue
    picked = pick(tags)
    recs, r = servlet(" AND ".join(f'category:{json.dumps(t)}' for t in picked))
    n = len(recs or [])
    print(f"   picked={picked}\n   records={n} HTTP {r.status}")
    hits = []
    types = {}
    for rec in recs or []:
        cats = rec.get("category") or []
        for c in cats:
            if c.startswith("Pearson-UK:Document-Type/"):
                t = c.split("/", 1)[1]
                types[t] = types.get(t, 0) + 1
        blob = (rec.get("title") or "") + " " + (rec.get("description") or "")
        if KW.search(blob):
            hits.append({
                "title": rec.get("title"), "desc": rec.get("description"),
                "url": rec.get("url"), "gating": rec.get("gating"),
                "size": rec.get("size"),
            })
    out[slug] = {"picked": picked, "n": n, "types": types, "hits": hits}
    kw_all[slug] = hits
    print(f"   types={json.dumps(types, ensure_ascii=False)}")
    for h in hits[:30]:
        print(f"   * {h['title']} | {h['url']} | gating={h['gating']}")

EV.joinpath("edexcel_materials_probe2.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
print("saved")
