# -*- coding: utf-8 -*-
"""0472/2026/Jun/41: apply agreed fixes to cie-index.json (finalize before first import).

Fixes (from visual re-check 2026-10-05 + byte-level text alignment probe
work/_text_align_0472_41.txt + work/_ms_geom_0472_41.txt + work/0472_2026_41_browser_notes.md):

QP regions (unrot PDF points):
- Q2 p3: y1 748.4 -> 530.0  (y1 748.4 pulled the page footer in and clipped it;
  [12] bottom is 523.7, +6 margin)
- Q3 p4: y1 414.8 -> 420.0  ([28](b) bottom 413.6, +6.4 margin)
- 3(b) p4: y1 414.8 -> 420.0
- Q1 p2 and 3(a) p4 unchanged.

MS regions (unrot PDF points; page border dX 58.7-733.9 => y 56.0-734.0 with margin):
- Q1: p7 [102.0,56.0,358.5,734.0]; p8 [72.0,56.0,265.0,734.0]; DROP p9 strip (fake)
- Q2: p9 [102.0,56.0,231.0,734.0]; p10 [72.0,56.0,450.0,734.0]; DROP p11 strip (fake)
- Q3: p11 [102.0,56.0,523.0,734.0] (x0 extends to 102.0 to include the
  "Answer Question 3(a) or Question 3(b)" instruction line) + p12 [72.0,56.0,377.5,734.0]
  + p13 [72.0,56.0,364.5,734.0] + p14 [72.0,56.0,290.5,734.0]
  (p12-p14 are shared Task completion / Range / Accuracy tables)
- 3(a): p11 [124.8,56.0,308.4,734.0] + p12/p13/p14 shared tables
- 3(b): p11 [308.4,56.0,523.0,734.0] + p12/p13/p14 shared tables

text (replaces Windows.Media.Ocr transcriptions, per byte-level probe):
- all five questions rewritten with \n line breaks, "• " bullets, en-dash;
  QP p4 bytes confirm "next and why" has NO comma; form fields have colons;
  "friend’s" uses U+2019 (subset-font byte 0x8D).

notes: OCR disclaimer replaced by visual-transcription note; per-question MS
page notes appended.

Backup -> work/0472-2026-Jun-41-index-before-fix.json (first backup preserved)
Report -> work/0472-2026-Jun-41-fix-report.json
Atomic replace; prints old/new sha256. Does NOT touch errors.jsonl.
"""
import hashlib
import json
import os
from pathlib import Path

BR = Path(r"C:/Users/weo/Desktop/api/cie-location-batch")
IDX = BR / "indexes/0472/2026-Jun-41/cie-index.json"
BACKUP = BR / "work/0472-2026-Jun-41-index-before-fix.json"
REPORT = BR / "work/0472-2026-Jun-41-fix-report.json"

OLD_SHA = "098d70339805a4a1ebe1e3e843b17a2644a80e519ec9c189af68ec38e0dfdb47"

OLD_QP = {
    "1": [(2, [71.2, 58.8, 540.4, 500.4])],
    "2": [(3, [70.4, 58.8, 541.2, 748.4])],
    "3": [(4, [70.8, 58.8, 540.4, 414.8])],
    "3(a)": [(4, [70.8, 107.6, 540.4, 278.8])],
    "3(b)": [(4, [70.8, 278.8, 540.4, 414.8])],
}
NEW_QP = {
    "1": [(2, [71.2, 58.8, 540.4, 500.4])],
    "2": [(3, [70.4, 58.8, 541.2, 530.0])],
    "3": [(4, [70.8, 58.8, 540.4, 420.0])],
    "3(a)": [(4, [70.8, 107.6, 540.4, 278.8])],
    "3(b)": [(4, [70.8, 278.8, 540.4, 420.0])],
}

