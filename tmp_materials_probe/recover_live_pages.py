"""恢复 83 个失败页：用 cq:Page servlet 记录的 category 数组做 facet 来源。

背景：第一遍 sweep 逐页抓 HTML 抽 facet，有 25 页活页拿不到 facet（页面 facet 块
缺失/瞬时报错/软跳转到家族页）。但 servlet 的 cq:Page 记录本身带 category 数组
（Family / Subject / Specification-Code），可直接作为查询基。

流程：
  1) 4 个 family 各查一次 type:"cq:Page"（<1000 即完整），落 evidence/edexcel_page_records.json；
  2) 按完整页面路径索引（记录 url 为相对路径；重名 slug 用 family 消歧）；
  3) 对 25 个 live_no_facet 页：从记录取 facet → servlet 查材料（hitsPerPage=1000）→ 汇总；
  4) 对 58 个 dead_404 页：先查记录，有可用 facet 的也查材料（页已删，结论随附标注）；
  5) capped 三科只取记录 tags（不做材料查询），供 finalize_capped.py 核对基查询。
结果写 evidence/edexcel_live_pages_recovery.json。全部请求走仓库 Fetcher（单线程）。
"""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, r"C:/Users/weo/Desktop/api/examdata/src")

from examdata.adapters.edexcel.adapter import EdexcelAdapter  # noqa: E402
from examdata.adapters.edexcel.classify import category_value, is_gated  # noqa: E402
from examdata.core.config import Settings  # noqa: E402
from examdata.core.fetch import Fetcher  # noqa: E402

EV = Path(r"C:/Users/weo/Desktop/api/tmp_materials_probe/evidence")
PAGES_OUT = EV / "edexcel_page_records.json"
OUT = EV / "edexcel_live_pages_recovery.json"
SERVLET = "https://qualifications.pearson.com/services/pearson/algolia/GET.servlet"
HITS = 1000

FAMS = [
    ("International-GCSE", "edexcel-international-gcses"),
    ("International-Advanced-Level", "edexcel-international-advanced-levels"),
    ("A-Level", "edexcel-a-levels"),
    ("GCSE", "edexcel-gcses"),
]

KW_REGEX = re.compile(
    r"formula|formulae|statistic|periodic|booklet|insert|equation|data[\s\-_]?sheet|pre[\s\-_]?release",
    re.I,
)
RE_SLUG = re.compile(r"/([a-z0-9\-]+)\.html$", re.I)


def probe(fetcher: Fetcher, fq: str, hits: int = HITS) -> tuple[list[dict], int, int]:
    url = f"{SERVLET}?fq={quote(fq)}&hitsPerPage={hits}"
    res = fetcher.get_text(url)
    if not res.ok or not res.text:
        return [], res.status, -1
    data = json.loads(res.text)
    sr = data.get("searchResults") or {}
    recs = sr.get("algoliaRecords")
    if not isinstance(recs, list):
        return [], res.status, -1
    nb = sr.get("nbHits")
    if not isinstance(nb, int):
        nb = -1
    return recs, res.status, nb


def summarize(records: list[dict]) -> dict:
    types: dict[str, int] = {}
    public = gated = 0
    materials: dict[str, dict] = {}
    for rec in records:
        t = (category_value(rec.get("category") or [], "Pearson-UK:Document-Type") or "").strip() or "(none)"
        types[t] = types.get(t, 0) + 1
        url = str(rec.get("url") or "")
        if is_gated(url):
            gated += 1
        else:
            public += 1
        blob = " ".join(str(rec.get(k) or "") for k in ("title", "url", "description", "extension"))
        if KW_REGEX.search(blob):
            key = url or str(rec.get("objectID") or "")
            if key and key not in materials:
                materials[key] = {
                    "title": rec.get("title"),
                    "url": url,
                    "gated": is_gated(url),
                    "size": rec.get("size"),
                    "extension": rec.get("extension"),
                    "doc_type": t,
                    "series": category_value(rec.get("category") or [], "Pearson-UK:Exam-Series"),
                    "unit": category_value(rec.get("category") or [], "Pearson-UK:Unit"),
                    "spec_code": category_value(rec.get("category") or [], "Pearson-UK:Specification-Code"),
                    "matched_by": "recovery",
                }
    return {
        "doc_types": dict(sorted(types.items(), key=lambda kv: (-kv[1], kv[0]))),
        "public_count": public,
        "gated_count": gated,
        "materials": sorted(materials.values(), key=lambda m: str(m.get("title") or "")),
    }


