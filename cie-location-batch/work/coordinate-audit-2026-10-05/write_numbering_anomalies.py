"""题号异常卷的精确刻画（纯离线，读本地索引，不访问上游）。

GOAL-SPEC §3 要求对下列卷逐页核对原件判定「真实缺题 or 合法编号例外」：
  8386/2025/Jun/11、8386/2026/Jun/12、8386/2026/Jun/13（缺顶层题号 1）
  0495/2026/Jun/11（2(a)、3(a) 的子子题只出现 (ii)）

本会话无图像输入能力，且这些卷的原件已被清理，无法逐页目视。此脚本只做能做的：
把索引里实际存在的题目/父子/区域结构完整导出，并复算 numbering_problems，
供有原件时逐条对号；不推断「真实缺题」，不修改任何索引。

输出：deliverables/numbering-anomalies.json
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

ROOT = r"C:/Users/weo/Desktop/api"
BATCH = os.path.join(ROOT, "cie-location-batch")
sys.path.insert(0, os.path.join(BATCH, "tools"))

import cleanup_paper as C  # noqa: E402

OUT = os.path.join(BATCH, "work/coordinate-audit-2026-10-05/deliverables")
TARGETS = [
    ("8386", "2025-Jun-11"),
    ("8386", "2026-Jun-12"),
    ("8386", "2026-Jun-13"),
    ("0495", "2026-Jun-11"),
]


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    import datetime
    os.makedirs(OUT, exist_ok=True)
    entries = []
    for subject, stem in TARGETS:
        path = os.path.join(BATCH, "indexes", subject, stem, "cie-index.json")
        if not os.path.isfile(path):
            entries.append({"key": f"{subject}/{stem}", "index_found": False})
            continue
        index = json.load(open(path, encoding="utf-8"))
        ident = index["identity"]
        key = "/".join(str(ident[k]) for k in ("subject", "year", "season", "paper"))
        questions = index["questions"]
        problems, _num_stats = C.numbering_problems(key)
        docs = {d["role"]: d.get("sha256") for d in index["documents"]}
        qp_pages = sorted({r["page"] for q in questions for r in (q.get("qp") or [])})
        ms_pages = sorted({r["page"] for q in questions for r in (q.get("ms") or [])})
        tops = [int(q["question"]) for q in questions
                if not q.get("parent") and str(q["question"]).isdigit()]
        gaps = sorted(set(range(1, max(tops) + 1)) - set(tops)) if tops else []
        entries.append({
            "key": key,
            "index_found": True,
            "index_path": path.replace("\\", "/"),
            "index_sha256": sha256_file(path),
            "qp_sha256": docs.get("qp"),
            "ms_sha256": docs.get("ms"),
            "documents_roles": [d["role"] for d in index["documents"]],
            "question_count": len(questions),
            "top_level_questions": sorted(tops),
            "top_level_missing": gaps,
            "qp_page_coverage": qp_pages,
            "ms_page_coverage": ms_pages,
            "qp_pages_uncovered_before_first_indexed":
                (min(qp_pages) - 1) if qp_pages else None,
            "coverage_note": (
                "QP 索引区域最早出现在第 "
                + (str(min(qp_pages)) if qp_pages else "-")
                + " 页；此前页面无任何 QP 区域，可能含封面/说明/共享材料或未被索引的题，需原件确认。"
            ),
            "numbering_problems": problems,
            "questions": [{
                "question": q["question"], "parent": q.get("parent"),
                "marks": q.get("marks"), "uncertain": q.get("uncertain"),
                "qp_pages": sorted({r["page"] for r in (q.get("qp") or [])}),
                "ms_pages": sorted({r["page"] for r in (q.get("ms") or [])}),
                "qp_regions": len(q.get("qp") or []),
                "ms_regions": len(q.get("ms") or []),
            } for q in questions],
            "verification": C.verification_state(key, [q["question"] for q in questions])[1],
            "status": "pending_original_refetch",
            "blocked_by": "原件已清理 + 本会话无图像输入能力，无法逐页目视判定真实缺题/合法例外",
        })
    payload = {
        "generated_at": datetime.datetime.now().astimezone()
            .replace(microsecond=0).isoformat(),
        "note": "只刻画索引中实际存在的结构，不判定真实缺题；需原件逐页目视才能定论。",
        "source": "本次实测（本地索引结构）",
        "entries": entries,
    }
    tmp = os.path.join(OUT, "numbering-anomalies.json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, os.path.join(OUT, "numbering-anomalies.json"))
    for e in entries:
        print(e.get("key"), "found" if e["index_found"] else "MISSING",
              "problems=", e.get("numbering_problems"), "n=", e.get("question_count"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
