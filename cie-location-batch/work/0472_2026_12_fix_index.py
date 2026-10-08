# -*- coding: utf-8 -*-
"""0472/2026/Jun/12: rebuild cie-index.json from PDF text-layer coordinates.

Defects found in the Oct-1 draft index (37 questions, OCR-based):
- ms=[] for Q1-19 and Q21 (MS p2/p3 answer-table rows exist for every question).
- QP regions were OCR approximations that cut the [1]/[2] marks and option D column
  (e.g. Q1 x1=528.8; [1] right-aligned to x539.0).
- Q8 wrongly spanned p5-p6 (p6 y34.8-164.4 is actually the Questions 9-14 section
  header block); Q34 wrongly spanned p13-p14 (p14 y58.8-168.8 is Questions 35-37).
- text was noisy OCR ("tO you", "a re", "9 Questions 20 h 28" ...); marks null.
- section-intro blocks (Questions 1-8 / 9-14 / 15-19 / 20-28 incl. Part 1 /
  Part 2 / 29-34 / 35-37) were not modelled as separate qp[0] regions.

Rebuild rules (verified against work/0472_2026_12_probe.json, extracted from the
downloaded originals; conventions matched to the already-verified 0472/2026/Jun/11):
- qp regions: x=[70.4,541.2]; first line top -0.3 .. next question start -0.3;
  last question on a page ends 2.0pt after its last content ([1]/[2]/[Total]/[PAUSE]);
  section-intro blocks become qp[0] of the section's first question.
- ms regions: MS answer-table row cells, x=[71.7,538.8],
  top = row_y0 - 5.7, bottom = next row_y0 - 5.7 (last row: row_y0 + 12.0).
- marks: 1 for Q1-34, 2 for Q35-37 (per MS table).
- text: faithful transcription of the text layer.

Backup -> work/0472-2026-Jun-12-index-before-fix.json
Report -> work/0472-2026-Jun-12-fix-report.json
Atomic replace; prints old/new sha256. Does NOT touch errors.jsonl.
"""
import hashlib
import json
import os
from pathlib import Path

BR = Path(r"C:/Users/weo/Desktop/api/cie-location-batch")
IDX = BR / "indexes/0472/2026-Jun-12/cie-index.json"
BACKUP = BR / "work/0472-2026-Jun-12-index-before-fix.json"
REPORT = BR / "work/0472-2026-Jun-12-fix-report.json"
PROBE = BR / "work/0472_2026_12_probe.json"

OLD_SHA = "6a30265d63f919579be98124444da5ddd4beffff1f5f6b7a58f3146a06f345e6"
OLD_QS = [str(n) for n in range(1, 38)]

# (page, y0, y1) — x always [70.4, 541.2]
QP_REGIONS = {
    "1": [(3, 58.8, 144.4), (3, 144.4, 365.3)],
    "2": [(3, 365.3, 563.5)],
    "3": [(4, 58.8, 279.8)],
    "4": [(4, 279.8, 500.7)],
    "5": [(4, 500.7, 698.9)],
    "6": [(5, 58.8, 279.8)],
    "7": [(5, 279.8, 500.7)],
    "8": [(5, 500.7, 723.3)],
    "9": [(6, 58.8, 164.2), (6, 164.2, 355.7)],
    "10": [(6, 355.7, 547.2)],
    "11": [(6, 547.2, 733.9)],
    "12": [(7, 58.8, 253.4)],
    "13": [(7, 253.4, 448.1)],
    "14": [(7, 448.1, 644.3)],
    "15": [(8, 58.8, 485.3), (8, 485.3, 522.0)],
    "16": [(8, 522.0, 558.7)],
    "17": [(8, 558.7, 595.4)],
    "18": [(8, 595.4, 632.0)],
    "19": [(8, 632.0, 682.6)],
    "20": [(9, 58.8, 217.8), (9, 217.8, 348.0)],
    "21": [(9, 348.0, 478.3)],
    "22": [(9, 478.3, 585.7)],
    "23": [(10, 58.8, 189.1)],
    "24": [(10, 189.1, 331.6)],
    "25": [(10, 331.6, 404.9), (10, 404.9, 535.2)],
    "26": [(10, 535.2, 642.6)],
    "27": [(11, 58.8, 189.1)],
    "28": [(11, 189.1, 321.0)],
    "29": [(12, 58.8, 168.8), (12, 168.8, 326.2)],
    "30": [(12, 326.2, 483.6)],
    "31": [(12, 483.6, 654.9)],
    "32": [(13, 58.8, 216.2)],
    "33": [(13, 216.2, 373.6)],
    "34": [(13, 373.6, 532.6)],
    "35": [(14, 58.8, 168.8), (14, 168.8, 353.3)],
    "36": [(14, 353.3, 515.0)],
    "37": [(15, 64.3, 278.1)],
}

