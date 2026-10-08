"""缺口 1 补证 v2：Wayback 捕获的附加材料清单（June 系列为主）解析 + 23 码核对。

- 批量取回 651593 各捕获（3 个显式 June/Nov 2022 URL + 4 个轮换内容捕获）
- pymupdf 提取文本，识别每份清单的系列标题
- 修复 v1 解析 bug（row["lines"] 被 None 覆盖）：对每份清单解析组件行
- 对 23 个无证据码做逐清单核对（存在性 + 材料命中）
- 原始 PDF 仅临时存放，解析后删除

输出：
  evidence/gap1_wayback_lists.json        总览（每份清单元数据 + 逐码核对）
  evidence/addmaterials_rows_<slug>.json  逐清单解析行（结构化证据）
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pymupdf

sys.path.insert(0, r"C:/Users/weo/Desktop/api/examdata/src")
from examdata.core.config import Settings
from examdata.core.fetch import Fetcher

OUT = Path(r"C:/Users/weo/Desktop/api/tmp_materials_probe/evidence")
DOWNLOADS = Path(r"C:/Users/weo/Desktop/api/tmp_materials_probe/downloads")
DOWNLOADS.mkdir(parents=True, exist_ok=True)

BASE = "https://www.cambridgeinternational.org/Images/651593-additional-exams-material-list-international-.pdf"
JUN22 = "https://www.cambridgeinternational.org/Images/651593-additional-exams-material-list-june-2022-international-.pdf"
NOV22 = "https://www.cambridgeinternational.org/Images/651593-additional-exams-material-list-november-2022-international-.pdf"

CANDIDATES = [
    ("20250108234633", BASE, "rotate-2025-01"),
    ("20240703193603", BASE, "rotate-2024-07"),
    ("20230322151331", BASE, "rotate-2023-03"),
    ("20251014160116", BASE, "rotate-2025-10"),
    ("20250505095707", BASE, "rotate-2025-05"),
    ("20220517211648", JUN22, "june-2022"),
    ("20220926091645", NOV22, "november-2022"),
]

CODES23 = ["0262", "0265", "0266", "0444", "0472", "0479", "0480", "0499", "0523", "0539", "0544",
           "0547", "0715", "0716", "0772", "0989", "0995", "7164", "8101", "8102", "8293", "9981", "9982"]

CODE_RE = re.compile(r"^(\d{4})/([A-Z0-9]{1,3})$")
ZONE_RE = re.compile(r"^Zone (\d+)$")
DATE_RE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
FURNITURE = {
    "Syllabus /", "Component", "Start Exam", "Date", "Administrative", "Zone",
    "Syllabus Title", "Materials we provide", "Additional materials for",
    "Candidates", "Do candidates answer on the", "question paper?",
}
HEADINGS = {
    "GCE AS & A Level", "IGCSE", "IGCSE (9-1)", "GCE O Level", "IGCSE Core",
    "Checkpoint", "Primary Checkpoint", "Lower Secondary Checkpoint",
    "Cambridge Primary Checkpoint", "Cambridge Lower Secondary Checkpoint",
}
ANCHOR_RE = re.compile(
    r"^(Attendance Register|Not applicable for this|Listening File|MS4 \(CIE\)"
    r"|Question Paper|Candidates answer|Script Envelope|Bar-coded Label"
    r"|\*\* Candidates|Multiple Choice|ICT Candidate ARF|Pre-Release|Source File"
    r"|DVD|CISpecimens|A2 Plastic)"
)
PROVIDED_PATTERNS = [
    ("mf19_formulae_tables", r"Formulae & Tables \(MF19\)"),
    ("answer_booklet_insert", r"(?:RTL )?Answer Booklet provided with the QP"),
    ("mc_answer_sheet", r"Multiple Choice Answer Sheet"),
    ("pre_release", r"Pre-Release [^/]*"),
    ("qp_special_format", r"Question Paper (?:DFD|SSH|DIR|RTL)"),
    ("listening_file_alf", r"Listening File ALF"),
    ("role_play_cards", r"Role Play Cards"),
    ("teachers_notes", r"Teacher's Notes"),
    ("cispecimens", r"CISpecimens"),
    ("source_file", r"Source File"),
    ("candidate_arf", r"Candidate ARF"),
    ("dvd", r"\bDVD\b"),
    ("instructions", r"\bInstructions\b"),
]


def parse_rows(text: str) -> list[dict]:
    lines = text.splitlines()
    rows = []
    current = None
    heading = None
    for line in lines:
        s = line.strip()
        if s in HEADINGS:
            heading = s
            continue
        m = CODE_RE.match(s)
        if m:
            if current is not None:
                rows.append(current)
            current = {"code": m.group(1), "component": m.group(2), "qualification": heading, "lines": []}
            continue
        if current is not None:
            current["lines"].append(line)
    if current is not None:
        rows.append(current)

    parsed = []
    for row in rows:
        block = []
        zone = None
        date = None
        for s in [x.strip() for x in (row["lines"] or [])]:
            if not s or s in FURNITURE or s in HEADINGS:
                continue
            if re.match(r"^\d+ of \d+$", s):
                continue
            if zone is None and (m := ZONE_RE.match(s)):
                zone = int(m.group(1))
                continue
            if date is None and (m := DATE_RE.match(s)):
                date = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
                continue
            block.append(s)
        title_lines, body_lines = [], []
        for s in block:
            if not body_lines and ANCHOR_RE.match(s):
                body_lines.append(s)
            elif body_lines:
                body_lines.append(s)
            else:
                title_lines.append(s)
        materials_text = re.sub(r"\s+", " ", " ".join(body_lines)).strip()
        m = re.search(r"(Yes, candidates|No, candidates|No, the answer|No, you should)", materials_text)
        materials_only = materials_text[: m.start()].strip() if m else materials_text
        provided = []
        for key, pattern in PROVIDED_PATTERNS:
            hit = re.search(pattern, materials_only)
            if hit:
                provided.append({"key": key, "text": hit.group(0)})
        parsed.append({
            "code": row["code"], "component": row["component"], "qualification": row["qualification"],
            "zone": zone, "date": date, "title": re.sub(r"\s+", " ", " ".join(title_lines)).strip(),
            "provided": provided, "materials_text": materials_only,
        })
    return parsed


def main() -> None:
    fetcher = Fetcher(Settings())
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    overview = {"generated_at": now, "lists": []}
    for capture, url, hint in CANDIDATES:
        fetch_url = f"https://web.archive.org/web/{capture}id_/{url}"
        rec = {"capture": capture, "url": url, "hint": hint}
        print("== fetching", capture, hint)
        r = fetcher.get(fetch_url, expect_binary=True)
        rec["http"] = getattr(r, "status", None)
        rec["error"] = r.error
        if not (r.ok and r.content):
            print("   FAILED", rec)
            overview["lists"].append(rec)
            continue
        rec["bytes"] = len(r.content)
        rec["sha256"] = hashlib.sha256(r.content).hexdigest()
        pdf_path = DOWNLOADS / f"addmat_{capture}.pdf"
        pdf_path.write_bytes(r.content)
        try:
            doc = pymupdf.open(pdf_path)
            rec["pages"] = len(doc)
            text = "\n".join(page.get_text("text") for page in doc)
            doc.close()
            rec["text_chars"] = len(text)
            m = re.search(r"Additional Materials List\s*[-–]\s*([A-Za-z]+ \d{4})", text)
            if not m:
                m = re.search(r"([A-Z][a-z]+ \d{4})", text[:4000])
            rec["document_title"] = m.group(1) if m else None
            print("   title:", rec["document_title"], "pages:", rec["pages"], "bytes:", rec["bytes"])
            title = rec["document_title"] or hint
            slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
            if not slug:
                slug = hint
            parsed = parse_rows(text)
            by_code = Counter(x["code"] for x in parsed)
            rec["slug"] = slug
            rec["row_count"] = len(parsed)
            rec["subject_count"] = len(by_code)
            (OUT / f"addmaterials_rows_{slug}.json").write_text(
                json.dumps({"source": {"url": url, "capture": capture, "document_title": rec["document_title"],
                                       "sha256": rec["sha256"], "bytes": rec["bytes"], "pages": rec["pages"],
                                       "generated_at": now},
                            "row_count": len(parsed), "rows": parsed}, ensure_ascii=False, indent=1), encoding="utf-8")
            # 23 码核对
            check = {}
            for code in CODES23:
                code_rows = [x for x in parsed if x["code"] == code]
                entry = {"rows": len(code_rows)}
                if code_rows:
                    entry["components"] = sorted({f'{x["code"]}/{x["component"]}' for x in code_rows})
                    mat = Counter()
                    for x in code_rows:
                        for p in x["provided"]:
                            mat[p["key"]] += 1
                    entry["provided_keys"] = dict(mat)
                    entry["sample_row"] = code_rows[0]["materials_text"][:300]
                check[code] = entry
            rec["codes23_check"] = check
            rec["codes23_present"] = [c for c in CODES23 if check[c]["rows"]]
            print("   rows:", len(parsed), "subjects:", len(by_code), "23codes present:", rec["codes23_present"])
        finally:
            pdf_path.unlink(missing_ok=True)
        overview["lists"].append(rec)

    (OUT / "gap1_wayback_lists.json").write_text(json.dumps(overview, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote gap1_wayback_lists.json")
    fetcher.close()


if __name__ == "__main__":
    main()
