# -*- coding: utf-8 -*-
"""0472/2025/Jun/12: rebuild cie-index.json from text-layer evidence.

Fixes (window 104-105, coordinate evidence from work/0472-12-lines*.txt):
- Q1: add section head region p3 [58.8,144.4] as qp[0] (Questions 1-8 + intro + "You are at a large cinema.")
- Q8/Q14/Q19/Q28/Q34: drop mis-attached section-header region (moved to next question)
- Q9/Q15/Q20/Q29/Q35: gain that header as qp[0]
- Q24: bottom 345.4 (stop before "Part 2" head, keep [PAUSE])
- Q25: head region [345.4,425.2] (Part 2 head + instructions) + body [425.2,565.2]
- Q23..Q26: x1 522.4 -> 542.4 (include right-side [1] marks)
- all QP regions: x1 unified to 542.4 (covers 541.8 long lines and 539.0 [1]/[2])
- ms: rebuild all 37 regions from MS row table (p2 Q1-28, p3 Q29-37, x=[71.7,538.8])
- marks: Q1-34=1, Q35-37=2 (from MS Marks column)
- text: rebuilt from QP text layer per new regions; [Total:] dropped; [PAUSE]/[1]/[2] kept;
  dot answer lines (Q15-19 "..........") kept; end-of-paper instructions dropped
- uncertain=false; notes rewritten to record visual verification

Backup -> work/0472-2025-12-index-before-fix.json
Report -> work/0472-2025-12-fix-report.json
"""
import hashlib
import json
import os
import re
import sys
from pathlib import Path

import pymupdf as fitz

BR = Path(r"C:/Users/weo/Desktop/api/cie-location-batch")
IDX = BR / "indexes/0472/2025-Jun-12/cie-index.json"
QP = BR / "tmp/0472/2025-Jun-12/0472_s25_qp_12.pdf"
BACKUP = BR / "work/0472-2025-12-index-before-fix.json"
REPORT = BR / "work/0472-2025-12-fix-report.json"
OLD_SHA = "bf451a912f1d8b668d15045439286979d3131edf5b6a7ca3d76282e2b442c2e1"

X0, X1 = 70.4, 542.4
NEW_QP = {
    "1":  [(3, [X0, 58.8, X1, 144.4]), (3, [X0, 144.4, X1, 368.4])],
    "2":  [(3, [X0, 368.4, X1, 761.6])],
    "3":  [(4, [X0, 58.8, X1, 282.8])],
    "4":  [(4, [X0, 282.8, X1, 506.4])],
    "5":  [(4, [X0, 506.4, X1, 759.6])],
    "6":  [(5, [X0, 58.8, X1, 282.8])],
    "7":  [(5, [X0, 282.8, X1, 506.4])],
    "8":  [(5, [X0, 506.4, X1, 761.6])],
    "9":  [(6, [X0, 58.8, X1, 163.2]), (6, [X0, 163.2, X1, 359.2])],
    "10": [(6, [X0, 359.2, X1, 554.8])],
    "11": [(6, [X0, 554.8, X1, 759.6])],
    "12": [(7, [X0, 58.8, X1, 258.4])],
    "13": [(7, [X0, 258.4, X1, 458.0])],
    "14": [(7, [X0, 458.0, X1, 761.6])],
    "15": [(8, [X0, 58.8, X1, 459.6]), (8, [X0, 459.6, X1, 496.4])],
    "16": [(8, [X0, 496.4, X1, 533.2])],
    "17": [(8, [X0, 533.2, X1, 570.0])],
    "18": [(8, [X0, 570.0, X1, 606.4])],
    "19": [(8, [X0, 606.4, X1, 759.6])],
    "20": [(9, [X0, 58.8, X1, 205.6]), (9, [X0, 205.6, X1, 346.0])],
    "21": [(9, [X0, 346.0, X1, 486.0])],
    "22": [(9, [X0, 486.0, X1, 761.6])],
    "23": [(10, [X0, 58.8, X1, 199.2])],
    "24": [(10, [X0, 199.2, X1, 345.4])],
    "25": [(10, [X0, 345.4, X1, 425.2]), (10, [X0, 425.2, X1, 565.2])],
    "26": [(10, [X0, 565.2, X1, 759.6])],
    "27": [(11, [X0, 58.8, X1, 199.2])],
    "28": [(11, [X0, 199.2, X1, 761.6])],
    "29": [(12, [X0, 58.8, X1, 168.8]), (12, [X0, 168.8, X1, 338.8])],
    "30": [(12, [X0, 338.8, X1, 509.2])],
    "31": [(12, [X0, 509.2, X1, 759.6])],
    "32": [(13, [X0, 58.8, X1, 228.8])],
    "33": [(13, [X0, 228.8, X1, 399.2])],
    "34": [(13, [X0, 399.2, X1, 761.6])],
    "35": [(14, [X0, 58.8, X1, 168.8]), (14, [X0, 168.8, X1, 364.0])],
    "36": [(14, [X0, 364.0, X1, 759.6])],
    "37": [(15, [X0, 64.0, X1, 759.6])],
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
    if old_sha != OLD_SHA:
        raise SystemExit(f"unexpected old sha256 {old_sha} != {OLD_SHA}")
    if not BACKUP.exists():
        BACKUP.write_bytes(old_bytes)
        print(f"backup written: {BACKUP.name}")
    else:
        print(f"backup exists (kept): {BACKUP.name}")

    index = json.loads(old_bytes.decode("utf-8"))
    qmap = {q["question"]: q for q in index["questions"]}
    assert set(qmap) == {str(i) for i in range(1, 38)}, "question set mismatch"
    for q in qmap.values():
        assert q["parent"] is None, q["question"]
    ms_map = ms_regions()

    doc = fitz.open(QP)
    changes = []
    for num in sorted(qmap, key=int):
        q = qmap[num]
        newq = NEW_QP[num]
        q["qp"] = [{"page": p, "bbox": list(b)} for p, b in newq]
        q["ms"] = [{"page": p, "bbox": list(b)} for p, b in ms_map[num]]
        q["marks"] = 1 if int(num) <= 34 else 2
        q["text"] = extract_text(doc, newq)
        q["uncertain"] = False
        if num in SECTION_FIRST:
            q["notes"] = (f"含本节（{SECTION_FIRST[num]}）共同说明区域（qp[0]）；"
                          f"区域/文字/ms 经视觉核验（2026-10-03，viewer 全帧通过）")
        else:
            q["notes"] = "区域/文字/ms 经视觉核验（2026-10-03，viewer 全帧通过）"
        changes.append({"question": num, "qp": q["qp"], "ms": q["ms"],
                        "marks": q["marks"], "text": q["text"]})
    doc.close()

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

    report = {"key": "0472/2025/Jun/12", "fixed_at": "2026-10-03",
              "old_sha256": old_sha, "new_sha256": new_sha,
              "qp_regions": sum(len(c["qp"]) for c in changes),
              "ms_regions": sum(len(c["ms"]) for c in changes),
              "changes": changes}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"old sha256: {old_sha}")
    print(f"new sha256: {new_sha}")
    print(f"qp regions={report['qp_regions']} ms regions={report['ms_regions']}")
    print("=" * 100)
    for c in changes:
        num = c["question"]
        print(f"--- Q{num} marks={c['marks']} qp={[(r['page'], [round(v,1) for v in r['bbox']]) for r in c['qp']]}")
        print(c["text"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