TEXT = {
    "1": "Questions 1\u20138 You will hear some short recordings. You will hear each recording twice. "
         "For Questions 1\u20138, tick the correct box (A\u2013D). You are at a bus station with a friend. "
         "1 Your friend says something to you. What does your friend want to buy? A B C D [1]",
    "2": "2 You are at the information desk at the bus station. Your friend asks the assistant something. "
         "Which bus number are you and your friend taking? 15 23 46 78 A B C D [1]",
    "3": "3 The assistant at the information desk says something to you and your friend. "
         "What time does your bus leave? A B C D [1]",
    "4": "4 You are waiting for the bus. Your friend says something to you. "
         "What is the weather like today? A B C D [1]",
    "5": "5 You are getting onto the bus. The driver says something to you. "
         "How much does your ticket cost? \u00a30.90 \u00a31.20 \u00a32.10 \u00a33.40 A B C D [1]",
    "6": "6 You are sitting on the bus. Your friend says something to you. "
         "What can your friend see from the window? A B C D [1]",
    "7": "7 Your friend says something else to you. What would your friend like to do later today? A B C D [1]",
    "8": "8 You are getting off the bus. A passenger says something to you. "
         "What did you nearly leave on the bus? A B C D [1] [Total: 8]",
    "9": "Questions 9\u201314 You will hear an announcement about a tour of an ice cream factory. "
         "You will hear the announcement twice. There will be a pause during the announcement. "
         "For Questions 9\u201314, tick the correct box (A\u2013D). You now have some time to read the questions. "
         "Tour of an ice cream factory 9 Visitors can leave their bags in a large cupboard by the \u2026 A B C D [1]",
    "10": "10 Everyone on the tour must wear \u2026 A B C D [1]",
    "11": "11 The flavour of the ice cream that the factory is making today is \u2026 A B C D [1] [PAUSE]",
    "12": "12 The ice cream factory first opened in \u2026 1959 1961 1972 1984 A B C D [1]",
    "13": "13 At the end of the tour, visitors can taste some of the ice cream in room \u2026 GA TR HP QC A B C D [1]",
    "14": "14 Everyone on the tour will get a free \u2026 A B C D [1] [Total: 6]",
    "15": "Questions 15\u201319 You will hear two teenagers, Rashida and Alberto, talking about caf\u00e9s in their town. "
          "You will hear the conversation twice. For Questions 15\u201319, choose the information (A\u2013F) that matches each cafe. "
          "For each cafe, write the correct letter (A\u2013F) on the answer line. Use each letter only once. "
          "There is one extra letter which you do not need to use. You now have some time to read the information below. "
          "Information A It has the best snacks in town. B The staff are very friendly there. "
          "C It\u2019s very expensive. D It\u2019s a great place to go before lessons. "
          "E It gets very busy. F It\u2019s usually quite dirty. "
          "Caf\u00e9s 15 The Coffee House ...................",
    "16": "16 Mario\u2019s Lounge ...................",
    "17": "17 Helena\u2019s Place ...................",
    "18": "18 Feeling Thirsty? ...................",
    "19": "19 The Cup and Spoon ................... [5] [Total: 5]",
    "20": "Questions 20\u201328 You will hear two interviews, one with Veronika and one with Haruto. "
          "They are talking about photography. There will be a pause between the two interviews. "
          "Part 1: Questions 20\u201324 You will now hear the interview with Veronika twice. "
          "For Questions 20\u201324, tick the correct box (A\u2013C). You now have some time to read the questions. "
          "20 Veronika became interested in photography after A talking to a friend. "
          "B watching a TV programme. C having lessons about it. [1]",
    "21": "21 Veronika prefers taking photographs of A people. B animals. C places. [1]",
    "22": "22 What prize did Veronika win in a photography competition? A a calendar B a book C a poster [1]",
    "23": "23 Veronika uses special software on her photos A to change the colours in them. "
          "B to make them clearer. C to remove things from them. [1]",
    "24": "24 In the future, Veronika would like to A have an exhibition of her photos. "
          "B take photos for news websites. C teach others how to take photos. [1] [PAUSE]",
    "25": "Part 2: Questions 25\u201328 You will now hear the interview with Haruto twice. "
          "For Questions 25\u201328, tick the correct box (A\u2013C). You now have some time to read the questions. "
          "25 Who does Haruto most often go out with to photograph things? A a neighbour B a classmate C a relative [1]",
    "26": "26 Haruto joined a photography club because A a friend was already a member. "
          "B he knew he needed to improve. C it took members on good trips. [1]",
    "27": "27 Haruto\u2019s photo that appeared in the school magazine showed A some birds. B a waterfall. C several students. [1]",
    "28": "28 What does Haruto say about his new camera? A Learning how it works is difficult. "
          "B It\u2019s heavier than he expected. C He can use it safely when it\u2019s wet. [1] [Total: 9]",
    "29": "Questions 29\u201334 You will hear Agatha telling her friend Reuben about climbing a mountain in Africa "
          "called Kilimanjaro. You will hear the conversation twice. There will be a pause during the conversation. "
          "For Questions 29\u201334, tick the correct box (A\u2013D). You now have some time to read the questions. "
          "29 Agatha chose a guide to take her up Kilimanjaro by \u2026 A reading different online reviews. "
          "B asking other climbers for recommendations. C enquiring at the tourist information office. "
          "D visiting each guide\u2019s website. [1]",
    "30": "30 Agatha says the most useful training for climbing Kilimanjaro was \u2026 "
          "A cycling long distances with friends. B running to and from work. "
          "C walking up hills in her local area. D using a step machine at the gym. [1]",
    "31": "31 How did Agatha feel as she was setting off up Kilimanjaro? "
          "A worried she wouldn\u2019t get to the top B curious about how hard the climb would be "
          "C surprised by how heavy her backpack was D relieved to finally start the climb [1] [PAUSE]",
    "32": "32 What did Agatha find most challenging about the climb up Kilimanjaro? "
          "A dealing with the cold B being frightened in high places "
          "C having to walk quite quickly D getting very little sleep [1]",
    "33": "33 What did Agatha most enjoy about getting to the top of Kilimanjaro? "
          "A the feeling of success B the view from the top C the chance to have a rest "
          "D the celebrations in her group [1]",
    "34": "34 In the future, Agatha would like to \u2026 A climb the highest mountains in her own country. "
          "B walk across a whole continent. C take part in a long-distance swim. "
          "D explore underground caves. [1] [Total: 6]",
    "35": "Questions 35\u201337 You will hear a radio interview with a young songwriter called Alex. "
          "You will hear the interview twice. There will be two pauses during the interview. "
          "For each Question (35\u201337), choose two true statements (A\u2013E) and tick the correct boxes. "
          "You now have some time to read the questions. "
          "35 A Alex is one of several children. B Alex has always enjoyed performing music. "
          "C The first instrument Alex learned was the piano. D Alex played in the band at school. "
          "E Alex studied music at college. [2] [PAUSE]",
    "36": "36 A Alex usually writes songs using a computer. B Alex finds words harder to write than music. "
          "C Alex plays all the instruments on his recordings. D Alex sometimes gets embarrassed by his singing. "
          "E Alex only plays his songs to others when they\u2019re finished. [2] [PAUSE]",
    "37": "37 A Alex has recently joined a new band. B Alex will play at a large music festival soon. "
          "C Alex has written songs for other musicians to perform. D Alex wants to write music for films in the future. "
          "E Alex is building his own recording studio. [2] [Total: 6]",
}

