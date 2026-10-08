# -*- coding: utf-8 -*-
"""0472/2025/Jun/41: apply agreed fixes to cie-index.json (P3 of the re-verification plan).

Fixes (from visual re-check 2026-10-04, finalized in window 130):
- Q1 ms: p6 [102.0,61.2,344.4,729.6] -> [102.0,56.0,346.0,730.0]
  (unrot coords; disp = (792-y1, x0, 792-y0, x1) => 62.0,102.0 -> 736.0,346.0)
- Q2 ms: p7 [102.0,62.4,282.4,729.6] -> [102.0,56.0,284.0,730.0]
         p8 [58.4,145.6,422.8,724.8] -> [72.0,56.0,427.0,730.0]
- Q3 ms: p9 [124.8,61.6,499.6,730.0] -> [102.0,56.0,501.0,730.0]  (includes the
  "Answer Question 3(a) or Question 3(b)" instruction line at disp 102.0-113.8)
         plus shared mark tables p10 [72.0,56.0,375.0,730.0],
         p11 [72.0,56.0,362.0,730.0], p12 [72.0,56.0,299.0,730.0]
- Q3(a) ms: p9 [124.8,61.6,316.4,730.0] -> [124.8,56.0,316.4,730.0]; plus p10/p11/p12
- Q3(b) ms: p9 [316.4,61.6,499.6,730.0] -> [316.4,56.0,501.0,730.0]; plus p10/p11/p12
- DROP Q1 ms p7 strip [58.4,62.4,102.0,729.6] (PUBLISHED + table header only)
- DROP Q2 ms p9 strip [58.4,61.6,124.8,730.0] (strip + instruction line, now in Q3 p9)
- notes: Q3 / Q3(a) / Q3(b) get shared-table note (p10-p12 tables are shared by both
  sub-questions; parent region = union of child regions)
- QP regions unchanged (Q1 p2, Q2 p3, Q3 p4 x2 + 3(a) + 3(b))

Backup -> work/0472-2025-Jun-41-index-before-fix.json (first backup preserved)
Report -> work/0472-2025-Jun-41-fix-report.json
Atomic replace; prints old/new sha256. Does NOT touch errors.jsonl.
"""
import hashlib
import json
import os
from pathlib import Path

BR = Path(r"C:/Users/weo/Desktop/api/cie-location-batch")
IDX = BR / "indexes/0472/2025-Jun-41/cie-index.json"
BACKUP = BR / "work/0472-2025-Jun-41-index-before-fix.json"
REPORT = BR / "work/0472-2025-Jun-41-fix-report.json"

OLD_SHA = "53a1eb33b1b344aa59807dc30ff5729cddddf5b44e37e8287e49181422dbb03f"

OLD_MS = {
    "1": [(6, [102.0, 61.2, 344.4, 729.6]), (7, [58.4, 62.4, 102.0, 729.6])],
    "2": [(7, [102.0, 62.4, 282.4, 729.6]), (8, [58.4, 145.6, 422.8, 724.8]),
          (9, [58.4, 61.6, 124.8, 730.0])],
    "3": [(9, [124.8, 61.6, 499.6, 730.0])],
    "3(a)": [(9, [124.8, 61.6, 316.4, 730.0])],
    "3(b)": [(9, [316.4, 61.6, 499.6, 730.0])],
}

NEW_MS = {
    "1": [(6, [102.0, 56.0, 346.0, 730.0])],
    "2": [(7, [102.0, 56.0, 284.0, 730.0]), (8, [72.0, 56.0, 427.0, 730.0])],
    "3": [(9, [102.0, 56.0, 501.0, 730.0]), (10, [72.0, 56.0, 375.0, 730.0]),
          (11, [72.0, 56.0, 362.0, 730.0]), (12, [72.0, 56.0, 299.0, 730.0])],
    "3(a)": [(9, [124.8, 56.0, 316.4, 730.0]), (10, [72.0, 56.0, 375.0, 730.0]),
             (11, [72.0, 56.0, 362.0, 730.0]), (12, [72.0, 56.0, 299.0, 730.0])],
    "3(b)": [(9, [316.4, 56.0, 501.0, 730.0]), (10, [72.0, 56.0, 375.0, 730.0]),
             (11, [72.0, 56.0, 362.0, 730.0]), (12, [72.0, 56.0, 299.0, 730.0])],
}

