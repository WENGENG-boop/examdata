# -*- coding: utf-8 -*-
"""0472/2025/Jun/21: apply agreed fixes to cie-index.json (P3 of the re-verification plan).

Fixes (from visual re-check 2026-10-03/04, finalized in window 114):
- QP regions: x0 -> 70.4, x1 -> 542.4 (covers p2=422.0 / p6=511.2 / p10=488.0 cut-offs;
  unifies 540.4/540.8/541.2; removes p14=580.8 artifact)
- QP regions with y1=766.0 -> 761.6 (exactly 3: Q5 p13, Q6 p14, 6(d) p14)
- Q5 p13 y0 64.0 -> 58.8 (ad box top 60.7 + title 65.9 both included)
- MS regions: x -> [71.7, 540.3] (table frame borders), y untouched
- drop 3 pseudo ms header regions [76.0,32.4,474.0,87.6] (3 / 3(g) on p5; 5 on p6)
- marks: 6(b) 0 -> 1, 6(d) 0 -> 1
- Q5 notes: append child-block note
- insert 5(a)-5(e) children (parent 5) between 5 and 6; qp = person blocks on p12,
  ms = the five 1-mark answer rows on ms p5

Backup -> work/0472-2025-Jun-21-index-before-fix.json (first backup preserved)
Report -> work/0472-2025-Jun-21-fix-report.json
Atomic replace; prints old/new sha256.
"""
import hashlib
import json
import os
import sys
from pathlib import Path

BR = Path(r"C:/Users/weo/Desktop/api/cie-location-batch")
IDX = BR / "indexes/0472/2025-Jun-21/cie-index.json"
BACKUP = BR / "work/0472-2025-Jun-21-index-before-fix.json"
REPORT = BR / "work/0472-2025-Jun-21-fix-report.json"

PSEUDO_MS = [76.0, 32.4, 474.0, 87.6]

CHILDREN = [
    {"question": "5(a)", "parent": "5",
     "text": "Habiba is interested in technology and wants to learn about the latest cameras. "
             "She'd like to join a course which meets weekly and visit some exhibitions with the group.",
     "marks": None,
     "qp": [{"page": 12, "bbox": [70.4, 156.6, 542.4, 236.6]}],
     "ms": [{"page": 5, "bbox": [71.7, 426.8, 540.3, 450.2]}],
     "uncertain": False,
     "notes": "text 来自 Windows.Media.Ocr(zh-Hans-CN) 转录，可能有识别噪声（说明继承自父题 5；人物 a 描述块与答案线）"},
    {"question": "5(b)", "parent": "5",
     "text": "Paolo wants to know more about using IT to improve his pictures and learn from a "
             "professional photographer. He also wants to know how to take better pictures of animals.",
     "marks": None,
     "qp": [{"page": 12, "bbox": [70.4, 254.3, 542.4, 334.2]}],
     "ms": [{"page": 5, "bbox": [71.7, 450.2, 540.3, 472.8]}],
     "uncertain": False,
     "notes": "text 来自 Windows.Media.Ocr(zh-Hans-CN) 转录，可能有识别噪声（说明继承自父题 5；人物 b 描述块与答案线）"},
    {"question": "5(c)", "parent": "5",
     "text": "Izabella hopes to take pictures of the clothes her dad designs and get ideas for making "
             "presents using photos. She wants a course for people who already have photography experience.",
     "marks": None,
     "qp": [{"page": 12, "bbox": [70.4, 351.9, 542.4, 431.7]}],
     "ms": [{"page": 5, "bbox": [71.7, 472.8, 540.3, 496.1]}],
     "uncertain": False,
     "notes": "text 来自 Windows.Media.Ocr(zh-Hans-CN) 转录，可能有识别噪声（说明继承自父题 5；人物 c 描述块与答案线）"},
    {"question": "5(d)", "parent": "5",
     "text": "Diego needs to do a beginners' course and get tips about photographing people. "
             "He wants to borrow a traditional camera to see if he likes using it.",
     "marks": None,
     "qp": [{"page": 12, "bbox": [70.4, 449.4, 542.4, 529.3]}],
     "ms": [{"page": 5, "bbox": [71.7, 496.1, 540.3, 518.7]}],
     "uncertain": False,
     "notes": "text 来自 Windows.Media.Ocr(zh-Hans-CN) 转录，可能有识别噪声（说明继承自父题 5；人物 d 描述块与答案线）"},
    {"question": "5(e)", "parent": "5",
     "text": "Christi would like to take pictures of scenery with the group. She'd like to find out "
             "about the history of photography and to show her pictures in an exhibition.",
     "marks": None,
     "qp": [{"page": 12, "bbox": [70.4, 547.0, 542.4, 626.8]}],
     "ms": [{"page": 5, "bbox": [71.7, 518.7, 540.3, 532.8]}],
     "uncertain": False,
     "notes": "text 来自 Windows.Media.Ocr(zh-Hans-CN) 转录，可能有识别噪声（说明继承自父题 5；人物 e 描述块与答案线）"},
]


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
    for q in index["questions"]:
        for r in q.get("qp", []):
            old = list(r["bbox"])
            b = list(r["bbox"])
            b[0] = 70.4
            b[2] = 542.4
            if b[3] == 766.0:
                b[3] = 761.6
                n766 += 1
            if q["question"] == "5" and r["page"] == 13 and b[1] == 64.0:
                b[1] = 58.8
            if b != old:
                r["bbox"] = b
                rec(f"QP {q['question']} p{r['page']}: {old} -> {b}")
    assert n766 == 3, f"expected exactly 3 y1=766.0 regions, got {n766}"

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
    for name, newmarks in (("6(b)", 1), ("6(d)", 1)):
        old = qs[name]["marks"]
        qs[name]["marks"] = newmarks
        rec(f"marks {name}: {old} -> {newmarks}")

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

    tmp = IDX.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, IDX)
    new_sha = hashlib.sha256(IDX.read_bytes()).hexdigest()

    report = {
        "key": "0472/2025/Jun/21",
        "fixed_at": "2026-10-04",
        "old_sha256": old_sha,
        "new_sha256": new_sha,
        "questions": len(index["questions"]),
        "qp_regions": sum(len(q["qp"]) for q in index["questions"]),
        "ms_regions": sum(len(q["ms"]) for q in index["questions"]),
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