OLD_MS = {
    "1": [(7, [102.0, 61.6, 353.6, 729.2]), (8, [58.4, 63.6, 258.0, 721.6]),
          (9, [58.4, 63.2, 102.0, 729.2])],
    "2": [(9, [102.0, 63.2, 225.6, 729.2]), (10, [58.4, 63.6, 443.2, 721.6]),
          (11, [58.4, 62.0, 124.8, 730.0])],
    "3": [(11, [124.8, 62.0, 554.0, 730.0])],
    "3(a)": [(11, [124.8, 62.0, 308.4, 730.0])],
    "3(b)": [(11, [308.4, 62.0, 554.0, 730.0])],
}
NEW_MS = {
    "1": [(7, [102.0, 56.0, 358.5, 734.0]), (8, [72.0, 56.0, 265.0, 734.0])],
    "2": [(9, [102.0, 56.0, 231.0, 734.0]), (10, [72.0, 56.0, 450.0, 734.0])],
    "3": [(11, [102.0, 56.0, 523.0, 734.0]), (12, [72.0, 56.0, 377.5, 734.0]),
          (13, [72.0, 56.0, 364.5, 734.0]), (14, [72.0, 56.0, 290.5, 734.0])],
    "3(a)": [(11, [124.8, 56.0, 308.4, 734.0]), (12, [72.0, 56.0, 377.5, 734.0]),
             (13, [72.0, 56.0, 364.5, 734.0]), (14, [72.0, 56.0, 290.5, 734.0])],
    "3(b)": [(11, [308.4, 56.0, 523.0, 734.0]), (12, [72.0, 56.0, 377.5, 734.0]),
             (13, [72.0, 56.0, 364.5, 734.0]), (14, [72.0, 56.0, 290.5, 734.0])],
}

NEW_TEXT = {
    "1": ("1 You are Eneida Alves. You want to join a local group to help in your area. "
          "Complete this form.\n"
          "Your name: Eneida Alves\n"
          "Your age:\n"
          "What day you can help:\n"
          "Now give more information.\n"
          "Write about:\n"
          "• where you found out about the group\n"
          "• what activities you can help with\n"
          "• how these activities will help your area.\n"
          "Write 20–30 words.\n"
          "[5]"),
    "2": ("2 Favourite celebration\n"
          "• What is your favourite celebration?\n"
          "• How does your family prepare for this celebration?\n"
          "• Describe what happens during this celebration.\n"
          "• Who would you like to celebrate this event with next year? Explain why.\n"
          "Write 80–90 words.\n"
          "[12]"),
    "3": ("3 Answer Question 3(a) or Question 3(b).\n"
          "Write 130–140 words.\n"
          "(a) Online course\n"
          "You recently started an online course to learn a new skill. "
          "Write an email to your friend about this.\n"
          "• Say what new skill you are learning.\n"
          "• Explain why you wanted to do the course online.\n"
          "• Describe what you did in your first lesson.\n"
          "• Explain how you feel about your progress.\n"
          "• Say what you will do after this course.\n"
          "[28]\n"
          "OR\n"
          "(b) Spending time in another country\n"
          "Your best friend lives abroad. You recently spent a week with them and their family. "
          "Write an article for your school magazine about your trip.\n"
          "• Explain why you decided to visit your best friend.\n"
          "• Describe the area where your friend’s family lives.\n"
          "• Say what you enjoyed most about your visit.\n"
          "• Say what you missed from your country.\n"
          "• Explain where you would like to travel next and why.\n"
          "[28]"),
    "3(a)": ("(a) Online course\n"
             "You recently started an online course to learn a new skill. "
             "Write an email to your friend about this.\n"
             "• Say what new skill you are learning.\n"
             "• Explain why you wanted to do the course online.\n"
             "• Describe what you did in your first lesson.\n"
             "• Explain how you feel about your progress.\n"
             "• Say what you will do after this course.\n"
             "[28]\n"
             "OR"),
    "3(b)": ("(b) Spending time in another country\n"
             "Your best friend lives abroad. You recently spent a week with them and their family. "
             "Write an article for your school magazine about your trip.\n"
             "• Explain why you decided to visit your best friend.\n"
             "• Describe the area where your friend’s family lives.\n"
             "• Say what you enjoyed most about your visit.\n"
             "• Say what you missed from your country.\n"
             "• Explain where you would like to travel next and why.\n"
             "[28]"),
}

