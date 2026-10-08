# -*- coding: utf-8 -*-
"""0472/2025/Jun/22: apply agreed fixes to cie-index.json (P3 of the re-verification plan).

Fixes (from visual re-check 2026-10-04, finalized in window 121):
- QP regions: x0 -> 70.4, x1 -> 542.4 (covers p2=473.6 / p4=488.4 / p8=486.0 / p10=504.0 /
  p12=580.8 cut-offs; unifies 540.4/540.8/541.2; removes p11 x0=30.4 artifact)
- QP regions with y1=766.0 -> 761.6 (exactly 3: Q5 p11, Q6 p12, 6(d) p12)
- Q5 p11 y0 66.0 -> 58.8 (content starts at 58.8; no text between 58.8 and 67.8)
- MS regions: x -> [71.7, 540.3] (text right edge 537.7-538.0, drawing edge 539.6)
- drop 3 pseudo ms header regions [76.0,32.4,535.6,87.6] (3 / 3(g) on p6; 5 on p7)
- marks (visual: printed [1] on each): 6(a) 0->1, 6(b) 0->1, 6(c) 0->1, 6(d) 0->1,
  6(e) None->1, 6(f) None->1, 6(h) None->1  ((g)=2, (i)=2 already correct)
- Q5 notes: append child-block note
- insert 5(a)-5(e) children (parent 5) between 5 and 6; qp = person blocks on p10,
  ms = the five 1-mark answer rows on ms p6 (5(a)=7, 5(b)=1, 5(c)=8, 5(d)=3, 5(e)=5)

Child texts are visual transcriptions read from the local PDF (4x crops, main agent,
2026-10-04); person names: a Betty, b Mo, c Mei, d Faisal, e Stella.

Backup -> work/0472-2025-Jun-22-index-before-fix.json (first backup preserved)
Report -> work/0472-2025-Jun-22-fix-report.json
Atomic replace; prints old/new sha256.
"""
import hashlib
import json
import os
from pathlib import Path

BR = Path(r"C:/Users/weo/Desktop/api/cie-location-batch")
IDX = BR / "indexes/0472/2025-Jun-22/cie-index.json"
BACKUP = BR / "work/0472-2025-Jun-22-index-before-fix.json"
REPORT = BR / "work/0472-2025-Jun-22-fix-report.json"

PSEUDO_MS = [76.0, 32.4, 535.6, 87.6]

CHILDREN = [
    {"question": "5(a)", "parent": "5",
     "text": "Betty wants to visit a beach where she can swim to see beautiful fish. "
             "She'll need to hire a beach umbrella and isn't coming by car.",
     "marks": None,
     "qp": [{"page": 10, "bbox": [70.4, 152.9, 542.4, 239.4]}],
     "ms": [{"page": 6, "bbox": [71.7, 403.6, 540.3, 420.7]}],
     "uncertain": False,
     "notes": "text 为本地原件视觉转录（说明继承自父题 5；人物 a 描述块与答案线）"},
    {"question": "5(b)", "parent": "5",
     "text": "Mo and his dad hope to cook food on the beach. They're bringing Mo's "
             "grandmother, who needs easy access to the beach, and they want to learn about "
             "local animals.",
     "marks": None,
     "qp": [{"page": 10, "bbox": [70.4, 250.1, 542.4, 336.2]}],
     "ms": [{"page": 6, "bbox": [71.7, 420.7, 540.3, 443.3]}],
     "uncertain": False,
     "notes": "text 为本地原件视觉转录（说明继承自父题 5；人物 b 描述块与答案线）"},
    {"question": "5(c)", "parent": "5",
     "text": "Mei and her mum are looking for a beach with lots of parking and want to buy "
             "snacks during their day. Mei would love to book a sailing lesson.",
     "marks": None,
     "qp": [{"page": 10, "bbox": [70.4, 346.9, 542.4, 434.6]}],
     "ms": [{"page": 6, "bbox": [71.7, 443.3, 540.3, 466.6]}],
     "uncertain": False,
     "notes": "text 为本地原件视觉转录（说明继承自父题 5；人物 c 描述块与答案线）"},
    {"question": "5(d)", "parent": "5",
     "text": "Faisal wants to buy a beach ball and would love to enter a sports competition "
             "during his visit. The family needs a swimming area suitable for his little sister.",
     "marks": None,
     "qp": [{"page": 10, "bbox": [70.4, 443.7, 542.4, 529.8]}],
     "ms": [{"page": 6, "bbox": [71.7, 466.6, 540.3, 489.2]}],
     "uncertain": False,
     "notes": "text 为本地原件视觉转录（说明继承自父题 5；人物 d 描述块与答案线）"},
    {"question": "5(e)", "parent": "5",
     "text": "Stella would like a beach which is not too crowded and has equipment for playing "
             "different sports. Her mum wants some organised activities for Stella's young "
             "brother to enjoy.",
     "marks": None,
     "qp": [{"page": 10, "bbox": [70.4, 538.9, 542.4, 626.7]}],
     "ms": [{"page": 6, "bbox": [71.7, 489.2, 540.3, 509.6]}],
     "uncertain": False,
     "notes": "text 为本地原件视觉转录（说明继承自父题 5；人物 e 描述块与答案线）"},
]

