# -*- coding: utf-8 -*-
"""0472/2025/Jun/22: fix2 — Q3 p7 top edge (only remaining re-verification issue).

From re-verification frame c10 (window 126): Q3 p7 region started at y0=71.2,
cutting off the printed "(d)" question-number area at top of page 7. The first
visible content row on Q3 p7 (child 3(d)) begins at y=58.6; Q3 p7 must start
at 58.6 like all other continuation pages (58.8/59.2 tolerance band).

Change: question "3" qp region page 7: [70.4, 71.2, 542.4, 761.6] -> [70.4, 58.6, 542.4, 761.6]

Backup -> work/0472-2025-Jun-22-index-before-fix2.json (fix1 backup preserved)
Report -> work/0472-2025-Jun-22-fix2-report.json
Atomic replace; prints old/new sha256.
"""
import hashlib
import json
import os
from pathlib import Path

BR = Path(r"C:/Users/weo/Desktop/api/cie-location-batch")
IDX = BR / "indexes/0472/2025-Jun-22/cie-index.json"
BACKUP = BR / "work/0472-2025-Jun-22-index-before-fix2.json"
REPORT = BR / "work/0472-2025-Jun-22-fix2-report.json"

OLD_BBOX = [70.4, 71.2, 542.4, 761.6]
NEW_BBOX = [70.4, 58.6, 542.4, 761.6]


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

    qs = {q["question"]: q for q in index["questions"]}
    q3 = qs["3"]
    hits = 0
    for r in q3["qp"]:
        if r["page"] == 7:
            assert list(r["bbox"]) == OLD_BBOX, f"unexpected Q3 p7 bbox: {r['bbox']}"
            r["bbox"] = list(NEW_BBOX)
            hits += 1
            rec(f"QP 3 p7: {OLD_BBOX} -> {NEW_BBOX}")
    assert hits == 1, f"expected exactly 1 Q3 p7 region, got {hits}"

    # validations
    for q in index["questions"]:
        assert 1 <= len(q["qp"]) <= 25 and 0 <= len(q["ms"]) <= 25, q["question"]
        for r in q["qp"]:
            b = r["bbox"]
            assert b[0] == 70.4 and b[2] == 542.4, (q["question"], b)
            assert 0 <= b[0] < b[2] and 0 <= b[1] < b[3] <= 761.6, (q["question"], b)
        for r in q["ms"]:
            b = r["bbox"]
            assert b[0] == 71.7 and b[2] == 540.3, (q["question"], b)
            assert 0 <= b[0] < b[2] and 0 <= b[1] < b[3], (q["question"], b)
    assert len(index["questions"]) == 48, len(index["questions"])
    qp_n = sum(len(q["qp"]) for q in index["questions"])
    ms_n = sum(len(q["ms"]) for q in index["questions"])
    assert (qp_n, ms_n) == (54, 48), (qp_n, ms_n)

    tmp = IDX.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, IDX)
    new_sha = hashlib.sha256(IDX.read_bytes()).hexdigest()

    report = {
        "key": "0472/2025/Jun/22",
        "fixed_at": "2026-10-04",
        "fix": "fix2_q3p7_top",
        "old_sha256": old_sha,
        "new_sha256": new_sha,
        "questions": len(index["questions"]),
        "qp_regions": qp_n,
        "ms_regions": ms_n,
        "changes": changes,
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("=" * 100)
    print(f"questions={report['questions']} qp_regions={report['qp_regions']} ms_regions={report['ms_regions']}")
    print(f"old sha256: {old_sha}")
    print(f"new sha256: {new_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
