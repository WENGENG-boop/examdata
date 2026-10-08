# -*- coding: utf-8 -*-
"""0472/2026/Jun/21: apply all fixes from work/0472_2026_21_fixes.jsonl to cie-index.json.

67 records = 24 qp fixes (frames 7-32) + 43 ms fixes (frame-34 MS text-layer audit).
Each record: (question normalized, role, page) must match a region whose bbox
equals old_bbox (apply) or already equals new_bbox (idempotent skip).

Backup -> work/0472-2026-Jun-21-index-before-fix2.json (first backup preserved)
Report -> work/0472-2026-Jun-21-fix-report2.json
Atomic replace; prints old/new sha256. No network.
"""
import hashlib
import json
import os
import re
from pathlib import Path

BR = Path(r"C:/Users/weo/Desktop/api/cie-location-batch")
IDX = BR / "indexes/0472/2026-Jun-21/cie-index.json"
FIXES = BR / "work/0472_2026_21_fixes.jsonl"
BACKUP = BR / "work/0472-2026-Jun-21-index-before-fix2.json"
REPORT = BR / "work/0472-2026-Jun-21-fix-report2.json"


def close(a, b):
    return all(abs(x - y) < 0.01 for x, y in zip(a, b))


def main():
    old_sha = hashlib.sha256(IDX.read_bytes()).hexdigest()
    orig_text = IDX.read_text(encoding="utf-8")
    index = json.loads(orig_text)
    by_q = {q["question"]: q for q in index["questions"]}

    fixes = [json.loads(l) for l in FIXES.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(fixes) == 67, f"expected 67 fixes, got {len(fixes)}"

    changes, applied, already = [], 0, 0
    seen = set()
    for f in fixes:
        name = re.sub(r"^Q(?=\d)", "", f["question"])
        role, page = f["role"], f["page"]
        old, new = [float(v) for v in f["old_bbox"]], [float(v) for v in f["new_bbox"]]
        key = (name, role, page)
        assert key not in seen, f"duplicate fix target {key}"
        seen.add(key)
        q = by_q.get(name)
        assert q is not None, f"question not found: {name}"
        match = [r for r in q[role] if r["page"] == page and close(r["bbox"], old)]
        if match:
            assert len(match) == 1, (key, match)
            match[0]["bbox"] = new
            applied += 1
            changes.append({"question": name, "role": role, "page": page, "old": old, "new": new})
        else:
            hit = [r for r in q[role] if r["page"] == page and close(r["bbox"], new)]
            assert hit, f"no region matches old/new for {key}: {q[role]}"
            already += 1
            changes.append({"question": name, "role": role, "page": page,
                            "old": old, "new": new, "note": "already applied"})

    assert applied + already == 67, (applied, already)
    for c in changes:
        assert not close(c["old"], c["new"]), c

    # ---- validations on the fixed index ----
    qs = index["questions"]
    assert len(qs) == 43, len(qs)
    qp_n = sum(len(q["qp"]) for q in qs)
    ms_n = sum(len(q["ms"]) for q in qs)
    assert (qp_n, ms_n) == (49, 43), (qp_n, ms_n)
    for q in qs:
        assert 1 <= len(q["qp"]) <= 25 and 1 <= len(q["ms"]) <= 25, q["question"]
        for r in q["qp"] + q["ms"]:
            b = r["bbox"]
            assert 0 < b[0] < b[2] and 0 < b[1] < b[3] <= 792, (q["question"], r)

    if not BACKUP.exists():
        BACKUP.write_text(orig_text, encoding="utf-8")
        print(f"backup written: {BACKUP.name}")
    else:
        print(f"backup already exists, kept: {BACKUP.name}")

    tmp = IDX.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, IDX)
    new_sha = hashlib.sha256(IDX.read_bytes()).hexdigest()

    report = {
        "key": "0472/2026/Jun/21",
        "fixed_at": "2026-10-04",
        "old_sha256": old_sha,
        "new_sha256": new_sha,
        "questions": len(qs),
        "qp_regions": qp_n,
        "ms_regions": ms_n,
        "applied": applied,
        "already_applied": already,
        "changes": changes,
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("=" * 100)
    print(f"questions={len(qs)} qp_regions={qp_n} ms_regions={ms_n} applied={applied} already={already}")
    print(f"old sha256: {old_sha}")
    print(f"new sha256: {new_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
