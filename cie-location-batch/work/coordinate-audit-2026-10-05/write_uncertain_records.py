"""把 uncertain 记录从卷级下钻到题级（纯离线，读本地索引）。

输入：cie-location-batch/indexes/**/cie-index.json（永久索引）
输出：
  deliverables/uncertain-records.jsonl       逐条题级记录
  deliverables/uncertain-records-summary.json 汇总（按卷/按父题/按是否有 MS 区域）

每条记录标注 needs_visual_verification=true：本会话无图像输入能力，无法生成
「实际看过裁剪图」的验收记录，故一律保持 pending_visual，不自动补 true。
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
from collections import Counter

ROOT = r"C:/Users/weo/Desktop/api"
BATCH = os.path.join(ROOT, "cie-location-batch")
OUT = os.path.join(BATCH, "work/coordinate-audit-2026-10-05/deliverables")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def now_iso() -> str:
    import datetime
    return datetime.datetime.now().astimezone().replace(microsecond=0).isoformat()


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    rows = []
    per_paper = Counter()
    per_category = Counter()
    for path in sorted(glob.glob(os.path.join(BATCH, "indexes", "**", "cie-index.json"),
                                recursive=True)):
        index = json.load(open(path, encoding="utf-8"))
        ident = index["identity"]
        key = "/".join(str(ident[k]) for k in ("subject", "year", "season", "paper"))
        index_sha = sha256_file(path)
        docs = {d["role"]: d.get("sha256") for d in index["documents"]}
        questions = index["questions"]
        for q in questions:
            if q.get("uncertain") is not True:
                continue
            qp = q.get("qp") or []
            ms = q.get("ms") or []
            if not ms:
                category = "uncertain_且无MS区域"
            elif len(ms) == 1:
                category = "uncertain_单MS区域"
            else:
                category = "uncertain_多MS区域"
            per_paper[key] += 1
            per_category[category] += 1
            rows.append({
                "key": key,
                "subject": ident["subject"], "year": ident["year"],
                "season": ident["season"], "paper": ident["paper"],
                "question": q["question"], "parent": q.get("parent"),
                "marks": q.get("marks"),
                "qp_region_count": len(qp), "ms_region_count": len(ms),
                "qp_pages": sorted({r["page"] for r in qp}),
                "ms_pages": sorted({r["page"] for r in ms}),
                "notes_present": bool(q.get("notes")),
                "category": category,
                "qp_sha256": docs.get("qp"), "ms_sha256": docs.get("ms"),
                "index_path": path.replace("\\", "/"),
                "index_sha256": index_sha,
                "needs_visual_verification": True,
                "status": "pending_visual",
                "source": "本次实测（当前本地索引 JSON 结构判定）",
            })
    rows.sort(key=lambda r: (r["key"], str(r["question"])))
    with open(os.path.join(OUT, "uncertain-records.jsonl"), "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    summary = {
        "generated_at": now_iso(),
        "total_uncertain_records": len(rows),
        "papers_with_uncertain": len(per_paper),
        "by_category": dict(per_category),
        "by_paper": dict(sorted(per_paper.items())),
        "note": "题级清单；本会话无图像输入能力，无法执行逐区域裁剪目视，全部保持 pending_visual。",
        "source": "本次实测",
    }
    tmp = os.path.join(OUT, "uncertain-records-summary.json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, os.path.join(OUT, "uncertain-records-summary.json"))
    print(json.dumps({k: v for k, v in summary.items()
                      if k not in ("by_paper",)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
