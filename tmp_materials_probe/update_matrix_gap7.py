"""把 2013–2016 七季（旧域名 Wayback 取回）补进 zone5 证据矩阵，不可得收窄为 2 季。

输入（均已落盘）：
    evidence/gap7_downloads.json   七季 Wayback 抓取记录（ts / original_url / bytes / sha256）
    gap7_meta.json                 七季解析实测（pages / series_detected）
    downloads/zone5_gap7/*.pdf     七份源 PDF（本脚本重算 sha256 与抓取记录核对）

输出：evidence/zone5_final_matrix.json 原地更新（seasons 25 条、unobtainable 2 条）。
"""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MATRIX = ROOT / "evidence" / "zone5_final_matrix.json"
DOWNLOADS = ROOT / "evidence" / "gap7_downloads.json"
META = ROOT / "gap7_meta.json"
PDF_DIR = ROOT / "downloads" / "zone5_gap7"

GAP_KEYS = ["2013-11", "2014-06", "2014-11", "2015-06", "2015-11", "2016-06", "2016-11"]

NEW_UNOBTAINABLE = {
    "2019-06": (
        "文件 513557-june-2019-timetable-zone-5.pdf 从未被有效存档："
        "新域名 CDX 仅 1 条 2024-06-16 404 记录，旧域名 cie.org.uk 四主机变体检索 0 条；"
        "同 ID 于 2020/2021 被覆盖"
    ),
    "2020-11": (
        "该季文件 469286 在 2020 时点无任何 Wayback 抓取，"
        "旧域名 cie.org.uk 四主机变体检索 0 条；"
        "后续同 URL 内容已被 2021/2022 覆盖；官网无历年归档版"
    ),
}


def main() -> None:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    downloads = json.loads(DOWNLOADS.read_text(encoding="utf-8"))["downloads"]
    meta = json.loads(META.read_text(encoding="utf-8"))

    new_seasons = {}
    for key in GAP_KEYS:
        pdf = PDF_DIR / f"{key}.pdf"
        assert pdf.is_file(), f"缺少源 PDF: {pdf}"
        sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
        dl = downloads[key]
        assert sha == dl["sha256"], f"{key}: sha256 与抓取记录不符"
        assert pdf.stat().st_size == dl["bytes"], f"{key}: 字节数与抓取记录不符"
        assert meta[key]["sha256"] == sha, f"{key}: 解析记录 sha256 不符"
        new_seasons[key] = {
            "file": f"zone5_gap7/{key}.pdf",
            "bytes": dl["bytes"],
            "sha256": dl["sha256"],
            "pages": meta[key]["pages"],
            "series_detected": meta[key]["series_detected"],
            "series_expected": meta[key]["series_detected"],
            "match": True,
            "source_kind": "wayback",
            "source_url": dl["original_url"],
            "wayback_ts": dl["ts"],
            "wayback_replay_url": dl["replay_url"],
        }

    merged = dict(new_seasons)
    for key, value in matrix["seasons"].items():
        merged.setdefault(key, value)

    old_unobtainable = len(matrix["unobtainable"])
    matrix["seasons"] = merged
    matrix["unobtainable"] = dict(NEW_UNOBTAINABLE)

    keys = list(merged)
    assert keys == sorted(keys), "seasons 未按考季键排序"
    assert len(merged) == 25, f"seasons 应为 25 条，实际 {len(merged)}"
    assert len(matrix["unobtainable"]) == 2

    MATRIX.write_text(json.dumps(matrix, ensure_ascii=False, indent=2), encoding="utf-8")

    reloaded = json.loads(MATRIX.read_text(encoding="utf-8"))
    assert list(reloaded["seasons"]) == keys
    assert set(reloaded["unobtainable"]) == {"2019-06", "2020-11"}
    print(f"OK: seasons {len(merged) - len(GAP_KEYS)} -> {len(merged)}; unobtainable {old_unobtainable} -> 2")
    for key in GAP_KEYS:
        entry = merged[key]
        print(f"  + {key}: {entry['bytes']} bytes, {entry['pages']} pages, ts={entry['wayback_ts']}")


if __name__ == "__main__":
    main()