MARKS_FIX = [("6(a)", 0, 1), ("6(b)", 0, 1), ("6(c)", 0, 1), ("6(d)", 0, 1),
             ("6(e)", None, 1), ("6(f)", None, 1), ("6(h)", None, 1)]


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

    # --- 1. QP regions -------------------------------------------------
    n766 = 0
    n588 = 0
    for q in index["questions"]:
        for r in q.get("qp", []):
            old = list(r["bbox"])
            b = list(r["bbox"])
            b[0] = 70.4
            b[2] = 542.4
            if b[3] == 766.0:
                b[3] = 761.6
                n766 += 1
            if q["question"] == "5" and r["page"] == 11 and b[1] == 66.0:
                b[1] = 58.8
                n588 += 1
            if b != old:
                r["bbox"] = b
                rec(f"QP {q['question']} p{r['page']}: {old} -> {b}")
    assert n766 == 3, f"expected exactly 3 y1=766.0 regions, got {n766}"
    assert n588 == 1, f"expected exactly 1 Q5 p11 y0=66.0 region, got {n588}"

    # --- 2. MS regions -------------------------------------------------
    dropped = 0
    for q in index["questions"]:
        keep = []
        for r in q.get("ms", []):
            if r["bbox"] == PSEUDO_MS:
                rec(f"MS {q['question']} p{r['page']}: DROP pseudo header region {r['bbox']}")
                dropped += 1
                continue
            old = list(r["bbox"])
            b = list(r["bbox"])
            b[0] = 71.7
            b[2] = 540.3
            if b != old:
                r["bbox"] = b
                rec(f"MS {q['question']} p{r['page']}: {old} -> {b}")
            keep.append(r)
        q["ms"] = keep
    assert dropped == 3, f"expected exactly 3 pseudo ms regions, dropped {dropped}"

    # --- 3. marks ------------------------------------------------------
    qs = {q["question"]: q for q in index["questions"]}
    for name, old_m, new_m in MARKS_FIX:
        cur = qs[name]["marks"]
        assert cur == old_m, f"{name} marks expected {old_m!r}, got {cur!r}"
        qs[name]["marks"] = new_m
        rec(f"marks {name}: {old_m!r} -> {new_m!r}")

    # --- 4. Q5 notes ---------------------------------------------------
    q5 = qs["5"]
    if "子题 (a)–(e)" not in q5["notes"]:
        old = q5["notes"]
        q5["notes"] = old + "；子题 (a)–(e) 为五位人物描述块（MS 每行 1 分）"
        rec(f"notes 5: {old!r} -> {q5['notes']!r}")

    # --- 5. insert children -------------------------------------------
    if "5(a)" in qs:
        rec("5(a)-5(e) already present, not re-inserted")
    else:
        pos = index["questions"].index(q5)
        for i, ch in enumerate(CHILDREN):
            index["questions"].insert(pos + 1 + i, ch)
        rec(f"inserted 5(a)-5(e) after 5 at positions {pos + 1}..{pos + 5}")

    # --- validations ---------------------------------------------------
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
    i5 = index["questions"].index(qs["5"])
    kids = [index["questions"][i5 + 1 + k]["question"] for k in range(5)]
    assert kids == ["5(a)", "5(b)", "5(c)", "5(d)", "5(e)"], kids
    assert index["questions"][i5 + 6] is qs["6"], "children placement"
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
