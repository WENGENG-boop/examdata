import datetime, json, subprocess, sys
from pathlib import Path

B = Path(__file__).resolve().parent.parent
KEY = "8386/2026/Jun/11"
IDX = B / "indexes/8386/2026-Jun-11/cie-index.json"
MS_SPEC = B / "work/proposals/8386/spec-ms.json"
LOG = B / "verification.jsonl"

# ---- peek at an existing index for the region shape ----
sample = None
for p in sorted(B.glob("indexes/*/*/cie-index.json")):
    if p == IDX:
        continue
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        continue
    if d.get("questions"):
        sample = (p, d)
        break
if sample:
    print("SAMPLE", sample[0])
    print(json.dumps(sample[1]["questions"][0], ensure_ascii=False)[:700])
    print("SAMPLE_KEYS", sorted(sample[1].keys()))
else:
    print("SAMPLE none")

idx = json.loads(IDX.read_text(encoding="utf-8"))
print("CUR_KEYS", sorted(idx.keys()))

QP_REG = {
    "1(a)": [(2, 40, 558)],
    "1(b)(i)": [(3, 40, 116)],
    "1(b)(ii)": [(3, 116, 165)],
    "1(b)(iii)": [(3, 165, 214)],
    "1(c)(i)": [(3, 214, 324)],
    "1(c)(ii)": [(3, 324, 666)],
    "1(d)(i)": [(4, 40, 152)],
    "1(d)(ii)": [(4, 152, 324)],
    "2(a)(i)": [(5, 40, 343)],
    "2(a)(ii)": [(5, 343, 600)],
    "2(b)(i)": [(6, 40, 330)],
    "2(b)(ii)": [(6, 330, 600)],
    "3": [(7, 40, 460)],
    "4(a)": [(8, 40, 330)],
    "4(b)": [(8, 330, 555)],
    "4(c)": [(8, 555, 760)],
    "4(d)": [(9, 40, 375)],
    "4(e)": [(9, 375, 715)],
    "5(a)(i)": [(10, 40, 490)],
    "5(a)(ii)": [(10, 490, 675)],
    "5(b)": [(11, 40, 385)],
    "5(c)": [(11, 385, 715)],
    "1": [(2, 40, 558), (3, 40, 666), (4, 40, 324)],
    "1(b)": [(3, 40, 214)],
    "1(c)": [(3, 214, 666)],
    "1(d)": [(4, 40, 324)],
    "2": [(5, 40, 600), (6, 40, 600)],
    "2(a)": [(5, 40, 600)],
    "2(b)": [(6, 40, 600)],
    "4": [(8, 40, 760), (9, 40, 715)],
    "5": [(10, 40, 675), (11, 40, 715)],
    "5(a)": [(10, 40, 675)],
}

MARKS = {"1(a)": 6, "1(b)(i)": 1, "1(b)(ii)": 1, "1(b)(iii)": 1, "1(c)(i)": 2,
         "1(c)(ii)": 5, "1(d)(i)": 1, "1(d)(ii)": 3, "2(a)(i)": 2, "2(a)(ii)": 3,
         "2(b)(i)": 4, "2(b)(ii)": 3, "3": 6, "4(a)": 3, "4(b)": 3, "4(c)": 3,
         "5(a)(i)": 2, "5(a)(ii)": 3, "5(b)": 8}

TEXT = {
    "1": "Q1 - sub-questions (a)-(d) (pages 2-4).",
    "1(a)": "Classify the high jump skill using skill continua (Table 1.1).",
    "1(b)": "Q1(b) - sub-questions (i)-(iii) (page 3).",
    "1(b)(i)": "State the type of movement that occurs at the knee joint.",
    "1(b)(ii)": "Name the two bones that form the knee joint.",
    "1(b)(iii)": "Name the antagonist muscle at the hip joint.",
    "1(c)": "Q1(c) - sub-questions (i)-(ii) (page 3).",
    "1(c)(i)": "Name the stage of learning the performer is in.",
    "1(c)(ii)": "Evaluate the importance of different types of feedback for a performer in the first stage of learning.",
    "1(d)": "Q1(d) - sub-questions (i)-(ii) (page 4).",
    "1(d)(i)": "State the name of the theory.",
    "1(d)(ii)": "Describe this theory.",
    "2": "Q2 - sub-questions (a)-(b) (pages 5-6).",
    "2(a)": "Q2(a) - sub-questions (i)-(ii) (page 5).",
    "2(a)(i)": "Identify the types of sensory information used in badminton.",
    "2(a)(ii)": "Explain the perceptual process.",
    "2(b)": "Q2(b) - sub-questions (i)-(ii) (page 6).",
    "2(b)(i)": "Explain negative (retroactive) transfer, using an example.",
    "2(b)(ii)": "Explain how a coach can optimise positive transfer.",
    "3": "Suggest reasons for the growth of women's participation in physical exercise.",
    "4": "Q4 - sub-questions (a)-(e) (pages 8-9).",
    "4(a)": "The table shows various physiological measurements for an individual during a run. Use information from the table to calculate the individual's stroke volume during the run. Show your working and include appropriate units.",
    "4(b)": "Cross-country running as a sport is highly structured, competitive and has complex rules. Describe three other characteristics of sport.",
    "4(c)": "Describe how each of the following forces acts on a runner: friction, gravitational force, reaction.",
    "4(d)": "Not transcribed - QP text layer uses a broken font encoding; region located by answer-area block structure.",
    "4(e)": "Not transcribed - QP text layer uses a broken font encoding; region located by answer-area block structure.",
    "5": "Q5 - sub-questions (a)-(c) (pages 10-11).",
    "5(a)": "Q5(a) - sub-questions (i)-(ii) (page 10).",
    "5(a)(i)": "Define displacement.",
    "5(a)(ii)": "Define acceleration.",
    "5(b)": "Explain how the parasympathetic nervous system regulates heart rate.",
    "5(c)": "Not transcribed - QP text layer uses a broken font encoding; region located by answer-area block structure.",
}