MARKS = {str(n): (2 if n >= 35 else 1) for n in range(1, 38)}

BASE_NOTE = "\u533a\u57df\u6309 PDF \u6587\u5b57\u5c42\u5750\u6807\u5b9a\u7a3f\uff082026-10-04\uff09\uff1bms \u4e3a MS \u7b54\u6848\u8868\u5bf9\u5e94\u884c"
INTRO_NOTES = {
    "1": "\u542b\u672c\u8282\uff081\u20138\uff09\u5171\u540c\u8bf4\u660e\u533a\u57df\uff08qp[0]\uff09\uff1b",
    "9": "\u542b\u672c\u8282\uff089\u201314\uff09\u5171\u540c\u8bf4\u660e\u533a\u57df\uff08qp[0]\uff0c\u542b\u6807\u9898 Tour of an ice cream factory\uff09\uff1b",
    "15": "\u542b\u672c\u8282\uff0815\u201319\uff09\u5171\u540c\u8bf4\u660e\u533a\u57df\uff08qp[0]\uff0c\u542b Information A\u2013F \u4e0e Caf\u00e9s \u6807\u9898\uff09\uff1b",
    "20": "\u542b\u672c\u8282\uff0820\u201328\uff09\u5171\u540c\u8bf4\u660e\u533a\u57df\uff08qp[0]\uff0c\u542b Part 1 \u8bf4\u660e\uff09\uff1b",
    "25": "\u542b Part 2 \u8bf4\u660e\u533a\u57df\uff08qp[0]\uff09\uff1b",
    "29": "\u542b\u672c\u8282\uff0829\u201334\uff09\u5171\u540c\u8bf4\u660e\u533a\u57df\uff08qp[0]\uff09\uff1b",
    "35": "\u542b\u672c\u8282\uff0835\u201337\uff09\u5171\u540c\u8bf4\u660e\u533a\u57df\uff08qp[0]\uff09\uff1b",
}


