# -*- coding: utf-8 -*-
"""0472/2026/Jun/22: apply agreed fixes to cie-index.json (P3 of the re-verification plan).

Fixes (from visual re-check frames 1-41, 2026-10-04; all values verified against
the local PDFs with pymupdf scans):
- 18 QP region changes (x1/y0/y1 corrections; qp_changes in fixlist)
- all MS regions: x0->70.8, x1->541.2 (include table left/right borders;
  table verticals on p6/p7/p8 sit at x72.3-72.8 and x539.2-539.6)
- 11 MS y1 changes (row bottom borders / table ends)
- 3 pseudo ms header regions dropped (3@p7, 3(g)@p7, 5@p8)

Backup -> work/0472-2026-Jun-22-index-before-fix.json (first backup preserved)
Report -> work/0472-2026-Jun-22-fix-report.json
Atomic replace; prints old/new sha256.
"""
import hashlib
import json
import os
from pathlib import Path

BR = Path(r"C:/Users/weo/Desktop/api/cie-location-batch")
IDX = BR / "indexes/0472/2026-Jun-22/cie-index.json"
FIX = BR / "work/0472_2026_22_fixlist.json"
BACKUP = BR / "work/0472-2026-Jun-22-index-before-fix.json"
REPORT = BR / "work/0472-2026-Jun-22-fix-report.json"


def main():
    old_sha = hashlib.sha256(IDX.read_bytes()).hexdigest()
    index = json.loads(IDX.read_text(encoding="utf-8"))
    fix = json.loads(FIX.read_text(encoding="utf-8"))
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
    assert len(index["questions"]) == 43, len(index["questions"])

    # --- 1. drop pseudo ms header regions ------------------------------
    dropped = 0
    for dele in fix["ms_deletions"]:
        q = qs[dele["question"]]
        keep = []
        for r in q["ms"]:
            if r["page"] == dele["page"] and r["bbox"] == dele["bbox"]:
                rec(f"MS {q['question']} p{dele['page']}: DROP pseudo header region {r['bbox']} ({dele['reason']})")
                dropped += 1
                continue
            keep.append(r)
        q["ms"] = keep
    assert dropped == 3, f"expected exactly 3 pseudo ms regions, dropped {dropped}"

    # --- 2. apply 18 QP changes ----------------------------------------
    n_qp = 0
    for ch in fix["qp_changes"]:
        q = qs[ch["question"]]
        hits = [r for r in q["qp"] if r["page"] == ch["page"] and r["bbox"] == ch["old"]]
        assert len(hits) == 1, f"QP {ch['question']} p{ch['page']}: {len(hits)} matches for {ch['old']}"
        hits[0]["bbox"] = list(ch["new"])
        rec(f"QP {ch['question']} p{ch['page']}: {ch['old']} -> {ch['new']}")
        n_qp += 1
    assert n_qp == 18, n_qp

    # --- 3. MS x rule (all regions) ------------------------------------
    x0n, x1n = fix["ms_common"]["x0"], fix["ms_common"]["x1"]
    n_x = 0
    for q in index["questions"]:
        for r in q["ms"]:
            r["bbox"] = [x0n, r["bbox"][1], x1n, r["bbox"][3]]
            n_x += 1
    assert n_x == 43, n_x
    rec(f"MS: all {n_x} regions x0->{x0n}, x1->{x1n}")

    # --- 4. MS y1 changes ----------------------------------------------
    n_y = 0
    for ch in fix["ms_y_changes"]:
        q = qs[ch["question"]]
        hits = [r for r in q["ms"] if r["page"] == ch["page"] and r["bbox"][3] == ch["old_y1"]]
        assert len(hits) == 1, f"MS {ch['question']} p{ch['page']}: {len(hits)} matches for y1={ch['old_y1']}"
        hits[0]["bbox"][3] = ch["new_y1"]
        rec(f"MS {ch['question']} p{ch['page']}: y1 {ch['old_y1']} -> {ch['new_y1']}")
        n_y += 1
    assert n_y == 11, n_y

    # --- validations ---------------------------------------------------
    for q in index["questions"]:
        assert 1 <= len(q["qp"]) <= 25 and 0 <= len(q["ms"]) <= 25, q["question"]
        for r in q["qp"] + q["ms"]:
            b = r["bbox"]
            assert 0 <= b[0] < b[2] and 0 <= b[1] < b[3], (q["question"], b)
            assert b[2] <= 612 and b[3] <= 792, (q["question"], b)
    qp_n = sum(len(q["qp"]) for q in index["questions"])
    ms_n = sum(len(q["ms"]) for q in index["questions"])
    assert qp_n == 49, qp_n
    assert ms_n == 43, ms_n

    # spot checks (values from fixlist + scans)
    assert qs["1"]["ms"] == [{"page": 6, "bbox": [70.8, 87.6, 541.2, 151.5]}], qs["1"]["ms"]
    assert qs["1(c)"]["ms"] == [{"page": 6, "bbox": [70.8, 133.5, 541.2, 151.5]}], qs["1(c)"]["ms"]
    assert qs["3"]["ms"] == [{"page": 6, "bbox": [70.8, 385.2, 541.2, 540.6]}], qs["3"]["ms"]
    assert qs["5"]["ms"] == [{"page": 7, "bbox": [70.8, 564.8, 541.2, 675.3]}], qs["5"]["ms"]
    assert qs["6"]["ms"] == [{"page": 8, "bbox": [70.8, 87.6, 541.2, 634.4]}], qs["6"]["ms"]
    assert qs["6(i)"]["ms"] == [{"page": 8, "bbox": [70.8, 604.8, 541.2, 634.4]}], qs["6(i)"]["ms"]
    assert qs["5"]["qp"][0]["bbox"] == [70.8, 58.8, 540.4, 614.9], qs["5"]["qp"]
    assert qs["1"]["qp"][0]["bbox"] == [71.2, 59.2, 541.2, 463.2], qs["1"]["qp"]

    tmp = IDX.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, IDX)
    new_sha = hashlib.sha256(IDX.read_bytes()).hexdigest()

    report = {
        "key": "0472/2026/Jun/22",
        "fixed_at": "2026-10-04",
        "old_sha256": old_sha,
        "new_sha256": new_sha,
        "questions": len(index["questions"]),
        "qp_regions": qp_n,
        "ms_regions": ms_n,
        "qp_changes": 18,
        "ms_x_rule_regions": n_x,
        "ms_y1_changes": n_y,
        "ms_deletions": dropped,
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
