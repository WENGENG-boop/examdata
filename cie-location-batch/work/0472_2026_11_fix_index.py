# -*- coding: utf-8 -*-
"""0472/2026/Jun/11: rebuild cie-index.json from PDF text-layer coordinates.

Defects found in the Oct-1 draft index (36 questions, OCR-based):
- Q15 missing entirely (OCR missed the "15 sportsworld.com" line on QP p8; the line
  had been mis-attached to Q1 as a stray second region).
- ms=[] for Q1-19 (MS p2 answer-table rows exist for every question); Q21 ms missing;
  Q20 ms region spanned two table rows; Q22-34 ms y-ranges offset.
- QP regions were OCR approximations that cut option columns / [1] marks
  (e.g. Q2 ended y494.8 but options end y557.4; Q3/Q4/Q5 x1=456.4 cut the [1] marks).
- text was noisy OCR ("H OW", "tO", "0 飞" ...).

Rebuild rules (verified against work/0472_2026_11_probe.json, extracted from the
downloaded originals; conventions matched to the already-verified 0472/2025/Jun/11):
- qp regions: x=[70.4,541.2]; first line top -0.3 .. next question start -0.3;
  last question on a page ends after its last content (Total / PAUSE / [1]);
  section-intro blocks (incl. Information A-F, Part 1/Part 2 headers) become qp[0]
  of the section's first question.
- ms regions: MS answer-table row cells, x=[71.7,538.8],
  top = row_y0 - 5.7, bottom = next row_y0 - 5.7 (last row: row_y0 + 12.0).
- marks: 1 for Q1-34, 2 for Q35-37 (per MS table).
- text: faithful transcription of the text layer.

Backup -> work/0472-2026-Jun-11-index-before-fix.json
Report -> work/0472-2026-Jun-11-fix-report.json
Atomic replace; prints old/new sha256. Does NOT touch errors.jsonl.
"""
import hashlib
import json
import os
from pathlib import Path

BR = Path(r"C:/Users/weo/Desktop/api/cie-location-batch")
IDX = BR / "indexes/0472/2026-Jun-11/cie-index.json"
BACKUP = BR / "work/0472-2026-Jun-11-index-before-fix.json"
REPORT = BR / "work/0472-2026-Jun-11-fix-report.json"
PROBE = BR / "work/0472_2026_11_probe.json"

OLD_SHA = "7383dc055425e41bdd896176d55d11cb2a1528cd6a7a64030ad9d6f20b03da61"
OLD_TOPS = [str(n) for n in range(1, 15)] + [str(n) for n in range(16, 38)]

# (page, y0, y1) — x always [70.4, 541.2]
QP_REGIONS = {
    "1": [(3, 58.8, 144.4), (3, 144.4, 363.2)],
    "2": [(3, 363.2, 560.0)],
    "3": [(4, 58.8, 277.8)],
    "4": [(4, 277.8, 496.7)],
    "5": [(4, 496.7, 693.0)],
    "6": [(5, 58.8, 277.6)],
    "7": [(5, 277.6, 496.5)],
    "8": [(5, 496.5, 717.6)],
    "9": [(6, 58.8, 173.9), (6, 173.9, 364.4)],
    "10": [(6, 364.4, 555.1)],
    "11": [(6, 555.1, 738.0)],
    "12": [(7, 58.8, 254.2)],
    "13": [(7, 254.2, 449.1)],
    "14": [(7, 449.1, 644.8)],
    "15": [(8, 58.8, 468.2), (8, 468.2, 504.8)],
    "16": [(8, 504.8, 541.4)],
    "17": [(8, 541.4, 578.1)],
    "18": [(8, 578.1, 614.8)],
    "19": [(8, 614.8, 653.2)],
    "20": [(9, 58.8, 217.8), (9, 217.8, 348.1)],
    "21": [(9, 348.1, 478.3)],
    "22": [(9, 478.3, 586.0)],
    "23": [(10, 58.8, 189.1)],
    "24": [(10, 189.1, 331.6)],
    "25": [(10, 331.6, 405.0), (10, 405.0, 535.2)],
    "26": [(10, 535.2, 643.0)],
    "27": [(11, 58.8, 189.1)],
    "28": [(11, 189.1, 320.8)],
    "29": [(12, 58.8, 168.8), (12, 168.8, 326.2)],
    "30": [(12, 326.2, 483.6)],
    "31": [(12, 483.6, 642.4)],
    "32": [(13, 58.8, 216.2)],
    "33": [(13, 216.2, 373.6)],
    "34": [(13, 373.6, 532.4)],
    "35": [(14, 58.8, 168.8), (14, 168.8, 350.7)],
    "36": [(14, 350.7, 509.6)],
    "37": [(15, 64.0, 300.0)],
}

