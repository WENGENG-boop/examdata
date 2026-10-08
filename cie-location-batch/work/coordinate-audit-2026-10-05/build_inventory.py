"""生成"每卷每题未完成清单"与机器可读统计（纯离线只读，不访问上游）。

用法: python build_inventory.py
输出:
  deliverables/per-paper-inventory.json   63 卷逐卷汇总（含 gate 条件、空 MS/uncertain 题号）
  deliverables/outstanding-summary.json   全局分子/分母与分类计数
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import sys
from collections import Counter

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BATCH = r"C:/Users/weo/Desktop/api/cie-location-batch"
AUD = os.path.join(BATCH, "work", "coordinate-audit-2026-10-05")
DELIV = os.path.join(AUD, "deliverables")
sys.path.insert(0, os.path.join(BATCH, "tools"))

import batchlib as B  # noqa: E402
import cleanup_paper as C  # noqa: E402


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    index_files = sorted(glob.glob(os.path.join(BATCH, "indexes", "*", "*", "cie-index.json")))
    papers = json.load(open(os.path.join(BATCH, "papers.json"), encoding="utf-8"))
    rows = []
    totals = Counter()
    for f in index_files:
        subj, folder = os.path.relpath(f, os.path.join(BATCH, "indexes")).replace("\\", "/").split("/")[:2]
        key = f"{subj}/{folder.replace('-', '/')}"
        idx = json.load(open(f, encoding="utf-8"))
        qs = idx.get("questions", [])
        empty_ms = [q["question"] for q in qs if not q.get("ms")]
        empty_qp = [q["question"] for q in qs if not q.get("qp")]
        unc = [q["question"] for q in qs if q.get("uncertain")]
        try:
            problems, info = C.check_conditions(key)
        except Exception as exc:  # noqa: BLE001
            problems, info = [f"check_conditions 异常: {type(exc).__name__}: {exc}"], {}
        ver = (info or {}).get("verification", {}) or {}
        entry = papers.get(key) or {}
        stage_problems = [p for p in problems if p.startswith("stage 不是")]
        content_problems = [p for p in problems if not p.startswith("stage 不是")]
        regions = int(ver.get("regions") or 0)
        vis_missing = int(ver.get("visual_evidence_missing") or 0)
        self_unver = int(ver.get("self_declared_unverified") or 0)
        missing_rec = int(ver.get("missing") or 0)
        evidence_complete = (regions > 0 and vis_missing == 0 and self_unver == 0
                             and missing_rec == 0)
        rows.append({
            "key": key,
            "index_path": f.replace("\\", "/"),
            "index_sha256": sha256_file(f),
            "papers_stage": entry.get("stage"),
            "kind": entry.get("kind"),
            "questions": len(qs),
            "qp_regions": sum(len(q.get("qp") or []) for q in qs),
            "ms_regions": sum(len(q.get("ms") or []) for q in qs),
            "empty_ms": empty_ms,
            "empty_qp": empty_qp,
            "uncertain": unc,
            "gate_pass": not problems,
            "gate_problems": problems,
            "stage_problems": stage_problems,
            "content_problems": content_problems,
            "regions_registered": regions,
            "regions_without_record": missing_rec,
            "regions_without_visual_evidence": vis_missing,
            "self_declared_unverified": self_unver,
            "evidence_complete": evidence_complete,
            "outstanding": bool(content_problems) or not evidence_complete,
            "gate_info": ver,
        })
        totals["papers"] += 1
        totals["questions"] += len(qs)
        totals["empty_ms"] += len(empty_ms)
        totals["empty_qp"] += len(empty_qp)
        totals["uncertain"] += len(unc)
        totals["gate_pass"] += 1 if not problems else 0
        totals["gate_fail"] += 0 if not problems else 1
        totals["content_pass"] += 1 if not content_problems else 0
        totals["evidence_complete"] += 1 if evidence_complete else 0
        totals["outstanding"] += 1 if (content_problems or not evidence_complete) else 0
        totals["regions_registered"] += regions
        totals["regions_without_record"] += missing_rec
        totals["regions_without_visual_evidence"] += vis_missing
        totals["self_declared_unverified"] += self_unver
        if entry.get("stage") == "cleaned":
            totals["stage_cleaned"] += 1
        if entry.get("stage") == "cleaned" and (content_problems or not evidence_complete):
            totals["cleaned_but_outstanding"] += 1
    os.makedirs(DELIV, exist_ok=True)
    with open(os.path.join(DELIV, "per-paper-inventory.json"), "w", encoding="utf-8") as fh:
        json.dump({"generated_at": B.now_iso(), "papers": rows}, fh, ensure_ascii=False, indent=1)
    summary = {
        "generated_at": B.now_iso(),
        "totals": dict(totals),
        "totals_display": {
            "发现卷": 13877,
            "有永久索引卷": totals["papers"],
            "无索引卷": 13877 - totals["papers"],
            "题目记录": totals["questions"],
            "空 MS 记录": totals["empty_ms"],
            "空 QP 记录": totals["empty_qp"],
            "uncertain 记录": totals["uncertain"],
            "gate 通过卷": totals["gate_pass"],
            "gate 未通过卷": totals["gate_fail"],
        },
        "stage_counts": dict(Counter(r["papers_stage"] for r in rows)),
        "gate_fail_list": [{"key": r["key"], "problems": r["gate_problems"]} for r in rows if not r["gate_pass"]],
        "outstanding_list": [
            {"key": r["key"], "stage": r["papers_stage"],
             "content_problems": r["content_problems"],
             "regions_registered": r["regions_registered"],
             "regions_without_record": r["regions_without_record"],
             "regions_without_visual_evidence": r["regions_without_visual_evidence"],
             "self_declared_unverified": r["self_declared_unverified"],
             "empty_ms": len(r["empty_ms"]), "uncertain": len(r["uncertain"])}
            for r in rows if r["outstanding"]],
    }
    with open(os.path.join(DELIV, "outstanding-summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1)
    print(json.dumps(summary["totals_display"], ensure_ascii=False, indent=1))
    print("stages:", json.dumps(summary["stage_counts"], ensure_ascii=False))
    print("gate_fail:", len(summary["gate_fail_list"]))
    for item in summary["gate_fail_list"][:40]:
        print("   ", item["key"], "|", "; ".join(item["problems"])[:150])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
