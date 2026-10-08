"""汇总 edexcel_live_pages_recovery.json：各状态计数、材料命中、缺口清单。

只读本地 JSON，输出 evidence/edexcel_recovery_summary.json（供报告与 build 使用）。
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

EV = Path(r"C:/Users/weo/Desktop/api/tmp_materials_probe/evidence")


def summarise(entries: dict) -> dict:
    st = Counter(v.get("status") for v in entries.values())
    mat_counts = {k: len(v.get("materials") or []) for k, v in entries.items() if v.get("materials")}
    total_mat = sum(mat_counts.values())
    capped = [k for k, v in entries.items() if v.get("capped")]
    no_record = [k for k, v in entries.items() if v.get("status") == "no_page_record"]
    no_facet = [k for k, v in entries.items() if v.get("status") == "record_no_usable_facet"]
    match = Counter(v.get("match") for v in entries.values())
    return {
        "n": len(entries),
        "status": dict(st),
        "match": dict(match),
        "with_materials": len(mat_counts),
        "material_rows_total": total_mat,
        "material_rows_top": dict(sorted(mat_counts.items(), key=lambda kv: -kv[1])[:15]),
        "capped_in_recovery": capped,
        "no_page_record": no_record,
        "record_no_usable_facet": no_facet,
    }


def main() -> None:
    d = json.loads((EV / "edexcel_live_pages_recovery.json").read_text(encoding="utf-8"))
    live = summarise(d["live"])
    dead = summarise(d["dead"])

    # 跨 live/dead 的唯一材料 URL 汇总
    urls: dict[str, dict] = {}
    for sec in ("live", "dead"):
        for slug, v in d[sec].items():
            for m in v.get("materials") or []:
                u = str(m.get("url") or "")
                if u and u not in urls:
                    urls[u] = {"slug": slug, "sec": sec, "title": m.get("title"), "gated": m.get("gated"), "doc_type": m.get("doc_type")}
    gated_n = sum(1 for m in urls.values() if m.get("gated"))
    gated_tags = sorted({m.get("doc_type") or "(none)" for m in urls.values() if m.get("gated")})

    out = {
        "source": "edexcel_live_pages_recovery.json",
        "live": live,
        "dead": dead,
        "unique_material_urls": len(urls),
        "unique_gated_urls": gated_n,
        "gated_doc_types": gated_tags,
        "fam_meta": d.get("fam_meta"),
        "capped_records_status": {k: v.get("status") for k, v in (d.get("capped_records") or {}).items()},
    }
    (EV / "edexcel_recovery_summary.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(json.dumps({k: out[k] for k in ("live", "dead", "unique_material_urls", "unique_gated_urls")}, ensure_ascii=False, indent=1))
    print("capped_records_status:", out["capped_records_status"])
    print("gated_doc_types:", gated_tags)


if __name__ == "__main__":
    main()
