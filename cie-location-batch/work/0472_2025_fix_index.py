# -*- coding: utf-8 -*-
"""0472/2025/Jun/11: apply agreed fixes to cie-index.json.

Fixes (from visual re-check 2026-10-03):
- Q1: add header region p3 [70.4,58.8,541.2,144.4] as qp[0] (Questions 1-8 + intro)
- Q8/Q14/Q19/Q28/Q34: drop mis-attached section-header region (moves to next question)
- Q9/Q15/Q20/Q29/Q35: gain that header as qp[0] (p6/p8/p9 top normalized 34.8->58.8 to exclude page number)
- Q24: bottom 415.6 -> 332.0 (include [PAUSE], stop before "Part 2" head)
- Q25: two regions [332.0,415.6] (Part 2 head + instructions) + [415.6,551.2] (content)
- Q23..Q26: x1 514.8 -> 541.2 (include right-side [1] marks; all other pages already do)
- ms: rebuild all 37 regions from MS table row borders (p2 Q1-28, p3 Q29-37, x=[71.7,538.8])
- marks: Q1-34=1, Q35-37=2 (from MS Marks column)
- text: rebuilt from QP text layer per new regions (footers/[Total:]/dot-leaders/end-of-paper note filtered)
- uncertain=false; notes rewritten to record visual verification

Backup -> work/0472-2025-index-before-fix.json (first backup preserved).
Report -> work/0472-2025-fix-report.json
"""
import hashlib
import json
import os
import re
import sys
from pathlib import Path

import pymupdf as fitz

BR = Path(r"C:/Users/weo/Desktop/api/cie-location-batch")
IDX = BR / "indexes/0472/2025-Jun-11/cie-index.json"
QP = BR / "tmp/0472/2025-Jun-11/0472_s25_qp_11.pdf"
BACKUP = BR / "work/0472-2025-index-before-fix.json"
REPORT = BR / "work/0472-2025-fix-report.json"

NEW_QP = {
    "1":  [(3, [70.4, 58.8, 541.2, 144.4]), (3, [70.4, 144.4, 541.2, 363.2])],
    "2":  [(3, [70.4, 363.2, 541.2, 761.6])],
    "3":  [(4, [70.4, 58.8, 540.8, 277.6])],
    "4":  [(4, [70.4, 277.6, 540.8, 514.0])],
    "5":  [(4, [70.4, 514.0, 540.8, 759.6])],
    "6":  [(5, [70.4, 58.8, 541.2, 282.8])],
    "7":  [(5, [70.4, 282.8, 541.2, 506.8])],
    "8":  [(5, [70.4, 506.8, 541.2, 761.6])],
    "9":  [(6, [70.4, 58.8, 540.4, 161.2]), (6, [70.4, 161.2, 540.4, 355.2])],
    "10": [(6, [70.4, 355.2, 540.4, 547.6])],
    "11": [(6, [70.4, 547.6, 540.4, 759.6])],
    "12": [(7, [70.4, 58.8, 541.2, 258.4])],
    "13": [(7, [70.4, 258.4, 541.2, 458.0])],
    "14": [(7, [70.4, 458.0, 541.2, 761.6])],
    "15": [(8, [70.4, 58.8, 540.8, 470.8]), (8, [70.4, 470.8, 540.8, 507.6])],
    "16": [(8, [70.4, 507.6, 540.8, 544.4])],
    "17": [(8, [70.4, 544.4, 540.8, 580.8])],
    "18": [(8, [70.4, 580.8, 540.8, 617.6])],
    "19": [(8, [70.4, 617.6, 540.8, 759.6])],
    "20": [(9, [70.4, 58.8, 541.2, 218.0]), (9, [70.4, 218.0, 541.2, 353.6])],
    "21": [(9, [70.4, 353.6, 541.2, 489.2])],
    "22": [(9, [70.4, 489.2, 541.2, 761.6])],
    "23": [(10, [70.4, 58.8, 541.2, 194.4])],
    "24": [(10, [70.4, 194.4, 541.2, 332.0])],
    "25": [(10, [70.4, 332.0, 541.2, 415.6]), (10, [70.4, 415.6, 541.2, 551.2])],
    "26": [(10, [70.4, 551.2, 541.2, 759.6])],
    "27": [(11, [70.4, 58.8, 541.2, 194.4])],
    "28": [(11, [70.4, 194.4, 541.2, 761.6])],
    "29": [(12, [70.4, 58.8, 540.4, 168.8]), (12, [70.4, 168.8, 540.4, 334.4])],
    "30": [(12, [70.4, 334.4, 540.4, 499.6])],
    "31": [(12, [70.4, 499.6, 540.4, 759.6])],
    "32": [(13, [70.4, 58.8, 541.2, 224.4])],
    "33": [(13, [70.4, 224.4, 541.2, 389.6])],
    "34": [(13, [70.4, 389.6, 541.2, 761.6])],
    "35": [(14, [70.4, 58.8, 540.4, 168.8]), (14, [70.4, 168.8, 540.4, 352.0])],
    "36": [(14, [70.4, 352.0, 540.4, 759.6])],
    "37": [(15, [70.4, 64.0, 540.4, 759.6])],
}