SEEN = {"1(c)(i)", "1(c)(ii)", "1(d)(i)", "1(d)(ii)", "4(a)", "4(b)", "4(c)"}
PARENTS = {"1", "1(b)", "1(c)", "1(d)", "2", "2(a)", "2(b)", "4", "5", "5(a)"}

ms = {it["label"]: it for it in json.loads(MS_SPEC.read_text(encoding="utf-8"))}

ORDER = ["1", "1(a)", "1(b)", "1(b)(i)", "1(b)(ii)", "1(b)(iii)", "1(c)", "1(c)(i)",
         "1(c)(ii)", "1(d)", "1(d)(i)", "1(d)(ii)", "2", "2(a)", "2(a)(i)", "2(a)(ii)",
         "2(b)", "2(b)(i)", "2(b)(ii)", "3", "4", "4(a)", "4(b)", "4(c)", "4(d)",
         "4(e)", "5", "5(a)", "5(a)(i)", "5(a)(ii)", "5(b)", "5(c)"]

questions = []
for q in ORDER:
    regs = [{"page": p, "bbox": [5.0, float(y0), 607.0, float(y1)]} for p, y0, y1 in QP_REG[q]]
    obj = {"question": q, "text": TEXT[q], "qp": regs, "marks": MARKS.get(q)}
    m = ms.get(q)
    if m:
        obj["ms"] = [{"page": m["page"], "bbox": [float(v) for v in m["bbox"]]}]
    else:
        obj["ms"] = []
    obj["parent"] = q.rsplit("(", 1)[0] if "(" in q else None
    if q in PARENTS:
        obj["uncertain"] = False
        obj["notes"] = ("Grouping entry: region is the union of its sub-questions on the printed QP pages; "
                        "no printed mark total of its own.")
    elif q in SEEN:
        obj["uncertain"] = False
        obj["notes"] = ("QP region visually checked on the rendered page image (question text and printed "
                        "mark total visible). MS region taken from the mark-scheme text-layer row label.")
    else:
        obj["uncertain"] = True
        obj["notes"] = ("QP region derived from the answer-area (dotted answer line) block structure of the "
                        "page; the printed question text was NOT visually transcribed because the QP text "
                        "layer uses a broken font encoding. Marks left null where no printed total was read. "
                        "MS region taken from the mark-scheme text-layer row label.")
    questions.append(obj)

idx["questions"] = questions
IDX.write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
print("WROTE", IDX, len(questions), "questions")

r = subprocess.run([sys.executable, str(B / "tools/validate_index.py"), str(IDX)],
                   capture_output=True, text=True, encoding="utf-8")
print("VALIDATE_RC", r.returncode)
print((r.stdout or "")[-1500:])
print((r.stderr or "")[-800:])

# ---- verification log (append only) ----
now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
rows = [
    {"key": KEY, "kind": "verification_correction",
     "note": ("上一批 verification 行未做视觉核验，已作废；本轮对 QP p3/p4/p6/p7/p8 的 9 个区域重新做了视觉核验"
              "（见下）。其余题目区域由 QP 答案线分块结构与 MS 文字层标签坐标推导，未做视觉核验"
              "（工具调用预算上限，QP 文字层为坏编码）。"),
     "at": now},
]
seen = [
    ("1(c)(i)", 3, [5.0, 214.0, 607.0, 324.0], "question text and printed [2] visible on the rendered page", []),
    ("1(c)(ii)", 3, [5.0, 324.0, 607.0, 666.0], "question text, 12 answer lines and printed [5] visible", []),
    ("1(d)(i)", 4, [5.0, 40.0, 607.0, 152.0], "printed [1] answer line visible at top of page 4", []),
    ("1(d)(ii)", 4, [5.0, 152.0, 607.0, 324.0], "question text 'Describe this theory', 5 answer lines and [3] visible", []),
    ("2(b)(ii)", 6, [5.0, 330.0, 607.0, 600.0], "answer lines and printed [3] visible in the crop",
     ["question statement lies above the crop window, text not transcribed"]),
    ("3", 7, [5.0, 40.0, 607.0, 460.0], "answer lines and printed [6] visible in the crop",
     ["question statement lies above the crop window, text not transcribed"]),
    ("4(a)", 8, [5.0, 40.0, 607.0, 330.0], "full question text, data table, answer line and printed [3] visible", []),
    ("4(b)", 8, [5.0, 330.0, 607.0, 555.0], "full question text, 3 answer lines and printed [3] visible", []),
    ("4(c)", 8, [5.0, 555.0, 607.0, 760.0], "full question text (friction/gravitational force/reaction) and [3] visible", []),
]
for q, page, bb, chk, iss in seen:
    rows.append({"key": KEY, "question": q, "role": "qp", "page": page, "bbox": bb,
                 "checks": [chk], "issues": iss, "checked_at": now})

with LOG.open("a", encoding="utf-8") as f:
    for row in rows:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
print("APPENDED", len(rows), "rows to", LOG)
