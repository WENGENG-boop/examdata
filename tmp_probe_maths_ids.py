"""临时：拉取 legacy ial-maths 资源列表，按推导单元分组，打印 title 与 category。

只读网络；不写 DB。输出 tmp_probe_maths_ids_out.json。
用法: python tmp_probe_maths_ids.py
"""
import json
import sys

sys.path.insert(0, "src")

from examdata.adapters.edexcel.adapter import EdexcelAdapter
from examdata.adapters.edexcel.classify import category_value
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


def main() -> None:
    settings = get_settings()
    fetcher = Fetcher(settings)
    try:
        ref = syllabus_ref("ial-maths")
        adapter = EdexcelAdapter(fetcher)
        tags, tags_source, notes = resolve_tags(adapter, ref)
        records, mode = query_records(fetcher, tags, label="ial-maths")
        kept = keep_qp_ms(dedup_records(records))
        print("kept:", len(kept), "mode:", mode)

        groups: dict[str, list[dict]] = {}
        for rec in kept:
            url = rec.get("url") or ""
            pc, uc = derive_paper_code(url)
            key = uc or "?"
            groups.setdefault(key, []).append(
                {
                    "file": url.rsplit("/", 1)[-1],
                    "title": (rec.get("title") or "")[:120],
                    "spec_codes": [
                        v
                        for v in (
                            category_value(rec.get("category") or [], k)
                            for k in (
                                "Pearson-UK:Specification-Code",
                                "Pearson-UK:Specification-Code/subject",
                            )
                        )
                        if v
                    ],
                    "doc_type": category_value(
                        rec.get("category") or [], "Pearson-UK:Document-Type"
                    ),
                    "categories": (rec.get("category") or [])[:14],
                }
            )

        out = {}
        for unit, rows in sorted(groups.items()):
            out[unit] = {"count": len(rows), "samples": rows[:3]}
            print(f"{unit}: {len(rows)}  e.g. {rows[0]['file']} | {rows[0]['title']}")
        with open("tmp_probe_maths_ids_out.json", "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1)
        print("written tmp_probe_maths_ids_out.json", flush=True)
    finally:
        fetcher.close()


if __name__ == "__main__":
    main()