EXPECTED_QP = {
    "1": [(2, [70.4, 58.8, 540.4, 759.6])],
    "2": [(3, [70.4, 58.8, 541.2, 761.6])],
    "3": [(4, [70.4, 58.8, 540.8, 759.6])],
    "3(a)": [(4, [70.4, 107.6, 540.8, 278.8])],
    "3(b)": [(4, [70.4, 278.8, 540.8, 759.6])],
}

NOTE_3 = "；ms p10–p12 为 3(a)/3(b) 共用评分表（Task completion / Range / Accuracy）"
NOTE_CHILD = ("；ms p10–p12 为 3(a)/3(b) 共用评分表（Task completion / Range / Accuracy），"
              "与另一子题引用同一区域")


def main():
    old_sha = hashlib.sha256(IDX.read_bytes()).hexdigest()
    assert old_sha == OLD_SHA, f"index sha changed: {old_sha} != {OLD_SHA}"
    index = json.loads(IDX.read_text(encoding="utf-8"))
    changes = []

    def rec(msg):
        changes.append(msg)
        print(msg)

    if not BACKUP.exists():
        BACKUP.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
        rec(f"backup written: {BACKUP.name}")
    else:
        rec(f"backup already exists, kept: {BACKUP.name}")

    qs = {q["question"]: q for q in index["questions"]}
    assert sorted(qs) == ["1", "2", "3", "3(a)", "3(b)"], sorted(qs)

    # --- 1. verify old state, then replace ms regions ------------------
    for name, expected in OLD_MS.items():
        q = qs[name]
        got = [(r["page"], list(r["bbox"])) for r in q["ms"]]
        assert got == expected, f"{name} old ms mismatch:\n got={got}\n exp={expected}"

    for name, new in NEW_MS.items():
        q = qs[name]
        old = [(r["page"], list(r["bbox"])) for r in q["ms"]]
        old_pages = {p for p, _ in old}
        new_pages = {p for p, _ in new}
        for (op, ob), (np_, nb) in zip(old, new):
            if op == np_ and ob != nb:
                rec(f"MS {name} p{op}: {ob} -> {nb}")
        for p, b in old:
            if p not in new_pages:
                rec(f"MS {name} p{p}: DROP {b}")
        for p, b in new:
            if p not in old_pages:
                rec(f"MS {name} p{p}: ADD {b}")
        q["ms"] = [{"page": p, "bbox": b} for p, b in new]

    # --- 2. notes ------------------------------------------------------
    for name, note in (("3", NOTE_3), ("3(a)", NOTE_CHILD), ("3(b)", NOTE_CHILD)):
        q = qs[name]
        if "共用评分表" not in q["notes"]:
            old = q["notes"]
            q["notes"] = old + note
            rec(f"notes {name}: appended shared-table note")

    # --- 3. QP unchanged check -----------------------------------------
    for name, expected in EXPECTED_QP.items():
        got = [(r["page"], list(r["bbox"])) for r in qs[name]["qp"]]
        assert got == expected, f"{name} qp changed unexpectedly: {got}"

    # --- validations ---------------------------------------------------
    assert len(index["questions"]) == 5, len(index["questions"])
    for q in index["questions"]:
        assert 1 <= len(q["qp"]) <= 25 and 0 <= len(q["ms"]) <= 25, q["question"]
        for r in q["ms"]:
            b = r["bbox"]
            assert b[1] == 56.0 and b[3] == 730.0, (q["question"], r["page"], b)
            assert 0 < b[0] < b[2] <= 612, (q["question"], r["page"], b)
            assert 0 < b[1] < b[3] <= 792, (q["question"], r["page"], b)
    ms_n = sum(len(q["ms"]) for q in index["questions"])
    qp_n = sum(len(q["qp"]) for q in index["questions"])
    assert (qp_n, ms_n) == (5, 15), (qp_n, ms_n)

    tmp = IDX.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, IDX)
    new_sha = hashlib.sha256(IDX.read_bytes()).hexdigest()

    report = {
        "key": "0472/2025/Jun/41",
        "fixed_at": "2026-10-04",
        "old_sha256": old_sha,
        "new_sha256": new_sha,
        "questions": len(index["questions"]),
        "qp_regions": qp_n,
        "ms_regions": ms_n,
        "changes": changes,
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")

    print("=" * 100)
    print(f"questions={report['questions']} qp_regions={qp_n} ms_regions={ms_n}")
    print(f"old sha256: {old_sha}")
    print(f"new sha256: {new_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
