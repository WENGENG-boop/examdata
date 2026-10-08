# -*- coding: utf-8 -*-
"""0472/2026/Jun/21: apply agreed fixes to cie-index.json (P3 of the re-verification plan).

Fixes (from visual re-check 2026-10-04, MS text-layer verified via pymupdf):
- drop 3 pseudo ms header regions "Question Answer Marks Guidance":
    Q3   p7 [76.4, 64.8, 530.4, 87.6]
    3(g) p7 [76.4, 64.8, 530.4, 87.6]
    Q5   p8 [76.4, 64.8, 534.0, 87.6]
  (all three clip-verified to contain only the table header row; the paper's
   convention everywhere else excludes header rows, e.g. Q4 starts at 87.6)
- Q5 ms p7 region y1: 759.6 -> 582.0 (over-extension into blank space + page
  footer "Page 7 of 8" at y749.3; table bottom border is y581.0)

Backup -> work/0472-2026-Jun-21-index-before-fix.json (first backup preserved)
Report -> work/0472-2026-Jun-21-fix-report.json
Atomic replace; prints old/new sha256.
"""
import hashlib
import json
import os
from pathlib import Path

BR = Path(r"C:/Users/weo/Desktop/api/cie-location-batch")
IDX = BR / "indexes/0472/2026-Jun-21/cie-index.json"
BACKUP = BR / "work/0472-2026-Jun-21-index-before-fix.json"
REPORT = BR / "work/0472-2026-Jun-21-fix-report.json"

PSEUDO_P7 = [76.4, 64.8, 530.4, 87.6]
PSEUDO_P8 = [76.4, 64.8, 534.0, 87.6]
Q5_MS_P7 = [76.4, 471.2, 530.4, 759.6]
Q5_MS_P7_NEW = [76.4, 471.2, 530.4, 582.0]


def main():
    old_sha = hashlib.sha256(IDX.read_bytes()).hexdigest()
    index = json.loads(IDX.read_text(encoding="utf-8"))
    changes = []

    def rec(msg):
        changes.append(msg)
        print(msg)

    if not BACKUP.exists():
        BACKUP.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        rec(f"backup written: {BACKUP.name}")
    else:
        rec(f"backup already exists, kept: {BACKUP.name}")

    # --- 1. drop pseudo ms header regions ------------------------------
    dropped = 0
    for q in index["questions"]:
        keep = []
        for r in q.get("ms", []):
            if r["page"] == 7 and r["bbox"] == PSEUDO_P7:
                rec(f"MS {q['question']} p7: DROP pseudo header region {r['bbox']}")
                dropped += 1
                continue
            if r["page"] == 8 and r["bbox"] == PSEUDO_P8:
                rec(f"MS {q['question']} p8: DROP pseudo header region {r['bbox']}")
                dropped += 1
                continue
            keep.append(r)
        q["ms"] = keep
    assert dropped == 3, f"expected exactly 3 pseudo ms regions, dropped {dropped}"

    # --- 2. trim Q5 ms p7 y1 -------------------------------------------
    trimmed = 0
    for q in index["questions"]:
        if q["question"] != "5":
            continue
        for r in q["ms"]:
            if r["page"] == 7 and r["bbox"] == Q5_MS_P7:
                r["bbox"] = list(Q5_MS_P7_NEW)
                rec(f"MS 5 p7: {Q5_MS_P7} -> {Q5_MS_P7_NEW} (footer over-extension trim)")
                trimmed += 1
    assert trimmed == 1, f"expected exactly 1 Q5 p7 trim, got {trimmed}"

    # --- validations ---------------------------------------------------
    for q in index["questions"]:
        assert 1 <= len(q["qp"]) <= 25 and 0 <= len(q["ms"]) <= 25, q["question"]
        for r in q["qp"] + q["ms"]:
            b = r["bbox"]
            assert 0 <= b[0] < b[2] and 0 <= b[1] < b[3], (q["question"], b)
            assert b[3] <= 792, (q["question"], b)
    assert len(index["questions"]) == 43, len(index["questions"])
    qp_n = sum(len(q["qp"]) for q in index["questions"])
    ms_n = sum(len(q["ms"]) for q in index["questions"])
    assert qp_n == 49, qp_n
    assert ms_n == 43, ms_n
    qs = {q["question"]: q for q in index["questions"]}
    assert [(r["page"], r["bbox"]) for r in qs["5"]["ms"]] == [(7, Q5_MS_P7_NEW)], qs["5"]["ms"]

    tmp = IDX.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, IDX)
    new_sha = hashlib.sha256(IDX.read_bytes()).hexdigest()

    report = {
        "key": "0472/2026/Jun/21",
        "fixed_at": "2026-10-04",
        "old_sha256": old_sha,
        "new_sha256": new_sha,
        "questions": len(index["questions"]),
        "qp_regions": qp_n,
        "ms_regions": ms_n,
        "changes": changes,
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("=" * 100)
    print(f"questions={report['questions']} qp_regions={qp_n} ms_regions={ms_n}")
    print(f"old sha256: {old_sha}")
    print(f"new sha256: {new_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
