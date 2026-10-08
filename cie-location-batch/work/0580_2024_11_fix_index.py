# -*- coding: utf-8 -*-
"""0580/2024/Jun/11: apply agreed fixes to cie-index.json after browser visual verification.

Fixes (from browser frame review 2026-10-04/05, notes in work/0580_2024_11_browser_notes.md):
- MS regions: M14 extend 475.7 -> 510.6 (Q14 A1 row "3 nfww" confirmed by tight crop);
  M22 extend 365.3 -> 428.3 (x=5 / y=-0.5 A1 rows confirmed by tight crop).
- QP/MS text: repair garbled text-layer readings (fractions, operators, exponents, cm²).
- All 42 questions: uncertain true -> false, notes rewritten to post-verification text.

Backup -> work/0580-2024-Jun-11-index-before-fix.json
Report -> work/0580-2024-Jun-11-fix-report.json
Atomic replace; prints old/new sha256.
"""
import hashlib
import json
import os
from pathlib import Path

BR = Path(r"C:/Users/weo/Desktop/api/cie-location-batch")
IDX = BR / "indexes/0580/2024-Jun-11/cie-index.json"
BACKUP = BR / "work/0580-2024-Jun-11-index-before-fix.json"
REPORT = BR / "work/0580-2024-Jun-11-fix-report.json"

MARKERS = ("未做视觉核验", "未视觉核验", "未做视觉", "PAGE_NOT_READY",
           "没有做视觉核验", "视觉核验未完成", "未做 page.visual.snapshot")

MS_BBOX_FIXES = {
    "14": ([72.6, 437.1, 539.3, 475.7], [72.6, 437.1, 539.3, 510.6]),
    "22": ([72.6, 342.4, 539.3, 365.3], [72.6, 342.4, 539.3, 428.3]),
}

TEXT_SUBS = {
    "3": [("14 12 10 Distance 8 (km) 6 4 2 0 14 00 14 30 15 00 15 30 16 00 Time ", "")],
    "5": [("1 cm2 grid", "1 cm² grid"), ("cm2 [1]", "cm² [1]")],
    "6": [("28 - 16 ' 2", "28 − 16 ÷ 2"),
          ("Find the reciprocal of 5 4.", "Find the reciprocal of 4/5.")],
    "6(a)": [("28 - 16 ' 2", "28 − 16 ÷ 2")],
    "6(b)": [("Find the reciprocal of 5 4.", "Find the reciprocal of 4/5.")],
    "9": [("9 y 8 7 6 A 5 4 3 C 2 1 B – 8 – 7 – 6 – 5 – 4 – 3 – 2 – 1 0 1 2 3 4 5 x – 1 – 2 The diagram",
           "9 The diagram")],
    "10": [("369 cm2", "369 cm²")],
    "12": [("60 – 4n", "60 − 4n"), ("n2 – 300", "n² − 300")],
    "13": [("y = 3 x - crosses the y-axis. 5", "y = 3x − 5 crosses the y-axis.")],
    "14": [("28 2 - 5 6 4 2 # 1 68", "(28.2 − 5.6) / (4.2 × 1.68)")],
    "15": [("36 x 2 + 40 x", "36x² + 40x")],
    "16": [("3 x - 12", "3x − 12"),
           ("length x 3 - 12 and width x + . 7", "length 3x − 12 and width x + 7")],
    "19": [("3 343 - 40 96", "∛343 − √40.96"),
           ("( 192 + 4 # 16 ) .1 25", "(192 + 4 × 16)^1.25")],
    "19(a)": [("3 343 - 40 96", "∛343 − √40.96")],
    "19(b)": [("( 192 + 4 # 16 ) .1 25", "(192 + 4 × 16)^1.25")],
    "20": [("value of 1370.", "value of 137⁰."),
           ("7 12 ' 7 p = 7 17", "7¹² ÷ 7ᵖ = 7¹⁷")],
    "20(a)": [("value of 1370.", "value of 137⁰.")],
    "20(b)": [("7 12 ' 7 p = 7 17", "7¹² ÷ 7ᵖ = 7¹⁷")],
    "21": [(".1 827 # 10 6 ' 9000", "1.827 × 10⁶ ÷ 9000")],
    "25": [("cm2 [3]", "cm² [3]")],
    "25(a)": [("cm2 [3]", "cm² [3]")],
}

