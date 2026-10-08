"""Rebuild the 9709/2024/Jun/11 index ms regions from the rule-snapped MS row bands.

Inputs:
- indexes/9709/2024-Jun-11/cie-index.json  (current, strips already removed)
- work/proposals/9709/2024-Jun-11.json     (ms_candidates, unrotated PDF points)

Rule:
- sub questions get their own label band (1(a), 1(b), ...);
- top-level questions get the per-page union of their children bands;
- questions 9 and 10 have their own labels and use them directly;
- label candidates on pages < 6 are ignored (no MS table header there).

Also rewrites notes/uncertain to the final form (OCR provenance + MS mapping
description) and writes a backup before saving. Prints sha before/after.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BATCH = HERE.parent
sys.path.insert(0, str(BATCH / "tools"))
import batchlib as B  # noqa: E402

KEY = "9709/2024/Jun/11"
SUBJECT, YEAR, SEASON, PAPER = KEY.split("/")
INDEX = BATCH / "indexes" / SUBJECT / f"{YEAR}-{SEASON}-{PAPER}" / "cie-index.json"
PROPOSAL = BATCH / "work" / "proposals" / SUBJECT / f"{YEAR}-{SEASON}-{PAPER}.json"
BACKUP_DIR = BATCH / "work" / "index-backups"
BACKUP = BACKUP_DIR / "9709-2024-Jun-11-before-ms-rebuild.json"

OCR_NOTE = "text 来自 Windows.Media.Ocr(zh-Hans-CN) 转录，可能有识别噪声"


def main() -> int:
    index = json.loads(INDEX.read_bytes().decode("utf-8"))
    proposal = json.loads(PROPOSAL.read_bytes().decode("utf-8"))

    bands: dict[str, list[dict]] = {}
    for cand in proposal["ms_candidates"]:
        if cand["page"] < 6:
            continue
        label = cand["label"]
        x0, y0, x1, y1 = cand["row_bbox"]
        bands.setdefault(label, []).append(
            {"page": int(cand["page"]), "bbox": [x0, y0, x1, y1]})

    def union(regions: list[dict]) -> list[dict]:
        by_page: dict[int, list[float]] = {}
        for r in regions:
            box = by_page.get(r["page"])
            if box is None:
                by_page[r["page"]] = list(r["bbox"])
            else:
                box[0] = min(box[0], r["bbox"][0])
                box[1] = min(box[1], r["bbox"][1])
                box[2] = max(box[2], r["bbox"][2])
                box[3] = max(box[3], r["bbox"][3])
        return [{"page": p, "bbox": by_page[p]} for p in sorted(by_page)]

    questions = index["questions"]
    children: dict[str, list[str]] = {}
    for q in questions:
        if q.get("parent"):
            children.setdefault(q["parent"], []).append(q["question"])

    report = []
    for q in questions:
        name = q["question"]
        direct = bands.get(name)
        if direct:
            ms = [dict(r) for r in direct]
            source = "direct"
        elif name in children:
            kid_regions = [r for kid in children[name] for r in bands.get(kid, [])]
            ms = union(kid_regions)
            source = "union"
        else:
            ms = []
            source = "none"
        q["ms"] = ms

        if q.get("parent"):
            base = f"{OCR_NOTE}（说明继承自父题 {q['parent']}）"
        else:
            base = OCR_NOTE
        if source == "direct":
            note = base + "；MS 该题评分行已按评分表规则带定位"
        elif source == "union":
            note = base + "；MS 区域为本题各子题评分行并集"
        else:
            note = base + "；MS 中未找到对应评分行，请复核定位"
        q["notes"] = note
        q["uncertain"] = source == "none"
        report.append((name, source, len(ms)))

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    if not BACKUP.exists():
        shutil.copy2(INDEX, BACKUP)
    sha_before = B.sha256_file(INDEX)
    B.atomic_write_json(INDEX, index)
    sha_after = B.sha256_file(INDEX)

    for name, source, n in report:
        print(f"  {name:6s} {source:6s} regions={n}")
    print(json.dumps({"sha_before": sha_before, "sha_after": sha_after,
                      "backup": str(BACKUP)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