def ms_rows(probe, page):
    out = []
    for line in probe["ms"]["pages"][page - 1]["lines"]:
        t = line["text"].strip()
        if t.isdigit() and 90 <= line["bbox"][0] <= 120:
            out.append((int(t), round(line["bbox"][1], 1)))
    out.sort()
    return out


def main():
    old_sha = hashlib.sha256(IDX.read_bytes()).hexdigest()
    assert old_sha == OLD_SHA, f"index sha changed: {old_sha} != {OLD_SHA}"
    index = json.loads(IDX.read_text(encoding="utf-8"))
    old_qs = index["questions"]
    assert [q["question"] for q in old_qs] == OLD_QS, "old question list unexpected"
    empty_ms = {q["question"] for q in old_qs if not q["ms"]}
    assert empty_ms == {str(n) for n in range(1, 20)} | {"21"}, empty_ms
    q8 = [q for q in old_qs if q["question"] == "8"][0]
    assert [r["page"] for r in q8["qp"]] == [5, 6], "old Q8 cross-page defect not found"
    q34 = [q for q in old_qs if q["question"] == "34"][0]
    assert [r["page"] for r in q34["qp"]] == [13, 14], "old Q34 cross-page defect not found"
    q1 = [q for q in old_qs if q["question"] == "1"][0]
    assert q1["qp"][0]["bbox"] == [70.4, 144.4, 528.8, 365.6], "old Q1 bbox unexpected"

    probe = json.loads(PROBE.read_text(encoding="utf-8"))
    rows2 = ms_rows(probe, 2)
    rows3 = ms_rows(probe, 3)
    assert [n for n, _ in rows2] == list(range(1, 29)), rows2
    assert [n for n, _ in rows3] == list(range(29, 38)), rows3

    def ms_regions(rows, page):
        regs = {}
        for i, (n, y0) in enumerate(rows):
            top = round(y0 - 5.7, 1)
            bot = round(rows[i + 1][1] - 5.7, 1) if i + 1 < len(rows) else round(y0 + 12.0, 1)
            regs[str(n)] = {"page": page, "bbox": [71.7, top, 538.8, bot]}
        return regs

    ms_map = {**ms_regions(rows2, 2), **ms_regions(rows3, 3)}
    assert sorted(ms_map, key=int) == [str(n) for n in range(1, 38)]

    questions = []
    for n in range(1, 38):
        name = str(n)
        note = (INTRO_NOTES.get(name, "") + BASE_NOTE)
        questions.append({
            "question": name,
            "parent": None,
            "text": TEXT[name],
            "marks": MARKS[name],
            "qp": [{"page": p, "bbox": [70.4, y0, 541.2, y1]} for p, y0, y1 in QP_REGIONS[name]],
            "ms": [ms_map[name]],
            "uncertain": False,
            "notes": note,
        })

    # ---- validations ----
    assert len(questions) == 37
    tops = [int(q["question"]) for q in questions]
    assert tops == list(range(1, 38)), tops
    qp_n = sum(len(q["qp"]) for q in questions)
    ms_n = sum(len(q["ms"]) for q in questions)
    assert (qp_n, ms_n) == (44, 37), (qp_n, ms_n)
    for q in questions:
        assert 1 <= len(q["qp"]) <= 25 and 1 <= len(q["ms"]) <= 25, q["question"]
        assert q["text"].strip(), q["question"]
        assert len(q["notes"]) < 2000, q["question"]
        for role, max_page in (("qp", 16), ("ms", 3)):
            for r in q[role]:
                x0, y0, x1, y1 = r["bbox"]
                assert 1 <= r["page"] <= max_page, (q["question"], role)
                assert 0 < x0 < x1 <= 612 and 0 < y0 < y1 <= 792, (q["question"], role, r["bbox"])

    index["questions"] = questions

    if not BACKUP.exists():
        BACKUP.write_text(json.dumps({"questions": old_qs}, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
        print(f"backup written: {BACKUP.name}")

    tmp = IDX.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, IDX)
    new_sha = hashlib.sha256(IDX.read_bytes()).hexdigest()

    report = {
        "key": "0472/2026/Jun/12",
        "fixed_at": "2026-10-04",
        "old_sha256": old_sha,
        "new_sha256": new_sha,
        "questions": len(questions),
        "qp_regions": qp_n,
        "ms_regions": ms_n,
        "changes": [
            "ms regions added for Q1-19 and Q21; all ms regions rebuilt to MS table rows (p2 rows 1-28, p3 rows 29-37)",
            "qp regions re-derived from text layer; option columns and [1]/[2]/[Total]/[PAUSE] marks included",
            "Q8/Q34 cross-page defects fixed (p6/p14 regions belonged to the next section headers)",
            "section-intro blocks added as qp[0] (Questions 1-8, 9-14, 15-19, 20-28 incl. Part 1, Part 2, 29-34, 35-37)",
            "text re-transcribed from text layer (was OCR noise)",
            "marks set 1 (Q1-34) / 2 (Q35-37) from MS table",
        ],
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("=" * 100)
    print(f"questions={len(questions)} qp_regions={qp_n} ms_regions={ms_n}")
    print(f"old sha256: {old_sha}")
    print(f"new sha256: {new_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
