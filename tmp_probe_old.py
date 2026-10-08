"""临时：探测 13 个旧 IAL 科目在 Pearson servlet 的试卷可获取性。

只读网络：每科一次 full 查询（不做分片）；不写 DB、不落 catalog。
用法: python tmp_probe_old.py
输出: tmp_probe_old_out.json
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

OLD_SLUGS = [
    "ial-accounting",
    "ial-arabic",
    "ial-englang",
    "ial-englit",
    "ial-french",
    "ial-geography",
    "ial-german",
    "ial-greek",
    "ial-history",
    "ial-law",
    "ial-maths",
    "ial-psychology",
    "ial-spanish",
]


def main() -> None:
    settings = get_settings()
    fetcher = Fetcher(settings)
    out = []
    try:
        for slug in OLD_SLUGS:
            ref = syllabus_ref(slug)
            try:
                adapter = EdexcelAdapter(fetcher)
                tags, tags_source, notes = resolve_tags(adapter, ref)
                try:
                    records = fetch_records(fetcher, tags)
                    kept = keep_qp_ms(dedup_records(records))
                    qp = ms = 0
                    for rec in kept:
                        raw = (
                            category_value(
                                rec.get("category") or [], "Pearson-UK:Document-Type"
                            )
                            or ""
                        ).strip().lower()
                        if raw == "question-paper":
                            qp += 1
                        elif raw == "mark-scheme":
                            ms += 1
                    rec_out = {
                        "slug": slug,
                        "tags_source": tags_source,
                        "query": "full",
                        "records_total": len(records),
                        "kept_qp_ms": len(kept),
                        "qp": qp,
                        "ms": ms,
                        "notes": notes[:3],
                    }
                except ShardExhausted as exc:
                    rec_out = {
                        "slug": slug,
                        "tags_source": tags_source,
                        "query": "full",
                        "shard_exhausted": True,
                        "detail": str(exc)[:200],
                        "notes": notes[:3],
                    }
            except Exception as exc:
                rec_out = {"slug": slug, "error": f"{type(exc).__name__}: {str(exc)[:300]}"}
            out.append(rec_out)
            print(json.dumps(rec_out, ensure_ascii=False), flush=True)
    finally:
        fetcher.close()
    with open("tmp_probe_old_out.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print("written tmp_probe_old_out.json", flush=True)


if __name__ == "__main__":
    main()