def subject_keyword(slug: str) -> str:
    k = re.sub(r"-\d{4}(-modular)?$", "", slug, flags=re.I)
    k = re.sub(r"^international-gcse-", "", k, flags=re.I)
    return k.replace("-", " ")


def main() -> None:
    classify = json.loads((EV / "edexcel_failed_page_classes.json").read_text(encoding="utf-8"))
    live = [p for p in classify["pages"].values() if p["kind"] == "live_no_facet"]
    dead = [p for p in classify["pages"].values() if p["kind"] == "dead_404"]

    fetcher = Fetcher(Settings())
    t0 = time.time()

    fam_records: dict[str, list[dict]] = {}
    fam_meta: dict[str, dict] = {}
    for facet, url_fam in FAMS:
        fq = (
            'type:"cq:Page" AND category:"Pearson-UK:Qualification-Family/%s"'
            ' AND NOT category:"page-type:news"' % facet
        )
        recs, status, nb = probe(fetcher, fq)
        fam_records[facet] = recs
        fam_meta[facet] = {
            "http": status,
            "n": len(recs),
            "nbHits": nb,
            "capped": len(recs) >= HITS,
            "url_family": url_fam,
        }
        print(f"[fam] {facet}: n={len(recs)} nbHits={nb} (http {status}) ({time.time()-t0:.0f}s)", flush=True)
    if not any(fam_records.values()):
        print("ERROR: all family page-record queries returned empty; aborting", flush=True)
        sys.exit(1)
    PAGES_OUT.write_text(
        json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(), "families": fam_meta, "records": fam_records},
                   ensure_ascii=False, indent=1),
        encoding="utf-8",
    )

    def norm_path(raw: str) -> str:
        s = raw.strip()
        low = s.lower()
        for scheme in ("https://qualifications.pearson.com", "http://qualifications.pearson.com"):
            if low.startswith(scheme):
                s = s[len(scheme):]
                break
        s = s.split("#", 1)[0].split("?", 1)[0]
        if not s.startswith("/"):
            s = "/" + s
        return s.lower()

    path_index: dict[str, list[dict]] = {}
    slug_index: dict[str, list[dict]] = {}
    for facet, recs in fam_records.items():
        for rec in recs:
            raw = str(rec.get("url") or "")
            entry = {**rec, "_fam": facet}
            p = norm_path(raw)
            if p:
                path_index.setdefault(p, []).append(entry)
            m = RE_SLUG.search(raw)
            if m:
                slug_index.setdefault(m.group(1).lower(), []).append(entry)

    def lookup(page: dict) -> tuple[list[dict], str]:
        """按完整路径优先匹配；失败依次退到 slug+family、slug（含前缀变体）。"""
        want = norm_path(str(page.get("page_url") or ""))
        recs = list(path_index.get(want, []))
        if recs:
            return recs, "path"
        slug = str(page.get("slug") or "").lower()
        fam = page.get("family")
        recs = [r for r in slug_index.get(slug, []) if r.get("_fam") == fam]
        if recs:
            return recs, "slug+family"
        recs = list(slug_index.get(slug, []))
        if recs:
            return recs, "slug"
        alt = "international-gcse-" + slug
        recs = [r for r in slug_index.get(alt, []) if r.get("_fam") == fam]
        if recs:
            return recs, "slug+family"
        recs = list(slug_index.get(alt, []))
        return recs, "slug" if recs else "none"

    out: dict = {"generated_at": None, "fam_meta": fam_meta, "live": {}, "dead": {}, "capped_records": {}}

    def process(page: dict, need_materials: bool) -> dict:
        slug = str(page.get("slug") or "")
        recs, how = lookup(page)
        info: dict = {
            "page_url": page.get("page_url"),
            "family": page.get("family"),
            "page_kind": page.get("kind"),
            "match": how,
            "page_records": [
                {"url": r.get("url"), "title": r.get("title"), "fam": r.get("_fam")} for r in recs
            ],
        }
        if not recs:
            info["status"] = "no_page_record"
            return info
        tags: list[str] = []
        for r in recs:
            tags.extend(c for c in (r.get("category") or []) if isinstance(c, str))
        # 去重保序
        seen = set()
        tags = [t for t in tags if not (t in seen or seen.add(t))]
        info["tags"] = tags
        info["status"] = "record_found"
        if not need_materials:
            return info
        picked = EdexcelAdapter.select_facet_tags(tags)
        if not picked or not any("Specification-Code" in p or "Qualification-Subject" in p for p in picked):
            info["status"] = "record_no_usable_facet"
            info["picked"] = picked
            return info
        base_fq = " AND ".join(f"category:{json.dumps(t)}" for t in picked)
        recs2, status, nb = probe(fetcher, base_fq)
        info["status"] = "ok"
        info["picked"] = picked
        info["base_fq"] = base_fq
        info["http"] = status
        info["nbHits"] = nb
        info["n_records"] = len(recs2)
        info["capped"] = len(recs2) >= HITS
        info.update(summarize(recs2))
        kw = subject_keyword(slug)
        toks = [t for t in kw.split() if len(t) >= 4]
        if toks:
            blob_all = " ".join(
                (str(r.get("title") or "") + " " + str(r.get("url") or "")).lower() for r in recs2
            )
            info["subject_tokens"] = toks
            info["subject_match_n"] = sum(1 for r in recs2 if all(t in (str(r.get("title") or "") + " " + str(r.get("url") or "")).lower() for t in toks))
        return info

    # capped 三科：只取记录 tags 供 finalize_capped.py 核对基查询，不做材料查询。
    prog = json.loads((EV / "edexcel_sweep_progress.json").read_text(encoding="utf-8"))["subjects"]
    for key in ("edexcel-a-level-geography-2015", "history-2015", "mathematics-2018"):
        entry = prog.get(key) or {}
        page = {
            "slug": entry.get("slug") or key,
            "page_url": entry.get("page_url"),
            "family": entry.get("family"),
            "kind": "capped",
        }
        try:
            out["capped_records"][key] = process(page, need_materials=False)
        except Exception as exc:  # noqa: BLE001
            out["capped_records"][key] = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
        print(f"[capped] {key}: {out['capped_records'][key].get('status')} match={out['capped_records'][key].get('match')}", flush=True)

    def flush() -> None:
        out["generated_at"] = datetime.now(timezone.utc).isoformat()
        OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    flush()

    for i, page in enumerate(live, 1):
        slug = str(page.get("slug"))
        try:
            out["live"][slug] = process(page, need_materials=True)
        except Exception as exc:  # noqa: BLE001
            out["live"][slug] = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
        print(f"[live {i}/{len(live)}] {slug}: {out['live'][slug].get('status')}"
              f" n={out['live'][slug].get('n_records')} mat={len(out['live'][slug].get('materials') or [])}"
              f" ({time.time()-t0:.0f}s)", flush=True)
        flush()

    for i, page in enumerate(dead, 1):
        slug = str(page.get("slug"))
        try:
            out["dead"][slug] = process(page, need_materials=True)
        except Exception as exc:  # noqa: BLE001
            out["dead"][slug] = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
        st = out["dead"][slug].get("status")
        print(f"[dead {i}/{len(dead)}] {slug}: {st} n={out['dead'][slug].get('n_records')}"
              f" mat={len(out['dead'][slug].get('materials') or [])} ({time.time()-t0:.0f}s)", flush=True)
        flush()

    fetcher.close()
    print("done", flush=True)


if __name__ == "__main__":
    main()