NOTE_OLD = "text 来自 Windows.Media.Ocr(zh-Hans-CN) 转录，可能有识别噪声"
NOTE_NEW = "text 按原件目视转录（替代 OCR 噪声）"
NOTE_APPEND = {
    "1": "；ms p7–p8 为 Q1 评分表（p8 为 3/2/1/0 分带表）",
    "2": "；ms p9–p10 为 Q2 评分表（p10 为分带表）",
    "3": "；ms p11–p14 为 Q3 评分内容（p12–p14 为 Task completion / Range / Accuracy 共用评分表）",
    "3(a)": "；ms p12–p14 为 3(a)/3(b) 共用评分表（Task completion / Range / Accuracy），与另一子题引用同一区域",
    "3(b)": "；ms p12–p14 为 3(a)/3(b) 共用评分表（Task completion / Range / Accuracy），与另一子题引用同一区域",
}


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

    # --- 1. verify old QP, then replace ---------------------------------
    for name, expected in OLD_QP.items():
        q = qs[name]
        got = [(r["page"], list(r["bbox"])) for r in q["qp"]]
        assert got == expected, f"{name} old qp mismatch:\n got={got}\n exp={expected}"
    for name, new in NEW_QP.items():
        q = qs[name]
        old = [(r["page"], list(r["bbox"])) for r in q["qp"]]
        for (op, ob), (np_, nb) in zip(old, new):
            if op == np_ and ob != nb:
                rec(f"QP {name} p{op}: {ob} -> {nb}")
        q["qp"] = [{"page": p, "bbox": b} for p, b in new]

    # --- 2. verify old MS, then replace ---------------------------------
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

    # --- 3. text ---------------------------------------------------------
    for name, new_text in NEW_TEXT.items():
        q = qs[name]
        old_text = q["text"]
        assert old_text != new_text, f"{name} text unchanged (already fixed?)"
        q["text"] = new_text
        rec(f"text {name}: replaced ({len(old_text)} -> {len(new_text)} chars)")

    # --- 4. notes --------------------------------------------------------
    for name, suffix in NOTE_APPEND.items():
        q = qs[name]
        assert NOTE_OLD in q["notes"], (name, q["notes"])
        assert "共用评分表" not in q["notes"] and "评分表（p8" not in q["notes"], name
        q["notes"] = q["notes"].replace(NOTE_OLD, NOTE_NEW) + suffix
        rec(f"notes {name}: rewritten")

    # --- validations -----------------------------------------------------
    assert len(index["questions"]) == 5, len(index["questions"])
    for q in index["questions"]:
        assert 1 <= len(q["qp"]) <= 25 and 0 <= len(q["ms"]) <= 25, q["question"]
        for r in q["qp"]:
            b = r["bbox"]
            assert 1 <= r["page"] <= 8, (q["question"], r["page"])
            assert 0 < b[0] < b[2] <= 612 and 0 < b[1] < b[3] <= 792, (q["question"], r["page"], b)
        for r in q["ms"]:
            b = r["bbox"]
            assert 1 <= r["page"] <= 14, (q["question"], r["page"])
            assert b[1] == 56.0 and b[3] == 734.0, (q["question"], r["page"], b)
            assert 0 < b[0] < b[2] <= 612, (q["question"], r["page"], b)
    ms_n = sum(len(q["ms"]) for q in index["questions"])
    qp_n = sum(len(q["qp"]) for q in index["questions"])
    assert (qp_n, ms_n) == (5, 16), (qp_n, ms_n)

    tmp = IDX.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, IDX)
    new_sha = hashlib.sha256(IDX.read_bytes()).hexdigest()

    report = {
        "key": "0472/2026/Jun/41",
        "fixed_at": "2026-10-05",
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
