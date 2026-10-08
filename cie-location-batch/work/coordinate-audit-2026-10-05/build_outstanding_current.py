"""按当前索引重算「未完成清单」（机器可读 + CSV），不使用旧 pending-work 数字。

输入（全部为本次实测产物）：
  deliverables/ms-row-audit.json              当前 63 卷的行-区域审计
  deliverables/empty-ms-classify-v4.json      当前空 MS 分类
  deliverables/empty-ms-verdicts.json         空 MS 旁侧验收日志（含理由）
  ms-region-fixes-generic-log.json            77 条补建的 overlap 警告
  row-without-region-fix-log.json             跨页续页修复
输出：
  deliverables/outstanding-current.json
  deliverables/outstanding-current.csv
"""
import csv
import json
import os
from collections import Counter, defaultdict
from datetime import datetime

A = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(A, "deliverables")

# 已知需在后续流程中处理的项（本轮未做，如实登记）
DEFERRED = [
    {"key": "0495/2026/Jun/11", "kind": "row_without_region_deferred",
     "detail": "ms p23 有真实题号行 1(e)（显示 bbox [77.7,102.1,99.0,113.7]）无任何 ms 区域覆盖；"
               "该卷 s08 已有 49 条记录绑定当前 index_sha256 6ba6291b5ef3，"
               "现在改动会使它们失效 → 推迟到 s09 后半片核验完成后一并补建并重绑 sha",
     "evidence": "deliverables/ms-row-audit.json → 0495/2026/Jun/11 findings[row_without_region]",
     "status": "not_run"},
]


def main():
    audit = json.loads(open(os.path.join(D, "ms-row-audit.json"), encoding="utf-8").read())
    cls = json.loads(open(os.path.join(D, "empty-ms-classify-v4.json"), encoding="utf-8").read())
    verdicts = json.loads(open(os.path.join(D, "empty-ms-verdicts.json"), encoding="utf-8").read())
    gen = json.loads(open(os.path.join(A, "ms-region-fixes-generic-log.json"), encoding="utf-8").read())

    find_counts = Counter()
    per_paper = defaultdict(lambda: defaultdict(int))
    for key, res in audit.items():
        for f in res["findings"]:
            find_counts[f["type"]] += 1
            per_paper[key][f["type"]] += 1

    empty_by_key = {k: len(r["questions_with_empty_ms"])
                    for k, r in audit.items() if r["questions_with_empty_ms"]}

    overlaps = []
    for paper in gen["papers"]:
        for o in paper["overlaps"]:
            overlaps.append({"key": paper["key"], **o})

    reason = {}
    for it in verdicts["items"]:
        if it["action"] and it["action"]["type"] == "manual_review_required":
            reason[(it["key"], it["question"])] = it["action"]["reason"]

    empty_items = []
    for it in cls["items"]:
        empty_items.append({
            "key": it["key"], "question": it["q"], "class": it["class"],
            "reason": reason.get((it["key"], it["q"])),
            "evidence": it.get("evidence"),
            "status": "not_run（待视觉核验原件）"})

    rows = []
    for it in empty_items:
        rows.append({"category": "empty_ms_manual", "key": it["key"], "question": it["question"],
                     "detail": it["class"], "status": "not_run"})
    for o in overlaps:
        rows.append({"category": "region_overlap_needs_visual", "key": o["key"], "question": o["q"],
                     "detail": f"新增区域与 {o['other']} 已有区域重叠 {o['overlap_pt']}pt (p{o['page']})",
                     "status": "not_run"})
    for key, c in sorted(per_paper.items()):
        for t, n in sorted(c.items()):
            rows.append({"category": f"audit:{t}", "key": key, "question": "",
                         "detail": f"{n} 条", "status": "not_run"})
    for d in DEFERRED:
        rows.append({"category": d["kind"], "key": d["key"], "question": "1(e)",
                     "detail": d["detail"], "status": d["status"]})

    out = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "basis": "本次实测：deliverables/ms-row-audit.json（63 卷）、empty-ms-classify-v4.json、"
                 "empty-ms-verdicts.json、ms-region-fixes-generic-log.json",
        "empty_ms_current": {"total": sum(empty_by_key.values()), "keys": empty_by_key,
                             "by_class": cls["totals"]},
        "audit_findings_current": dict(find_counts),
        "audit_findings_by_paper": {k: dict(v) for k, v in sorted(per_paper.items())},
        "overlaps_from_this_round": overlaps,
        "empty_ms_items": empty_items,
        "deferred": DEFERRED,
        "csv_rows": rows,
    }
    open(os.path.join(D, "outstanding-current.json"), "w", encoding="utf-8").write(
        json.dumps(out, ensure_ascii=False, indent=1))
    with open(os.path.join(D, "outstanding-current.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["category", "key", "question", "detail", "status"])
        w.writeheader()
        w.writerows(rows)
    print("empty_ms", out["empty_ms_current"]["total"], "keys", len(empty_by_key))
    print("findings", dict(find_counts))
    print("overlaps", len(overlaps), "rows", len(rows))
    print("->", os.path.join(D, "outstanding-current.json"))


if __name__ == "__main__":
    main()