NOTES = {
    "1": "浏览器快照目视核验通过：父区含 (a)(b)(c) 三小问，下缘止于 (c) 的 [1]，未混入 Q2。",
    "1(a)": "浏览器快照目视核验通过：子区完整，未混入 (b)。",
    "1(b)": "浏览器快照目视核验通过：子区完整，未混入 (c)。",
    "1(c)": "浏览器快照目视核验通过：子区完整，未混入 Q2。",
    "2": "浏览器快照目视核验通过：线段 AB 图完整，答案线与 mm [1] 在位，未混入 Q3。",
    "3": "浏览器快照目视核验通过：父区含行程图（坐标轴完整）与 (a)(b)，下缘未混入 Q4。",
    "3(a)": "浏览器快照目视核验通过：子区完整（距离问题 + km [1]）。",
    "3(b)": "浏览器快照目视核验通过：子区完整（停留时间问题 + min [1]）。",
    "4": "浏览器快照目视核验通过：题干、答案线与 [1] 完整，区域内无其他题。",
    "5": "浏览器快照目视核验通过：网格图完整（图形与网格未截断），cm² 标注确认。",
    "6": "浏览器快照目视核验通过：共同题干可见；6(b) 分数 4/5 经 MS 6(b)=1.25=5/4 交叉确认。",
    "6(a)": "浏览器快照目视核验通过：28 − 16 ÷ 2 与答案线 [1] 完整。",
    "6(b)": "浏览器快照目视核验通过：分数 4/5 已确认（与 MS 6(b)=1.25 交叉验证一致）。",
    "7": "浏览器快照目视核验通过：题干、答案线与 °C [1] 完整。",
    "8": "浏览器快照目视核验通过：十字图形完整未截断，[2] 在位。",
    "9": "浏览器快照目视核验通过：坐标系图完整（A、B、C 与两线段可见）；答案经 MS 9=(−3, 7) 交叉确认。",
    "10": "浏览器快照目视核验通过：长方体图三标注齐全，369 cm² 与 [4] 完整；单题无子问。",
    "11": "浏览器快照目视核验通过：父区含 (a)(b) 与表格，未混入 Q12。",
    "11(a)": "浏览器快照目视核验通过：子区完整；答案经 MS 11(a)=0.4 交叉确认。",
    "11(b)": "浏览器快照目视核验通过：表格区完整；答案经 MS 11(b)=42 及 0.2/0.2 交叉确认。",
    "12": "浏览器快照目视核验通过：表格（60 − 4n / n² − 300）完整；单题无子问；MS 12=40/−275。",
    "13": "浏览器快照目视核验通过：y = 3x − 5 与坐标答案格式完整；MS 13=(0, −5)。",
    "14": "浏览器快照目视核验通过：分数式 (28.2 − 5.6)/(4.2 × 1.68) 完整；MS 14 两行（(30−6)/(4×2) M1 与 3 nfww A1）已在加长区域确认。",
    "15": "浏览器快照目视核验通过：36x² + 40x 完整；MS 15=4x(9x+10)。",
    "16": "浏览器快照目视核验通过：矩形图与 3x − 12 / x + 7 标注完整；MS 16=8x−10 or 2(4x−5)。",
    "17": "浏览器快照目视核验通过：父区含圆图（O、P、OP 线段）与 (a)(b)；圆图为 17(b) 绘图所依，由子题继承。",
    "17(a)": "浏览器快照目视核验通过：子区完整；MS 17(a)=radius。",
    "17(b)": "浏览器快照目视核验通过：子区完整；绘图所依圆图在父区（继承）；MS 17(b)=过 P 垂直于 OP 的直线。",
    "18": "浏览器快照目视核验通过：题干与答案线 [2] 完整；MS 18=35。",
    "19": "浏览器快照目视核验通过：父区含 (a)(b)；19(b) 运算符 + 经 MS 19(b)=1024 交叉确认。",
    "19(a)": "浏览器快照目视核验通过：∛343 − √40.96 完整；MS 19(a)=0.6 or 3/5。",
    "19(b)": "浏览器快照目视核验通过：运算符 + 已确认（(192 + 4 × 16)^1.25 = 1024 与 MS 一致）。",
    "20": "浏览器快照目视核验通过：父区含 (a)(b)，指数记号完整。",
    "20(a)": "浏览器快照目视核验通过：137⁰ 完整；MS 20(a)=1。",
    "20(b)": "浏览器快照目视核验通过：7¹² ÷ 7ᵖ = 7¹⁷ 完整；MS 20(b)=−5。",
    "21": "浏览器快照目视核验通过：指数 6 已确认（1.827 × 10⁶ ÷ 9000 = 203）；MS 21=2.03×10² cao。",
    "22": "浏览器快照目视核验通过：联立方程两式与 x/y 答案行完整；MS 22 三行（M1 eliminating one variable、A1 x=5、A1 y=−0.5）已在加长区域确认。",
    "23": "浏览器快照目视核验通过：9.6 km/h → m/s 完整；MS 23=2⅔ or 2.67。",
    "24": "浏览器快照目视核验通过：序列 11 18 25 32 39 完整；MS 24=7n+4。",
    "25": "浏览器快照目视核验通过：父区含图形（J/K/L、12.8 cm 两处、半圆弧）与 (a)(b)；cm² 标注确认。",
    "25(a)": "浏览器快照目视核验通过：子区完整；MS 25(a)=146 或 146.2–146.3。",
    "25(b)": "浏览器快照目视核验通过：子区完整；MS 25(b)=51[.0]。",
}

