"""解析 CIE《Additional exam materials list - November 2026》文本稿为结构化数据。

输入：evidence/additional_materials_intl.txt（PDF 全文文本导出）
输出：
  - evidence/addmaterials_rows.json       逐组件行（含原始材料文本，供审计）
  - evidence/addmaterials_by_subject.json 按科目聚合（材料类型检测结果）

文本结构：每行以 `NNNN/CC` 开头，随后是 [Zone N]、日期、标题、三个单元格
（我们提供的材料 / 考生需自备 / 是否在试卷上作答）。页面家具（表头、页脚、
分节标题）在解析时剔除。单元格在文本里被折行且互不标记，因此对材料类型的
判定用短语扫描而非精确列切分；每条匹配都保留命中原文。
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "evidence" / "additional_materials_intl.txt"
OUT_ROWS = HERE / "evidence" / "addmaterials_rows.json"
OUT_SUBJ = HERE / "evidence" / "addmaterials_by_subject.json"

CODE_RE = re.compile(r"^(\d{4})/([A-Z0-9]{1,3})$")
ZONE_RE = re.compile(r"^Zone (\d+)$")
DATE_RE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")

FURNITURE = {
    "Syllabus /", "Component", "Start Exam", "Date", "Administrative", "Zone",
    "Syllabus Title", "Materials we provide", "Additional materials for",
    "Candidates", "Do candidates answer on the", "question paper?",
    "Additional Materials List - November 2026",
}
HEADINGS = {
    "GCE AS & A Level", "IGCSE", "IGCSE (9-1)", "GCE O Level", "IGCSE Core",
    "Checkpoint", "Primary Checkpoint", "Lower Secondary Checkpoint",
    "Cambridge Primary Checkpoint", "Cambridge Lower Secondary Checkpoint",
}

# 单元格 1（我们提供）里的锚点：材料文本从这里开始，之前是标题。
ANCHOR_RE = re.compile(
    r"^(Attendance Register|Not applicable for this|Listening File|MS4 \(CIE\)"
    r"|Question Paper|Candidates answer|Script Envelope|Bar-coded Label"
    r"|\*\* Candidates|Multiple Choice|ICT Candidate ARF|Pre-Release|Source File"
    r"|DVD|CISpecimens|A2 Plastic)"
)

# (key, 正则, 说明) —— 命中即视为该行提供/涉及该材料。
PROVIDED_PATTERNS = [
    ("mf19_formulae_tables", r"Formulae & Tables \(MF19\)", "MF19 公式与统计表"),
    ("answer_booklet_insert", r"(?:RTL )?Answer Booklet provided with the QP", "随卷装订的答题册（insert）"),
    ("mc_answer_sheet", r"Multiple Choice Answer Sheet", "选择题答题卡"),
    ("pre_release", r"Pre-Release [^/]*", "考前预发材料"),
    ("qp_special_format", r"Question Paper (?:DFD|SSH|DIR|RTL)", "特殊格式试卷（DFD/SSH/DIR）"),
    ("listening_file_alf", r"Listening File ALF", "听力音频文件"),
    ("role_play_cards", r"Role Play Cards", "口语角色扮演卡"),
    ("teachers_notes", r"Teacher's Notes", "教师用说明"),
    ("cispecimens", r"CISpecimens", "保密样例材料"),
    ("source_file", r"Source File", "源文件（ICT/设计类）"),
    ("candidate_arf", r"Candidate ARF", "考生 ARF 文件"),
    ("dvd", r"\bDVD\b", "DVD 素材"),
    ("instructions", r"\bInstructions\b", "说明文件"),
    ("supervisor_report_folder", r"Supervisor Report Folder", "监考报告文件夹（考务）"),
]
CANDIDATE_PATTERNS = [
    ("geometrical_instruments", r"Geometrical Instruments", "几何工具"),
    ("tracing_paper", r"Tracing Paper(?: \(Optional\))?", "描图纸"),
    ("calculator", r"Calculator", "计算器"),
    ("ruler", r"Ruler", "直尺"),
    ("protractor", r"Protractor", "量角器"),
    ("pair_of_compasses", r"Pair of compasses", "圆规"),
    ("plain_paper", r"Plain Paper", "草稿纸"),
    ("coloured_pencils", r"Coloured Pencils", "彩色铅笔"),
    ("standard_drawing_equipment", r"Standard Drawing Equipment", "标准绘图工具"),
    ("soft_pencil", r"Soft Pencil \(B or HB must be used\)", "软铅笔"),
    ("eraser", r"Eraser", "橡皮"),
    ("pen", r"\bPen\b", "笔"),
    ("scissors", r"Scissors", "剪刀"),
    ("sewing_equipment", r"Sewing Equipment", "缝纫工具"),
    ("sewing_threads", r"Sewing and Tacking Threads", "缝纫线"),
    ("tape_measure", r"Tape Measure", "卷尺"),
    ("pattern_by_centre", r"Pattern provided by Centre", "中心自备纸样"),
]
POLICY_PATTERNS = [
    ("set_texts_allowed", r"Unannotated set texts allowed in exam", "允许携带无批注指定文本"),
    ("set_texts_not_allowed", r"Set texts not allowed in exam", "指定文本不得带入考场"),
]


def clean_block(lines: list[str]) -> list[str]:
    out = []
    for line in lines:
        s = line.strip()
        if not s or s in FURNITURE or s in HEADINGS:
            continue
        if re.match(r"^\d+ of \d+$", s):
            continue
        out.append(s)
    return out


def parse_block(code: str, component: str, qualification: str, lines: list[str]) -> dict:
    zone = None
    date = None
    rest: list[str] = []
    for s in clean_block(lines):
        if zone is None and (m := ZONE_RE.match(s)):
            zone = int(m.group(1))
            continue
        if date is None and (m := DATE_RE.match(s)):
            date = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
            continue
        rest.append(s)
    title_lines: list[str] = []
    body_lines: list[str] = []
    for s in rest:
        if not body_lines and ANCHOR_RE.match(s):
            body_lines.append(s)
        elif body_lines:
            body_lines.append(s)
        else:
            title_lines.append(s)
    title = re.sub(r"\s+", " ", " ".join(title_lines)).strip()
    materials_text = re.sub(r"\s+", " ", " ".join(body_lines)).strip()
    # 去掉尾部的“是否在试卷上作答”单元格（Yes/No 句），材料正文到此为止。
    m = re.search(r"(Yes, candidates|No, candidates|No, the answer|No, you should)", materials_text)
    materials_only = materials_text[: m.start()].strip() if m else materials_text
    answer_on_qp = "yes" if m and m.group(1).startswith("Yes") else ("no" if m else "na")
    if re.search(r"Not applicable for this component$", materials_only):
        # 末段 NA 属于第二单元格，保留计数即可
        pass
    na_cells = materials_only.count("Not applicable for this component")
    provided = []
    for key, pattern, label in PROVIDED_PATTERNS:
        for hit in re.finditer(pattern, materials_only):
            provided.append({"key": key, "label": label, "text": hit.group(0)})
            break
    candidate = []
    for key, pattern, label in CANDIDATE_PATTERNS:
        for hit in re.finditer(pattern, materials_only):
            candidate.append({"key": key, "label": label, "text": hit.group(0)})
            break
    policy = []
    for key, pattern, label in POLICY_PATTERNS:
        for hit in re.finditer(pattern, materials_only):
            policy.append({"key": key, "label": label, "text": hit.group(0)})
            break
    return {
        "code": code,
        "component": component,
        "qualification": qualification,
        "zone": zone,
        "date": date,
        "title": title,
        "answer_on_qp": answer_on_qp,
        "na_cells": na_cells,
        "provided": provided,
        "candidate": candidate,
        "policy": policy,
        "materials_text": materials_only,
    }


def main() -> None:
    lines = SRC.read_text(encoding="utf-8").splitlines()
    rows: list[dict] = []
    current: dict | None = None
    heading = None
    for line in lines:
        s = line.strip()
        if s in HEADINGS:
            heading = s
            continue
        if (m := CODE_RE.match(s)):
            if current is not None:
                rows.append(parse_block(current["code"], current["component"], current["qualification"], current["lines"]))
            current = {"code": m.group(1), "component": m.group(2), "qualification": heading, "lines": []}
            continue
        if current is not None:
            current["lines"].append(line)
    if current is not None:
        rows.append(parse_block(current["code"], current["component"], current["qualification"], current["lines"]))

    OUT_ROWS.write_text(
        json.dumps(
            {
                "source": {
                    "file": "evidence/additional_materials_intl.txt",
                    "document": "CIE Additional exam materials list, November 2026 series",
                    "url": "https://www.cambridgeinternational.org/Images/651593-additional-exams-material-list-international-.pdf",
                    "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                },
                "row_count": len(rows),
                "rows": rows,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )

    by_subject: dict[str, dict] = {}
    for r in rows:
        subj = by_subject.setdefault(
            r["code"],
            {
                "code": r["code"],
                "titles": Counter(),
                "qualifications": Counter(),
                "components": [],
                "provided": {},
                "candidate": {},
                "policy": {},
                "answer_on_qp": Counter(),
                "zone_rows": 0,
            },
        )
        subj["titles"][r["title"]] += 1
        subj["qualifications"][r["qualification"]] += 1
        subj["components"].append(f'{r["code"]}/{r["component"]}')
        if r["zone"] is not None:
            subj["zone_rows"] += 1
        subj["answer_on_qp"][r["answer_on_qp"]] += 1
        for bucket in ("provided", "candidate", "policy"):
            for item in r[bucket]:
                key = item["key"]
                entry = subj[bucket].setdefault(key, {"label": item["label"], "hits": 0, "sample": item["text"]})
                entry["hits"] += 1

    serialised = {}
    for code, s in sorted(by_subject.items()):
        serialised[code] = {
            "code": code,
            "titles": dict(s["titles"]),
            "qualifications": dict(s["qualifications"]),
            "component_count": len(set(s["components"])),
            "components": sorted(set(s["components"])),
            "zone_rows": s["zone_rows"],
            "provided": s["provided"],
            "candidate": s["candidate"],
            "policy": s["policy"],
            "answer_on_qp": dict(s["answer_on_qp"]),
        }
    OUT_SUBJ.write_text(
        json.dumps(
            {
                "source": "evidence/additional_materials_intl.txt (CIE Additional exam materials list, Nov 2026)",
                "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "subject_count": len(serialised),
                "subjects": serialised,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"rows: {len(rows)}  subjects: {len(serialised)}")
    print("wrote", OUT_ROWS.name, OUT_SUBJ.name)


if __name__ == "__main__":
    main()
