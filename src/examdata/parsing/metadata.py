"""试卷元数据抽取（封面页）。

封面页是权威元数据来源，且提供**校验用的真值**：
"The total mark for this paper is 56."

需要识别（需求文档）：科目代码、Paper、Component、Variant、Level、考试季、年份、时长、总分。
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from .pdfdoc import PdfDocument

_PAPER_CODE = re.compile(r"\b(\d{4})\s*/\s*(\d{1,2})\b")
_PAPER_TITLE = re.compile(r"Paper\s+(\d+)\s*(?:\(([^)]+)\))?", re.I)
_SESSION = re.compile(
    r"\b(May/June|October/November|February/March|June|November|March|October)\s+(20\d{2})\b",
    re.I,
)
_DURATION_HOURS = re.compile(r"\b(\d+(?:\.\d+)?)\s*hours?\b", re.I)
_DURATION_MINUTES = re.compile(r"\b(\d+)\s*minutes?\b", re.I)
_TOTAL_MARKS = re.compile(r"total\s+marks?\s+for\s+this\s+paper\s+is\s+(\d+)", re.I)
_TOTAL_MARKS_ALT = re.compile(r"total\s+marks?\s*[:\-]?\s*(\d+)", re.I)
_PAGE_COUNT = re.compile(r"This document has\s+(\d+)\s+pages", re.I)
_SYLLABUS_NAME = re.compile(r"^([A-Z][A-Z0-9 &/'\-]{2,60})\s*$", re.M)

_SESSION_CANON = {
    "may/june": "june",
    "june": "june",
    "october/november": "november",
    "november": "november",
    "february/march": "march",
    "march": "march",
    "october": "october",
}


@dataclass
class PaperMetadata:
    """从试卷封面页抽取的元数据。"""

    subject_code: Optional[str] = None
    paper_code: Optional[str] = None
    component: Optional[str] = None
    variant: Optional[str] = None
    paper_number: Optional[str] = None
    paper_title: Optional[str] = None
    syllabus_title: Optional[str] = None
    session: Optional[str] = None
    session_raw: Optional[str] = None
    year: Optional[int] = None
    duration_minutes: Optional[int] = None
    total_marks: Optional[int] = None
    declared_page_count: Optional[int] = None
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_paper_metadata(doc: PdfDocument, *, cover_pages: int = 2) -> PaperMetadata:
    """从前若干页（默认封面 2 页）抽取试卷元数据。"""
    if not doc.pages:
        return PaperMetadata()

    text = "\n".join(p.text for p in doc.pages[:cover_pages])
    md = PaperMetadata()

    m = _PAPER_CODE.search(text)
    if m:
        md.subject_code = m.group(1)
        md.paper_code = m.group(2).zfill(2)
        # Cambridge 两位 paper code：第一位 component，第二位 variant
        digits = md.paper_code
        md.component = digits[0]
        md.variant = digits[1] if len(digits) > 1 else None
        md.evidence["paper_code"] = m.group(0)

    m = _PAPER_TITLE.search(text)
    if m:
        md.paper_number = m.group(1)
        md.paper_title = (m.group(2) or "").strip() or None
        md.evidence["paper_title"] = m.group(0).strip()

    m = _SESSION.search(text)
    if m:
        md.session_raw = m.group(0)
        md.session = _SESSION_CANON.get(m.group(1).lower(), m.group(1).lower())
        md.year = int(m.group(2))
        md.evidence["session"] = m.group(0)

    minutes = 0
    mh = _DURATION_HOURS.search(text)
    if mh:
        minutes += int(float(mh.group(1)) * 60)
    mm = _DURATION_MINUTES.search(text)
    if mm and not mh:
        minutes += int(mm.group(1))
    if minutes:
        md.duration_minutes = minutes

    m = _TOTAL_MARKS.search(text) or _TOTAL_MARKS_ALT.search(text)
    if m:
        md.total_marks = int(m.group(1))
        md.evidence["total_marks"] = m.group(0)

    m = _PAGE_COUNT.search(text)
    if m:
        md.declared_page_count = int(m.group(1))

    # 科目名：封面上的全大写行（如 "MATHEMATICS"）
    for line in text.split("\n"):
        line = line.strip()
        mm2 = _SYLLABUS_NAME.match(line)
        if mm2 and len(line) > 4 and line.upper() == line and "PAPER" not in line:
            md.syllabus_title = line
            break

    return md