EXPECTED = ["1", "1(a)", "1(b)", "1(c)", "2", "3", "3(a)", "3(b)", "4", "5", "6", "6(a)",
            "6(b)", "7", "8", "9", "10", "11", "11(a)", "11(b)", "12", "13", "14", "15",
            "16", "17", "17(a)", "17(b)", "18", "19", "19(a)", "19(b)", "20", "20(a)",
            "20(b)", "21", "22", "23", "24", "25", "25(a)", "25(b)"]


def main() -> int:
    old_sha = hashlib.sha256(IDX.read_bytes()).hexdigest()
    index = json.loads(IDX.read_text(encoding="utf-8"))
    changes: list[str] = []

    def rec(msg: str) -> None:
        changes.append(msg)
        print(msg)

    if not BACKUP.exists():
        BACKUP.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
        rec(f"backup written: {BACKUP.name}")
    else:
        rec(f"backup already exists, kept: {BACKUP.name}")

    questions = index["questions"]
    qs = {q["question"]: q for q in questions}
    assert len(questions) == len(qs) == 42, len(questions)
    assert [q["question"] for q in questions] == EXPECTED

    # 1. MS bbox fixes
    for qid, (old_b, new_b) in MS_BBOX_FIXES.items():
        q = qs[qid]
        assert len(q["ms"]) == 1, qid
        region = q["ms"][0]
        assert region["bbox"] == old_b, (qid, region["bbox"])
        region["bbox"] = list(new_b)
        rec(f"MS bbox {qid} p{region['page']}: {old_b} -> {new_b}")

    # 2. text fixes
    for qid, subs in TEXT_SUBS.items():
        q = qs[qid]
        old_text = q["text"]
        new_text = old_text
        for old_s, new_s in subs:
            n = new_text.count(old_s)
            assert n == 1, (qid, old_s, n)
            new_text = new_text.replace(old_s, new_s)
        q["text"] = new_text
        rec(f"text {qid}: {old_text!r} -> {new_text!r}")

    # 3. uncertain false + notes rewritten
    for qid in EXPECTED:
        q = qs[qid]
        assert q["uncertain"] is True, qid
        q["uncertain"] = False
        q["notes"] = NOTES[qid]
        rec(f"notes {qid}: rewritten, uncertain -> false")

    # validations
    for q in questions:
        assert q["uncertain"] is False, q["question"]
        assert q["notes"] and not any(m in q["notes"] for m in MARKERS), q["question"]
        for r in q["qp"] + q["ms"]:
            b = r["bbox"]
            assert 0 <= b[0] < b[2] and 0 <= b[1] < b[3], (q["question"], b)
        for r in q["ms"]:
            assert r["bbox"][0] == 72.6 and r["bbox"][2] == 539.3, (q["question"], r["bbox"])
        assert 1 <= len(q["qp"]) <= 25 and 0 <= len(q["ms"]) <= 25, q["question"]
    qp_regions = sum(len(q["qp"]) for q in questions)
    ms_regions = sum(len(q["ms"]) for q in questions)
    leaf_marks = sum(q["marks"] for q in questions if q["marks"] is not None)
    assert qp_regions == 42, qp_regions
    assert ms_regions == 34, ms_regions
    assert leaf_marks == 56, leaf_marks

    tmp = IDX.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, IDX)
    new_sha = hashlib.sha256(IDX.read_bytes()).hexdigest()
    json.loads(IDX.read_text(encoding="utf-8"))

    report = {
        "key": "0580/2024/Jun/11",
        "fixed_at": "2026-10-05",
        "old_sha256": old_sha,
        "new_sha256": new_sha,
        "questions": len(questions),
        "qp_regions": qp_regions,
        "ms_regions": ms_regions,
        "leaf_marks": leaf_marks,
        "text_fixed": sorted(TEXT_SUBS),
        "ms_bbox_fixed": {k: {"old": v[0], "new": v[1]} for k, v in MS_BBOX_FIXES.items()},
        "notes_rewritten": 42,
        "changes": changes,
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")

    print("=" * 100)
    print(f"questions={len(questions)} qp_regions={qp_regions} ms_regions={ms_regions} "
          f"leaf_marks={leaf_marks}")
    print(f"old sha256: {old_sha}")
    print(f"new sha256: {new_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