MS_P2 = [59.1, 81.7, 105.1, 128.4, 151.0, 174.4, 197.0, 220.3, 242.9, 266.3,
         289.6, 312.2, 335.6, 358.1, 381.5, 404.1, 427.5, 450.0, 473.4, 496.7,
         519.3, 542.7, 565.3, 588.6, 611.2, 634.6, 657.9, 680.5, 703.9, 726.5]
MS_P3 = [59.1, 81.7, 105.1, 128.4, 151.0, 174.4, 197.0, 220.3, 242.9, 266.3, 288.9]

SECTION_FIRST = {"1": "1–8", "9": "9–14", "15": "15–19", "20": "20–28",
                 "25": "25–28", "29": "29–34", "35": "35–37"}

SKIP_PREFIX = ("There will now be six minutes",
               "Follow the instructions on the answer sheet")


def ms_regions():
    out = {}
    for n in range(1, 29):
        out[str(n)] = [(2, [71.7, MS_P2[n], 538.8, MS_P2[n + 1]])]
    for n in range(29, 38):
        i = n - 28
        out[str(n)] = [(3, [71.7, MS_P3[i], 538.8, MS_P3[i + 1]])]
    return out


def extract_text(doc, regions):
    parts, seen = [], set()
    for page_no, bbox in regions:
        page = doc[page_no - 1]
        x0, y0, x1, y1 = bbox
        lines = []
        for block in page.get_text("dict")["blocks"]:
            if block.get("type") != 0:
                continue
            for line in block["lines"]:
                lb = line["bbox"]
                cx, cy = (lb[0] + lb[2]) / 2, (lb[1] + lb[3]) / 2
                if not (x0 <= cx <= x1 and y0 <= cy <= y1):
                    continue
                txt = re.sub(r"\s+", " ", "".join(s["text"] for s in line["spans"])).strip()
                if not txt:
                    continue
                if cy > 740:
                    continue
                if re.fullmatch(r"\[Total: \d+\]", txt):
                    continue
                if txt == "[Turn over":
                    continue
                if re.fullmatch(r"[.…\s]+", txt):
                    continue
                if txt.startswith(SKIP_PREFIX):
                    continue
                key = (page_no, round(lb[0], 1), round(lb[1], 1), txt)
                if key in seen:
                    continue
                seen.add(key)
                lines.append((round(lb[1], 2), round(lb[0], 2), txt))
        lines.sort()
        parts.extend(t for _, _, t in lines)
    return " ".join(parts)


def main():
    old_bytes = IDX.read_bytes()
    old_sha = hashlib.sha256(old_bytes).hexdigest()
    if not BACKUP.exists():
        BACKUP.write_bytes(old_bytes)
        print(f"backup written: {BACKUP.name}")
    else:
        print(f"backup exists (kept): {BACKUP.name}")

    index = json.loads(old_bytes.decode("utf-8"))
    qmap = {q["question"]: q for q in index["questions"]}
    assert set(qmap) == {str(i) for i in range(1, 38)}, "question set mismatch"
    ms_map = ms_regions()

    doc = fitz.open(QP)
    changes = []
    for num in sorted(qmap, key=int):
        q = qmap[num]
        newq = NEW_QP[num]
        q["qp"] = [{"page": p, "bbox": b} for p, b in newq]
        q["ms"] = [{"page": p, "bbox": b} for p, b in ms_map[num]]
        q["marks"] = 1 if int(num) <= 34 else 2
        q["text"] = extract_text(doc, newq)
        q["uncertain"] = False
        if num in SECTION_FIRST:
            q["notes"] = (f"含本节（{SECTION_FIRST[num]}）共同说明区域（qp[0]）；"
                          f"区域/文字/ms 经视觉核验（2026-10-03，viewer 全帧通过）")
        else:
            q["notes"] = "区域/文字/ms 经视觉核验（2026-10-03，viewer 全帧通过）"
        changes.append({"question": num, "qp": q["qp"], "ms": q["ms"],
                        "marks": q["marks"]})
    doc.close()

    # validations
    for num, q in qmap.items():
        assert 1 <= len(q["qp"]) <= 25 and 1 <= len(q["ms"]) <= 25, num
        for r in q["qp"] + q["ms"]:
            b = r["bbox"]
            assert 0 <= b[0] < b[2] and 0 <= b[1] < b[3], (num, b)
        if not q["text"]:
            print(f"[warn] empty text for Q{num}", file=sys.stderr)

    tmp = IDX.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, IDX)
    new_sha = hashlib.sha256(IDX.read_bytes()).hexdigest()

    report = {"key": "0472/2025/Jun/11", "fixed_at": "2026-10-03",
              "old_sha256": old_sha, "new_sha256": new_sha,
              "qp_regions": sum(len(c["qp"]) for c in changes),
              "ms_regions": sum(len(c["ms"]) for c in changes),
              "changes": changes}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"old sha256: {old_sha}")
    print(f"new sha256: {new_sha}")
    print(f"qp regions={report['qp_regions']} ms regions={report['ms_regions']}")
    print("=" * 100)
    for num in sorted(qmap, key=int):
        q = qmap[num]
        print(f"--- Q{num} marks={q['marks']} qp={[(r['page'], [round(v,1) for v in r['bbox']]) for r in q['qp']]}")
        print(q["text"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
