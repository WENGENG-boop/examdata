"""构建"可恢复的逐卷重验队列"（纯离线只读）。

输入:
  deliverables/per-paper-inventory.json      逐卷 gate/verification 统计
  deliverables/empty-ms-classification.json  空 MS 逐条分类
输出:
  deliverables/reverify-queue.json           逐卷待办（含优先级与原件是否在本地）
  deliverables/outstanding-by-paper.csv      人读清单
"""
from __future__ import annotations

import csv
import glob
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BATCH = r"C:/Users/weo/Desktop/api/cie-location-batch"
AUD = os.path.join(BATCH, "work", "coordinate-audit-2026-10-05")
DELIV = os.path.join(AUD, "deliverables")

STAGE_PROBLEM_PREFIX = "stage 不是"


def originals(key: str) -> dict:
    subj, year, season, paper = key.split("/")
    d = os.path.join(BATCH, "tmp", subj, f"{year}-{season}-{paper}")
    out = {"dir": d, "qp": None, "ms": None}
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            low = f.lower()
            if not low.endswith(".pdf"):
                continue
            if "_qp_" in low:
                out["qp"] = f
            elif "_ms_" in low:
                out["ms"] = f
    return out


def main() -> int:
    inv = json.load(open(os.path.join(DELIV, "per-paper-inventory.json"), encoding="utf-8"))
    ems = json.load(open(os.path.join(DELIV, "empty-ms-classification.json"), encoding="utf-8"))
    ems_by_paper: dict[str, list[dict]] = {}
    for r in ems["records"]:
        ems_by_paper.setdefault(r["paper"], []).append(r)

    queue = []
    for p in inv["papers"]:
        key = p["key"]
        v = p.get("gate_info") or {}
        regions = v.get("regions") or 0
        vis_missing = v.get("visual_evidence_missing") or 0
        missing = v.get("missing") or 0
        selfdecl = v.get("self_declared_unverified") or 0
        ems_list = p.get("empty_ms") or []
        unc = p.get("uncertain") or []
        orig = originals(key)
        other_problems = [x for x in p["gate_problems"] if not x.startswith(STAGE_PROBLEM_PREFIX)]
        needs_visual = (vis_missing + missing) > 0
        needs_ems = len(ems_list) > 0
        needs_unc = len(unc) > 0
        outstanding = needs_visual or needs_ems or needs_unc or bool(other_problems)
        cat_counts: dict[str, int] = {}
        for r in ems_by_paper.get(key, []):
            cat_counts[r["category"]] = cat_counts.get(r["category"], 0) + 1
        queue.append({
            "key": key,
            "papers_stage": p["papers_stage"],
            "index_sha256": p["index_sha256"],
            "regions": regions,
            "regions_with_visual_evidence": regions - vis_missing,
            "regions_missing_evidence": vis_missing,
            "regions_without_record": missing,
            "self_declared_unverified": selfdecl,
            "questions": p["questions"],
            "empty_ms_count": len(ems_list),
            "empty_ms_questions": ems_list,
            "empty_ms_categories": cat_counts,
            "uncertain_count": len(unc),
            "uncertain_questions": unc,
            "other_gate_problems": other_problems,
            "outstanding": outstanding,
            "originals": orig,
            "originals_present": bool(orig["qp"]) and bool(orig["ms"]),
        })
    queue.sort(key=lambda r: (not r["outstanding"], -r["regions_missing_evidence"]))
    with open(os.path.join(DELIV, "reverify-queue.json"), "w", encoding="utf-8") as fh:
        json.dump({"generated_at": __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds"),
                   "queue": queue}, fh, ensure_ascii=False, indent=1)

    with open(os.path.join(DELIV, "outstanding-by-paper.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["key", "stage", "regions", "regions_with_evidence", "regions_missing_evidence",
                    "regions_without_record", "empty_ms", "uncertain", "originals_present",
                    "other_gate_problems", "empty_ms_categories"])
        for r in queue:
            w.writerow([r["key"], r["papers_stage"], r["regions"], r["regions_with_visual_evidence"],
                        r["regions_missing_evidence"], r["regions_without_record"], r["empty_ms_count"],
                        r["uncertain_count"], r["originals_present"],
                        " | ".join(r["other_gate_problems"])[:200],
                        json.dumps(r["empty_ms_categories"], ensure_ascii=False)])
    todo = [r for r in queue if r["outstanding"]]
    print("卷总数:", len(queue), " 有待办:", len(todo), " 已完成:", len(queue) - len(todo))
    print("待重验区域总数:", sum(r["regions_missing_evidence"] + r["regions_without_record"] for r in todo))
    print()
    print("%-22s %-9s %5s %5s %5s %5s %5s %s" % ("key", "stage", "reg", "miss", "ems", "unc", "orig", "problems"))
    for r in todo:
        print("%-22s %-9s %5d %5d %5d %5d %5s %s" % (
            r["key"], r["papers_stage"], r["regions"],
            r["regions_missing_evidence"] + r["regions_without_record"],
            r["empty_ms_count"], r["uncertain_count"],
            "Y" if r["originals_present"] else "N",
            " | ".join(r["other_gate_problems"])[:90]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
