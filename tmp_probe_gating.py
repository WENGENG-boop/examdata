"""临时：探测 legacy 科目 QP/MS 的 gating 比例 + it/CS 可枚举性。

只读网络：每科一次 full 查询；不写 DB、不落 catalog。
用法: python tmp_probe_gating.py
输出: tmp_probe_gating_out.json
"""
import json
import sys

sys.path.insert(0, "src")

from examdata.adapters.edexcel.adapter import EdexcelAdapter
from examdata.adapters.edexcel.classify import category_value
from examdata.adapters.edexcel.servlet import ShardExhausted, fetch_records
from examdata.core.config import get_settings
from examdata.core.fetch import Fetcher
from examdata.edexcel_papers.enumerate import (
    dedup_records,
    keep_qp_ms,
    resolve_tags,
    syllabus_ref,
)

SLUGS = [
    "ial18-it",
    "ial26-computer-science",
    "ial-accounting",
    "ial-psychology",
    "ial-maths",
    "ial-history",
]


def main() -> None:
    settings = get_settings()
    fetcher = Fetcher(settings)
    out = []
    try:
        for slug in SLUGS:
            ref = syllabus_ref(slug)
            try:
                adapter = EdexcelAdapter(fetcher)
                tags, tags_source, notes = resolve_tags(adapter, ref)
                try:
                    records = fetch_records(fetcher, tags)
                    kept = keep_qp_ms(dedup_records(records))
                    qp_gated = ms_gated = qp_open = ms_open = 0
                    series_set = set()
                    for rec in kept:
                        raw = (
                            category_value(
                                rec.get("category") or [], "Pearson-UK:Document-Type"
                            )
                            or ""
                        ).strip().lower()
                        gated = bool(rec.get("gating"))
                        for cat in rec.get("category") or []:
                            if str(cat).startswith("Pearson-UK:Exam-Series/"):
                                series_set.add(str(cat).split("/", 1)[1])
                        if raw == "question-paper":
                            if gated:
                                qp_gated += 1
                            else:
                                qp_open += 1
                        elif raw == "mark-scheme":
                            if gated:
                                ms_gated += 1
                            else:
                                ms_open += 1
                    rec_out = {
                        "slug": slug,
                        "tags_source": tags_source,
                        "query": "full",
                        "records_total": len(records),
                        "kept_qp_ms": len(kept),
                        "qp_gated": qp_gated,
                        "qp_open": qp_open,
                        "ms_gated": ms_gated,
                        "ms_open": ms_open,
                        "series_n": len(series_set),
                        "series_sample": sorted(series_set)[:8],
                        "notes": notes[:2],
                    }
                except ShardExhausted as exc:
                    rec_out = {
                        "slug": slug,
                        "tags_source": tags_source,
                        "shard_exhausted": True,
                        "detail": str(exc)[:200],
                    }
            except Exception as exc:
                rec_out = {"slug": slug, "error": f"{type(exc).__name__}: {str(exc)[:300]}"}
            out.append(rec_out)
            print(json.dumps(rec_out, ensure_ascii=False), flush=True)
    finally:
        fetcher.close()
    with open("tmp_probe_gating_out.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print("written tmp_probe_gating_out.json", flush=True)


if __name__ == "__main__":
    main()
