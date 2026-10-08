"""补齐 25 个家族变体页：258 页中与 progress 主条目 (slug,url) 不同的条目。

背景：第一遍 sweep（sweep_edexcel_subjects.py）按 (family, slug) 排序后每 slug
只处理了第一条（family 字典序最靠前的变体），20 个 slug 的其余 25 条家族页
从未得到结论。这些页不出现在 failed_page_classes 里（它们压根没被访问过）。

本脚本：
  1) 从 edexcel_all_pages.json 与 edexcel_sweep_progress.json 求出 25 条变体；
  2) 复用 edexcel_page_records.json 的 cq:Page 记录做 path/slug 精确匹配；
  3) select_facet_tags → 基查询 → 材料汇总（与 recover_live_pages.py 同构）；
  4) 附主条目摘要（family/status/n_records/材料数）便于报告对照。
输出 evidence/edexcel_dup_variants_sweep.json。全部请求走仓库 Fetcher（单线程）。
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
ALL_PAGES = EV / "edexcel_all_pages.json"
PROGRESS = EV / "edexcel_sweep_progress.json"
PAGE_RECORDS = EV / "edexcel_page_records.json"
OUT = EV / "edexcel_dup_variants_sweep.json"
SERVLET = "https://qualifications.pearson.com/services/pearson/algolia/GET.servlet"
HITS = 1000

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
                    "matched_by": "dup_variant",
                }
    return {
        "doc_types": dict(sorted(types.items(), key=lambda kv: (-kv[1], kv[0]))),
        "public_count": public,
        "gated_count": gated,
        "materials": sorted(materials.values(), key=lambda m: str(m.get("title") or "")),
    }


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


def main() -> None:
    all_pages = json.loads(ALL_PAGES.read_text(encoding="utf-8"))
    progress = json.loads(PROGRESS.read_text(encoding="utf-8"))["subjects"]
    records_file = json.loads(PAGE_RECORDS.read_text(encoding="utf-8"))

    # 1) 求变体页：slug 已有主条目，但 (family,url) 与主条目不同。
    main_url = {s: str((v.get("page_url") or "")) for s, v in progress.items()}
    variants = [
        p for p in all_pages["pages"]
        if p["slug"] in main_url and p["url"].lower() != main_url[p["slug"]].lower()
    ]
    print(f"[plan] {len(all_pages['pages'])} pages, {len(progress)} slugs, {len(variants)} variants", flush=True)

    # 2) 记录索引（与 recover_live_pages.py 同构）。
    path_index: dict[str, list[dict]] = {}
    slug_index: dict[str, list[dict]] = {}
    for facet, recs in (records_file.get("records") or {}).items():
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
        want = norm_path(str(page.get("url") or ""))
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

    fetcher = Fetcher(Settings())
    t0 = time.time()
    out: dict = {
        "generated_at": None,
        "plan": {
            "pages_total": len(all_pages["pages"]),
            "slugs": len(progress),
            "variants": len(variants),
            "source": "edexcel_all_pages.json vs edexcel_sweep_progress.json",
        },
        "variants": {},
    }

    def flush() -> None:
        out["generated_at"] = datetime.now(timezone.utc).isoformat()
        OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    flush()

    for i, page in enumerate(variants, 1):
        slug = str(page.get("slug"))
        fam = str(page.get("family"))
        key = f"{fam}/{slug}"
        recs, how = lookup(page)
        info: dict = {
            "slug": slug,
            "family": fam,
            "level": page.get("level"),
            "version_year": page.get("version_year"),
            "page_url": page.get("url"),
            "match": how,
            "main_entry": {
                k: progress[slug].get(k)
                for k in ("family", "level", "page_url", "status", "n_records", "capped", "notes")
            },
            "main_materials_count": len(progress[slug].get("materials") or []),
        }
        if not recs:
            info["status"] = "no_page_record"
        else:
            tags: list[str] = []
            for r in recs:
                tags.extend(c for c in (r.get("category") or []) if isinstance(c, str))
            seen: set[str] = set()
            tags = [t for t in tags if not (t in seen or seen.add(t))]
            info["tags"] = tags
            info["page_records"] = [
                {"url": r.get("url"), "title": r.get("title"), "fam": r.get("_fam")} for r in recs
            ]
            picked = EdexcelAdapter.select_facet_tags(tags)
            if not picked or not any(
                "Specification-Code" in p or "Qualification-Subject" in p for p in picked
            ):
                info["status"] = "record_no_usable_facet"
                info["picked"] = picked
            else:
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
        out["variants"][key] = info
        print(
            f"[{i}/{len(variants)}] {key}: {info['status']} n={info.get('n_records')}"
            f" mat={len(info.get('materials') or [])} ({time.time()-t0:.0f}s)",
            flush=True,
        )
        flush()

    ok = sum(1 for v in out["variants"].values() if v.get("status") == "ok")
    mats = sum(len(v.get("materials") or []) for v in out["variants"].values())
    out["summary"] = {"variants": len(out["variants"]), "ok": ok, "material_rows": mats}
    flush()
    fetcher.close()
    print(f"done: variants={len(out['variants'])} ok={ok} material_rows={mats} ({time.time()-t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
