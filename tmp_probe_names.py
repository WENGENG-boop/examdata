"""临时：采样 13 个 legacy IAL 科目资源文件名 → 推导 (paper_code, unit_code)。

只读网络；不写 DB、不落 catalog。输出 tmp_probe_names_out.json。
用法: python tmp_probe_names.py
"""
import json
import sys

sys.path.insert(0, "src")

from examdata.adapters.edexcel.adapter import EdexcelAdapter
from examdata.adapters.edexcel.servlet import ShardExhausted
from examdata.core.config import get_settings
from examdata.core.fetch import Fetcher
from examdata.edexcel_papers.enumerate import (
    dedup_records,
    keep_qp_ms,
    query_records,
    resolve_tags,
    syllabus_ref,
)
from examdata.edexcel_papers.pipeline import derive_paper_code

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

SAMPLE_PER_SUBJECT = 12


def main() -> None:
    settings = get_settings()
    fetcher = Fetcher(settings)
    out = []
    try:
        for slug in OLD_SLUGS:
            ref = syllabus_ref(slug)
            adapter = EdexcelAdapter(fetcher)
            tags, tags_source, notes = resolve_tags(adapter, ref)
            try:
                records, mode = query_records(fetcher, tags, label=slug)
            except ShardExhausted as exc:
                out.append(
                    {"slug": slug, "shard_exhausted": True, "detail": str(exc)[:200]}
                )
                print(json.dumps(out[-1], ensure_ascii=False), flush=True)
                continue
            kept = keep_qp_ms(dedup_records(records))
            units: dict[str, int] = {}
            samples: list[dict[str, object]] = []
            for rec in kept:
                res = adapter.build_resource(rec, ref, ref.attrs["subject_page_url"])
                if res is None:
                    continue
                url = res.url or ""
                pc, uc = derive_paper_code(url)
                key = uc or "?"
                units[key] = units.get(key, 0) + 1
                if len(samples) < SAMPLE_PER_SUBJECT:
                    samples.append(
                        {
                            "file": url.rsplit("/", 1)[-1],
                            "paper_code": pc,
                            "unit_code": uc,
                            "doc_type": res.doc_type,
                        }
                    )
            rec_out = {
                "slug": slug,
                "mode": mode,
                "kept": len(kept),
                "units": dict(sorted(units.items())),
                "samples": samples,
            }
            out.append(rec_out)
            print(
                json.dumps(
                    {
                        "slug": slug,
                        "mode": mode,
                        "kept": len(kept),
                        "units": rec_out["units"],
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
    finally:
        fetcher.close()
    with open("tmp_probe_names_out.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print("written tmp_probe_names_out.json", flush=True)


if __name__ == "__main__":
    main()
