"""Edexcel 全家族科目页 sweep：考试发放资料可得性 + Document-Type 直方图。

范围：4 个家族全部科目页（research/edexcel.md 实测 258 个）。
做法（全部走仓库 Fetcher，robots + 限速）：
  1) 用 EdexcelAdapter.discover_syllabuses() 枚举科目页（cq:Page servlet）。
  2) 每科：抓科目页 facet 标签 -> select_facet_tags -> servlet 全量查询（hitsPerPage=1000）。
     - 未饱和（<1000 条）：完整清单，本地统计直方图 + 材料候选。
     - 饱和（>=1000 条）：直方图只算「前 1000 条（部分）」；另外用
       关键词查询（query=...）与材料类 Document-Type 查询补齐材料候选。
  3) 逐科 checkpoint 到 evidence/edexcel_sweep_progress.json；支持断点续跑。
  4) 汇总落 evidence/edexcel_sweep.json。

只记录聚合与材料候选（不落全量记录），门禁只按 URL 前缀判定（不请求）。
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

from examdata.adapters.edexcel.adapter import FAMILIES, EdexcelAdapter  # noqa: E402
from examdata.adapters.edexcel.classify import category_value, is_gated  # noqa: E402
from examdata.core.config import Settings  # noqa: E402
from examdata.core.fetch import Fetcher  # noqa: E402

OUT = Path(r"C:/Users/weo/Desktop/api/tmp_materials_probe")
EV = OUT / "evidence"
SERVLET = "https://qualifications.pearson.com/services/pearson/algolia/GET.servlet"
PAGES_FILE = EV / "edexcel_all_pages.json"
PROGRESS_FILE = EV / "edexcel_sweep_progress.json"
FINAL_FILE = EV / "edexcel_sweep.json"

HITS = 1000

# 材料候选关键词：对完整清单做本地过滤（servlet 实测忽略 query 参数）。
KW_REGEX = re.compile(
    r"formula|formulae|statistic|periodic|booklet|insert|equation|data[\s\-_]?sheet|pre[\s\-_]?release",
    re.I,
)


def raw_query(fetcher: Fetcher, fq: str, extra: str = "") -> tuple[list[dict], int, str]:
    """返回 (records, http_status, error)。不抛 ShardExhausted——调用方自己判饱和。"""
    url = f"{SERVLET}?fq={quote(fq)}&hitsPerPage={HITS}{extra}"
    try:
        res = fetcher.get_text(url)
    except Exception as exc:  # noqa: BLE001
        return [], 0, f"request failed: {exc}"
    if not res.ok or not res.text:
        return [], res.status, f"HTTP {res.status}"
    try:
        data = json.loads(res.text)
    except ValueError:
        return [], res.status, "invalid JSON"
    recs = (data.get("searchResults") or {}).get("algoliaRecords")
    if not isinstance(recs, list):
        return [], res.status, "no algoliaRecords"
    return recs, res.status, ""


def build_fq(tags: list[str]) -> str:
    return " AND ".join(f"category:{json.dumps(t)}" for t in tags)


def rec_doc_type(rec: dict) -> str:
    v = category_value(rec.get("category") or [], "Pearson-UK:Document-Type")
    return (v or "").strip() or "(none)"


def rec_blob(rec: dict) -> str:
    return " ".join(
        str(rec.get(k) or "") for k in ("title", "url", "description", "extension")
    )


def material_entry(rec: dict, matched_by: str) -> dict:
    url = str(rec.get("url") or "")
    return {
        "title": rec.get("title"),
        "url": url,
        "gated": is_gated(url),
        "size": rec.get("size"),
        "extension": rec.get("extension"),
        "doc_type": rec_doc_type(rec),
        "series": category_value(rec.get("category") or [], "Pearson-UK:Exam-Series"),
        "unit": category_value(rec.get("category") or [], "Pearson-UK:Unit"),
        "spec_code": category_value(rec.get("category") or [], "Pearson-UK:Specification-Code"),
        "matched_by": matched_by,
    }


def summarize_records(records: list[dict], capped: bool, notes: list[str]) -> dict:
    types: dict[str, int] = {}
    public = gated = 0
    materials: dict[str, dict] = {}
    for rec in records:
        t = rec_doc_type(rec)
        types[t] = types.get(t, 0) + 1
        url = str(rec.get("url") or "")
        if is_gated(url):
            gated += 1
        else:
            public += 1
        if KW_REGEX.search(rec_blob(rec)):
            key = url or str(rec.get("objectID") or "")
            if key and key not in materials:
                materials[key] = material_entry(rec, "list" + ("(partial)" if capped else ""))
    out = {
        "doc_types": dict(sorted(types.items(), key=lambda kv: (-kv[1], kv[0]))),
        "public_count": public,
        "gated_count": gated,
        "materials": sorted(materials.values(), key=lambda m: str(m.get("title") or "")),
        "notes": notes,
    }
    if capped:
        out["doc_types_note"] = "partial: first 1000 records of a truncated result"
        out["materials_note"] = "list-derived materials may be partial; see material_queries"
    return out


def main() -> None:
    fresh = "--fresh" in sys.argv
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    fetcher = Fetcher(Settings())
    adapter = EdexcelAdapter(fetcher)

    # 1) 枚举科目页（可复用）
    if PAGES_FILE.exists() and not fresh:
        pages = json.loads(PAGES_FILE.read_text(encoding="utf-8"))
        print(f"[pages] reused {PAGES_FILE.name}: {len(pages)} pages", flush=True)
        if isinstance(pages, dict):
            pages = pages["pages"]
    else:
        pages = []
        fam_counts: dict[str, int] = {}
        fam_meta: dict[str, dict] = {}
        for fam in FAMILIES:
            facet = fam["facet_family"]
            url_fam = fam["url_family"]
            fq = (
                'type:"cq:Page" AND category:"Pearson-UK:Qualification-Family/%s"'
                ' AND NOT category:"page-type:news"' % facet
            )
            records, status, err = raw_query(fetcher, fq)
            prefix = f"/en/qualifications/{url_fam}/"
            slugs: set[str] = set()
            extras: list[str] = []
            for rec in records:
                url = str(rec.get("url") or "").strip()
                if url.startswith(prefix) and url.endswith(".html"):
                    tail = url[len(prefix) : -len(".html")]
                    if "/" not in tail:
                        slugs.add(tail)
                        continue
                extras.append(url)
            if len(records) >= HITS or err:
                raise SystemExit(
                    f"enumeration not provable for {facet}: n={len(records)} err={err!r} status={status}"
                )
            fam_counts[facet] = len(slugs)
            fam_meta[facet] = {
                "n_records": len(records),
                "http": status,
                "non_subject_urls": extras[:10],
                "non_subject_count": len(extras),
            }
            for slug in sorted(slugs):
                m = re.search(r"-(\d{4})(?:-|$)", slug)
                pages.append(
                    {
                        "slug": slug,
                        "title": "",
                        "family": facet,
                        "level": fam["level"],
                        "url": f"https://qualifications.pearson.com{prefix}{slug}.html",
                        "version_year": int(m.group(1)) if m else None,
                    }
                )
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "method": (
                'cq:Page servlet per family with NOT category:"page-type:news" '
                "(avoids the 1000-record truncation; every family response < 1000)"
            ),
            "family_counts": fam_counts,
            "family_meta": fam_meta,
            "total": len(pages),
            "pages": pages,
        }
        PAGES_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[pages] enumerated {len(pages)} pages: {fam_counts}", flush=True)

    # 2) 逐科 sweep（断点续跑）
    progress: dict = {"generated_at": None, "subjects": {}}
    if PROGRESS_FILE.exists() and not fresh:
        progress = json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
        print(f"[resume] {len(progress['subjects'])} subjects already done", flush=True)

    order = sorted(pages, key=lambda p: (p["family"], p["slug"]))
    t0 = time.time()
    processed = 0
    for i, page in enumerate(order):
        slug = page["slug"]
        if slug in progress["subjects"]:
            continue
        if limit is not None and processed >= limit:
            break
        processed += 1
        entry: dict = {
            "slug": slug,
            "title": page["title"],
            "family": page["family"],
            "level": page["level"],
            "page_url": page["url"],
            "notes": [],
        }
        try:
            raw_tags = adapter.subject_facet_tags(
                type("R", (), {  # 构造带 attrs 的轻量对象
                    "slug": slug,
                    "code": slug,
                    "attrs": {"subject_page_url": page["url"]},
                    "source_url": page["url"],
                })()
            )
        except Exception as exc:  # noqa: BLE001
            entry["notes"].append(f"page/tags failed: {exc}")
            entry["status"] = "page_failed"
            progress["subjects"][slug] = entry
            _save(progress)
            print(f"[{i+1}/{len(order)}] {slug}: PAGE FAILED {exc}", flush=True)
            continue
        picked = EdexcelAdapter.select_facet_tags(list(raw_tags or []))
        entry["tags_count"] = len(raw_tags or [])
        entry["picked"] = picked
        if not picked:
            entry["notes"].append("no usable facet tags")
            entry["status"] = "no_tags"
            progress["subjects"][slug] = entry
            _save(progress)
            print(f"[{i+1}/{len(order)}] {slug}: NO TAGS", flush=True)
            continue

        fq = build_fq(picked)
        records, status, err = raw_query(fetcher, fq)
        entry["servlet_status"] = status
        if err:
            entry["notes"].append(f"servlet: {err}")
            entry["status"] = "servlet_failed"
            progress["subjects"][slug] = entry
            _save(progress)
            print(f"[{i+1}/{len(order)}] {slug}: SERVLET {err}", flush=True)
            continue

        capped = len(records) >= HITS
        entry["n_records"] = len(records)
        entry["capped"] = capped
        entry["status"] = "ok"
        summary = summarize_records(records, capped, entry["notes"])
        entry.update(summary)

        if capped:
            # servlet 实测忽略 query / facets / page 参数，关键词补充不可行；
            # 饱和科目留待第二遍「Document-Type 分片 + NOT 残差校验」补齐。
            entry["notes"].append(
                "capped at 1000: materials from first page only; completion pass pending"
            )

        progress["subjects"][slug] = entry
        _save(progress)
        dt = time.time() - t0
        print(
            f"[{i+1}/{len(order)}] {slug}: n={entry['n_records']}"
            f"{' CAPPED' if capped else ''} mat={len(entry.get('materials') or [])}"
            f" types={len(entry.get('doc_types') or {})} ({dt:.0f}s)",
            flush=True,
        )

    progress["generated_at"] = datetime.now(timezone.utc).isoformat()
    _save(progress)
    # 汇总
    total = len(progress["subjects"])
    ok = sum(1 for s in progress["subjects"].values() if s.get("status") == "ok")
    failed = total - ok
    final = {
        "generated_at": progress["generated_at"],
        "pages_total": len(order),
        "subjects_done": total,
        "subjects_ok": ok,
        "subjects_failed": failed,
        "family_counts": json.loads(PAGES_FILE.read_text(encoding="utf-8"))["family_counts"],
    }
    FINAL_FILE.write_text(json.dumps(final, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[done] {total} subjects, ok={ok}, failed={failed}", flush=True)


def _save(progress: dict) -> None:
    tmp = PROGRESS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(progress, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(PROGRESS_FILE)


if __name__ == "__main__":
    main()