TEXT = {
    "1": "Questions 1\u20138 You will hear some short recordings. You will hear each recording twice. "
         "For Questions 1\u20138, tick the correct box (A\u2013D). You are at a museum with a friend. "
         "1 You are at the museum ticket office. The sales assistant says something to you. "
         "How much is your ticket? \u00a31.20 \u00a32.50 \u00a33.70 \u00a34.60 A B C D [1]",
    "2": "2 The sales assistant says something else to you. What must you leave at the ticket office? A B C D [1]",
    "3": "3 Your friend says something to you. What would your friend like to see first? A B C D [1]",
    "4": "4 Your friend says something else to you. What does your friend want to buy at the museum shop? A B C D [1]",
    "5": "5 You are in the caf\u00e9 in the museum. Your friend says something to you. What does your friend want to eat? A B C D [1]",
    "6": "6 Your friend says something else to you. Where would your friend like to sit? A B C D [1]",
    "7": "7 You hear an announcement. What time does the museum close today? A B C D [1]",
    "8": "8 Your friend says something to you. Where does your friend suggest going after leaving the museum? A B C D [1] [Total: 8]",
    "9": "Questions 9\u201314 You will hear an announcement about a class trip to a river. You will hear the announcement twice. "
         "There will be a pause during the announcement. For Questions 9\u201314, tick the correct box (A\u2013D). "
         "You now have some time to read the questions. Class trip to the river 9 Students should meet at 8.00 am in the \u2026 A B C D [1]",
    "10": "10 The students will travel to the river by \u2026 A B C D [1]",
    "11": "11 The first thing students will do at the river is \u2026 A B C D [1] [PAUSE]",
    "12": "12 Students will eat their lunch at \u2026 A B C D [1]",
    "13": "13 After lunch, students will walk to a \u2026 A B C D [1]",
    "14": "14 Students must not forget to bring \u2026 A B C D [1] [Total: 6]",
    "15": "Questions 15\u201319 You will hear two teenagers, Ella and Konstantin, talking about sports websites that they use. "
          "You will hear the conversation twice. For Questions 15\u201319, choose the information (A\u2013F) that matches each website. "
          "For each website, write the correct letter (A\u2013F) on the answer line. Use each letter only once. "
          "There is one extra letter which you do not need to use. You now have some time to read the information below. "
          "Information A It has sports clothing and equipment for sale. B Most of the content is about one sport. "
          "C There are some exciting videos on it. D You can enter great competitions on it. "
          "E It\u2019s quite hard to find information on it. F It has useful advice on keeping fit. "
          "Sports websites 15 sportsworld.com ................... [1]",
    "16": "16 mysport.net ................... [1]",
    "17": "17 sportandyou.com ................... [1]",
    "18": "18 perfectsport.net ................... [1]",
    "19": "19 sportweb.com ................... [1] [Total: 5]",
    "20": "Questions 20\u201328 You will hear two interviews, one with Armando and one with Zhang. They are talking about the "
          "things they do after school and in the evening. There will be a pause between the two interviews. "
          "Part 1: Questions 20\u201324 You will now hear the interview with Armando twice. "
          "For Questions 20\u201324, tick the correct box (A\u2013C). You now have some time to read the questions. "
          "20 What\u2019s the first thing Armando does after getting home from school? A changes his clothes "
          "B listens to some music C has something to eat [1]",
    "21": "21 How much time does Armando usually spend doing homework? A 30 minutes B 45 minutes C 1 hour [1]",
    "22": "22 Armando\u2019s favourite food at dinnertime is \u2026 A vegetable curry. B roast chicken. C sausage and chips. [1]",
    "23": "23 What does Armando do most often with his friends in the evening? A play video games B watch TV C go on a bike ride [1]",
    "24": "24 During the school week, Armando goes to bed at \u2026 A 9.00 pm. B 9.30 pm. C 10.00 pm. [1] [PAUSE]",
    "25": "Part 2: Questions 25\u201328 You will now hear the interview with Zhang twice. "
          "For Questions 25\u201328, tick the correct box (A\u2013C). You now have some time to read the questions. "
          "25 How does Zhang help her parents in the evening? A She does some of the cooking. B She washes the dishes. "
          "C She puts her brother to bed. [1]",
    "26": "26 What kind of programme does Zhang prefer to watch? A crime dramas B nature documentaries C comedy shows [1]",
    "27": "27 How does Zhang feel about seeing her friends in the evening? A pleased they like doing the same things "
          "B disappointed she can\u2019t meet them more often C surprised their time together passes so fast [1]",
    "28": "28 Just before going to bed, Zhang likes to \u2026 A read a book. B check her social media. C have a shower. [1] [Total: 9]",
    "29": "Questions 29\u201334 You are going to hear an interview with Virender, who spent a day at a racetrack learning how to "
          "drive a racing car. You are going to hear the interview twice. There will be a pause in the interview. "
          "For Questions 29\u201334, tick the correct box (A\u2013D). You now have some time to read the questions. "
          "29 How did Virender find out about the racetrack day? A A friend told him about it. B He saw an advert for it. "
          "C A relative emailed him about it. D He read an article about it. [1]",
    "30": "30 Virender says that the racetrack was \u2026 A smaller than he expected. B extremely busy when he arrived. "
          "C a difficult place to find. D less noisy than he imagined. [1]",
    "31": "31 What does Virender say about his driving instructor? A She spoke too fast. B She was very funny. "
          "C She told interesting stories. D She reminded him of someone. [1] [PAUSE]",
    "32": "32 How did Virender feel when he first started driving the racing car? A worried he\u2019d forget what to do "
          "B surprised by how relaxed he felt C nervous about crashing D relieved to set off at last [1]",
    "33": "33 What did Virender find most difficult about driving the racing car? A controlling his speed "
          "B staying in the middle of the track C seeing clearly in front of him D going around corners [1]",
    "34": "34 In the future, Virender would like to learn how to \u2026 A ride a motorbike. B dive underwater. "
          "C fly a plane. D climb up cliffs. [1] [Total: 6]",
    "35": "Questions 35\u201337 You will hear a radio interview with a successful drummer called Heather. "
          "You will hear the interview twice. There will be two pauses during the interview. "
          "For each question (35\u201337), choose the two true statements (A\u2013E) and tick the correct boxes. "
          "You now have some time to read the statements. 35 A Heather started drumming when she was seven years old. "
          "B Someone else in Heather\u2019s family also plays drums. C Heather\u2019s drum teacher gave her a set of drums. "
          "D Heather regularly played in school concerts. E Heather\u2019s parents allowed her to practise whenever she wanted. [2] [PAUSE]",
    "36": "36 A Heather studied music after leaving school. B Heather has also learned to play several other instruments. "
          "C Heather has won a prize for her drumming. D Heather prefers recording music to playing live. "
          "E Heather has set up her own video channel online. [2] [PAUSE]",
    "37": "37 A Heather plays for several different bands. B Heather has appeared on a television music show. "
          "C Heather finds being away from home difficult. D Heather writes some of the songs she performs. "
          "E Heather would like to teach drumming one day. [2] [Total: 6]",
}

