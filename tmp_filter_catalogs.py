"""临时：过滤 13 个 legacy IAL catalog。

规则（先命中先判定）：
1. 丢弃 .zip（听力音频打包）。
2. 保留：文件名推导 unit 匹配 ``W[A-Z]{2,4}\\d{2}`` / ``YLA\\d``（IAL unit 码）。
3. 保留：url 位于 IAL 专属目录（"International Advanced Level" /
   "international-advanced-level"，归一化连字符后匹配）。
4. 保留：显式白名单子串（无标准 unit 码的 June 2018 口语 QP 等）。
5. 其余 → 丢弃（英国 GCE 卷）。

dry-run 默认，只输出统计与排除清单；--write 才写回（先备份 <slug>.json.unfiltered）。
用法: python tmp_filter_catalogs.py [--write]
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, "src")

from examdata.edexcel_papers.pipeline import derive_paper_code

CATALOG_DIR = Path(".data/edexcel_papers/catalog")

SLUGS = [
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

IAL_TOKEN_RE = re.compile(r"W[A-Z]{2,4}\d{2}|YLA\d")

# 白名单：url 或 label 含以下子串则保留（无 IAL unit 码的口语 QP / 个别旧卷）
KEEP_SUBSTRINGS = [
    "Spoken Expression and Response",
    "unit-1-spoken-expression-and-response",
    "question-paper-teacher-examiner-version",
    "Question Paper-Paper-1-June-2016",
]


def classify(res: dict) -> tuple[bool, str]:
    url = res.get("url") or ""
    label = res.get("label") or ""
    cats = res.get("evidence", {}).get("categories") or []
    cats_blob = " ".join(str(c) for c in cats)

    if url.lower().endswith(".zip"):
        return False, "zip"

    _, unit = derive_paper_code(url)
    if unit and IAL_TOKEN_RE.search(unit):
        return True, f"unit:{unit}"

    # IAL 专属目录（"International Advanced Level" / "international-advanced-level"）
    norm = url.lower().replace("-", " ").replace("_", " ")
    if "international advanced level" in norm:
        return True, "ial-folder"

    for sub in KEEP_SUBSTRINGS:
        if sub in url or sub in label:
            return True, "whitelist"

    blob = f"{url} {label} {cats_blob}"
    m = IAL_TOKEN_RE.search(blob)
    if m:
        return True, f"token:{m.group(0)}"

    return False, f"uk-gce(unit={unit})"


def recount(counts: dict, kept: list[dict]) -> dict:
    qp = sum(1 for r in kept if r.get("doc_type") == "question_paper")
    ms = sum(1 for r in kept if r.get("doc_type") == "mark_scheme")
    gated = sum(1 for r in kept if (r.get("meta") or {}).get("is_gated"))
    out = dict(counts)
    out["records"] = len(kept)
    out["resources"] = len(kept)
    out["question_papers"] = qp
    out["mark_schemes"] = ms
    out["gated"] = gated
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    excluded: list[dict] = []
    summary: list[dict] = []

    for slug in SLUGS:
        path = CATALOG_DIR / f"{slug}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        resources = data.get("resources", [])
        kept: list[dict] = []
        drops: list[dict] = []
        for res in resources:
            ok, reason = classify(res)
            if ok:
                kept.append(res)
            else:
                drops.append(
                    {
                        "slug": slug,
                        "url": res.get("url"),
                        "label": res.get("label"),
                        "doc_type": res.get("doc_type"),
                        "reason": reason,
                    }
                )

        # 排除清单里 zip 与 gce 分开统计
        zip_drops = sum(1 for d in drops if d["reason"] == "zip")
        gce_drops = len(drops) - zip_drops
        summary.append(
            {
                "slug": slug,
                "total": len(resources),
                "kept": len(kept),
                "dropped": len(drops),
                "zip": zip_drops,
                "gce": gce_drops,
                "old_counts": data.get("counts"),
                "new_counts": recount(data.get("counts") or {}, kept),
            }
        )
        excluded.extend(drops)

        if args.write:
            backup = path.with_suffix(".json.unfiltered")
            if not backup.exists():
                backup.write_text(
                    json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8"
                )
            data["resources"] = kept
            data["counts"] = recount(data.get("counts") or {}, kept)
            notes = data.get("notes")
            note = (
                f"filtered 2026-10-03: dropped {len(drops)} "
                f"(zip={zip_drops}, uk-gce={gce_drops})"
            )
            if isinstance(notes, list):
                notes.append(note)
            else:
                data["notes"] = [note]
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8"
            )

    Path("tmp_filter_excluded.json").write_text(
        json.dumps(excluded, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    Path("tmp_filter_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    total_kept = sum(s["kept"] for s in summary)
    total_dropped = sum(s["dropped"] for s in summary)
    print(f"{'slug':<16}{'total':>6}{'kept':>6}{'dropped':>8}{'zip':>5}{'gce':>6}")
    for s in summary:
        print(
            f"{s['slug']:<16}{s['total']:>6}{s['kept']:>6}{s['dropped']:>8}"
            f"{s['zip']:>5}{s['gce']:>6}"
        )
    print(f"{'TOTAL':<16}{'':>6}{total_kept:>6}{total_dropped:>8}")
    print(f"excluded -> tmp_filter_excluded.json ({len(excluded)} rows)")
    print("mode:", "WRITE" if args.write else "dry-run")


if __name__ == "__main__":
    main()