MARKS = {str(n): (2 if n >= 35 else 1) for n in range(1, 38)}

BASE_NOTE = "\u533a\u57df\u6309 PDF \u6587\u5b57\u5c42\u5750\u6807\u5b9a\u7a3f\uff082026-10-04\uff09\uff1bms \u4e3a MS \u7b54\u6848\u8868\u5bf9\u5e94\u884c"
INTRO_NOTES = {
    "1": "\u542b\u672c\u8282\uff081\u20138\uff09\u5171\u540c\u8bf4\u660e\u533a\u57df\uff08qp[0]\uff09\uff1b",
    "9": "\u542b\u672c\u8282\uff089\u201314\uff09\u5171\u540c\u8bf4\u660e\u533a\u57df\uff08qp[0]\uff0c\u542b\u6807\u9898 Class trip to the river\uff09\uff1b",
    "15": "\u542b\u672c\u8282\uff0815\u201319\uff09\u5171\u540c\u8bf4\u660e\u533a\u57df\uff08qp[0]\uff0c\u542b Information A\u2013F \u4e0e Sports websites \u6807\u9898\uff09\uff1b",
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
    assert [q["question"] for q in old_qs] == OLD_TOPS, "old question list unexpected"
    assert [q for q in old_qs if q["question"] == "1"][0]["qp"][1]["bbox"] == \
        [70.4, 468.4, 540.4, 504.8], "old Q1 stray p8 region not found"

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
        "key": "0472/2026/Jun/11",
        "fixed_at": "2026-10-04",
        "old_sha256": old_sha,
        "new_sha256": new_sha,
        "questions": len(questions),
        "qp_regions": qp_n,
        "ms_regions": ms_n,
        "changes": [
            "Q15 added (qp p8 line + ms p2 row 15C); old Q1 stray p8 region dropped",
            "ms regions added/fixed for all 37 questions (MS p2 rows 1-28, p3 rows 29-37)",
            "qp regions re-derived from text layer; option columns and [1]/[2] marks included",
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
