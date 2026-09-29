"""Cambridge 锚文本分类器。

实测锚文本样本（research/cambridge.md §3.3）：
    June 2024 Question Paper 11
    June 2024 Mark Scheme Paper 11
    June 2024 Examiner Report
    2025 Specimen Paper 1
    2025 Specimen Paper 1 Mark Scheme
    2020 Specimen Mark Scheme Paper 1        <- 词序相反，必须同时支持
    2020 Specimen Paper 1 Insert
    June 2024 Confidential Instructions Paper 51

分类不能只看文件名：以锚文本为主信号，URL 中的 descriptive slug 作为交叉校验。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

# --- 统一文件类型（跨考试局通用概念） ---
DOC_QUESTION_PAPER = "question_paper"
DOC_MARK_SCHEME = "mark_scheme"
DOC_EXAMINER_REPORT = "examiner_report"
DOC_SPECIMEN_PAPER = "specimen_paper"
DOC_SPECIMEN_MARK_SCHEME = "specimen_mark_scheme"
DOC_CONFIDENTIAL_INSTRUCTIONS = "confidential_instructions"
DOC_INSERT = "source_material"
DOC_FORMULA_BOOKLET = "formula_booklet"
DOC_DATA_BOOKLET = "data_booklet"
DOC_SAMPLE_RESPONSE = "sample_response"
DOC_OTHER = "other"

_SERIES_WORDS = {
    "june": "june",
    "november": "november",
    "march": "march",
    "may": "may",
    "october": "october",
    "january": "january",
    "february": "february",
}

_HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
_SIZE_SUFFIX = re.compile(r"\(\s*(?:PDF|pdf)[^)]*\)\s*$")
_WS = re.compile(r"\s+")
_YEAR = re.compile(r"\b(20\d{2})\b")
_PAPER_NUM = re.compile(r"\bPaper\s+(\d{1,2})\b", re.I)
_SPECIMEN_NUM = re.compile(r"\bSpecimen\s+(?:Paper|Mark\s+Scheme\s+Paper)\s+(\d{1,2})\b", re.I)


@dataclass
class ParsedResource:
    """分类与元数据解析结果。"""

    doc_type: str
    confidence: float
    year: Optional[int] = None
    series: Optional[str] = None
    paper_code: Optional[str] = None
    is_specimen: bool = False
    evidence: dict[str, Any] = field(default_factory=dict)


def normalize_label(raw: str) -> str:
    """清洗锚文本：去 HTML 注释、去 (PDF, 1MB) 后缀、压缩空白。"""
    if not raw:
        return ""
    s = _HTML_COMMENT.sub(" ", raw)
    s = s.replace("-->", " ").replace("<!--", " ")
    s = _SIZE_SUFFIX.sub("", s)
    s = _WS.sub(" ", s)
    return s.strip()


def _detect_doc_type(text: str) -> tuple[str, bool, dict[str, Any]]:
    """返回 (doc_type, is_specimen, evidence)。"""
    t = text.lower()
    specimen = "specimen" in t
    ev: dict[str, Any] = {"specimen": specimen}

    has_paper = "question paper" in t or bool(re.search(r"\bpaper\b", t))
    has_ms = "mark scheme" in t

    if "confidential instruction" in t:
        return DOC_CONFIDENTIAL_INSTRUCTIONS, specimen, ev
    if "examiner report" in t:
        return DOC_EXAMINER_REPORT, specimen, ev
    if has_ms and specimen:
        return DOC_SPECIMEN_MARK_SCHEME, True, ev
    if has_ms:
        return DOC_MARK_SCHEME, specimen, ev
    if "insert" in t:
        return DOC_INSERT, specimen, ev
    if "formula booklet" in t:
        return DOC_FORMULA_BOOKLET, specimen, ev
    if "data booklet" in t:
        return DOC_DATA_BOOKLET, specimen, ev
    if "specimen" in t and has_paper:
        return DOC_SPECIMEN_PAPER, True, ev
    if "question paper" in t:
        return DOC_QUESTION_PAPER, specimen, ev
    return DOC_OTHER, specimen, ev


def parse_label(raw_label: str) -> ParsedResource:
    """从锚文本解析文件类型与考试元数据。"""
    text = normalize_label(raw_label)
    doc_type, is_specimen, ev = _detect_doc_type(text)
    ev["normalized_label"] = text

    year = None
    m = _YEAR.search(text)
    if m:
        year = int(m.group(1))
        ev["year_from"] = "label"

    series = None
    for word, canon in _SERIES_WORDS.items():
        if re.search(rf"\b{word}\b", text, re.I):
            series = canon
            ev["series_from"] = "label"
            break

    paper_code = None
    m = _SPECIMEN_NUM.search(text) or _PAPER_NUM.search(text)
    if m:
        paper_code = m.group(1).zfill(2) if len(m.group(1)) == 1 else m.group(1)
        ev["paper_from"] = "label"

    # 置信度：类型明确 + 年份 + 期号
    conf = 0.0
    if doc_type != DOC_OTHER:
        conf += 0.7
    if year is not None:
        conf += 0.1
    if series is not None or is_specimen:
        conf += 0.1
    if paper_code is not None or doc_type in (DOC_EXAMINER_REPORT,):
        conf += 0.1

    return ParsedResource(
        doc_type=doc_type,
        confidence=round(min(conf, 1.0), 3),
        year=year,
        series=series,
        paper_code=paper_code,
        is_specimen=is_specimen,
        evidence=ev,
    )


# 顺序即优先级：修饰性后缀（insert / mark-scheme）必须排在基础类型（specimen-paper）之前。
# 例如 2020-specimen-paper-1-insert 同时含 specimen-paper 与 insert，应判为 source_material。
_SLUG_TOKEN_TO_TYPE = [
    ("confidential-instructions", DOC_CONFIDENTIAL_INSTRUCTIONS),
    ("examiner-report", DOC_EXAMINER_REPORT),
    ("specimen-mark-scheme", DOC_SPECIMEN_MARK_SCHEME),
    ("mark-scheme", DOC_MARK_SCHEME),
    ("formula-booklet", DOC_FORMULA_BOOKLET),
    ("data-booklet", DOC_DATA_BOOKLET),
    ("insert", DOC_INSERT),
    ("specimen-paper", DOC_SPECIMEN_PAPER),
    ("question-paper", DOC_QUESTION_PAPER),
]


def parse_slug(url: str) -> Optional[ParsedResource]:
    """从 /Images/{id}-{descriptive-slug}.pdf 的 slug 部分解析，作为交叉校验。"""
    m = re.search(r"/Images/(?:\d+-)?([a-z0-9\-]+)\.pdf", url, re.I)
    if not m:
        return None
    slug = m.group(1).lower()

    doc_type = DOC_OTHER
    is_specimen = "specimen" in slug
    # 先匹配更具体的 token
    for token, dtype in _SLUG_TOKEN_TO_TYPE:
        if token in slug:
            if dtype == DOC_MARK_SCHEME and is_specimen:
                doc_type = DOC_SPECIMEN_MARK_SCHEME
            elif dtype == DOC_QUESTION_PAPER and is_specimen:
                doc_type = DOC_SPECIMEN_PAPER
            else:
                doc_type = dtype
            break

    year = None
    my = re.search(r"\b(20\d{2})\b", slug)
    if my:
        year = int(my.group(1))

    series = None
    for word, canon in _SERIES_WORDS.items():
        if re.search(rf"(^|[-]){word}([-]|$)", slug):
            series = canon
            break

    paper_code = None
    mp = re.search(r"paper-(\d{1,2})(?:$|-)", slug)
    if mp:
        paper_code = mp.group(1).zfill(2) if len(mp.group(1)) == 1 else mp.group(1)

    return ParsedResource(
        doc_type=doc_type,
        confidence=0.5,
        year=year,
        series=series,
        paper_code=paper_code,
        is_specimen=is_specimen,
        evidence={"slug": slug},
    )


def cross_check(label_parsed: ParsedResource, slug_parsed: Optional[ParsedResource]) -> dict[str, Any]:
    """锚文本与 slug 交叉校验，返回一致性证据。

    不一致时降置信度并交由校验层决定是否转人工 —— 不静默丢弃。
    """
    if slug_parsed is None:
        return {"slug_available": False, "agree": None}

    mismatches: list[str] = []
    for field_name in ("doc_type", "year", "series", "paper_code"):
        a = getattr(label_parsed, field_name)
        b = getattr(slug_parsed, field_name)
        if a is not None and b is not None and a != b:
            mismatches.append(f"{field_name}: label={a!r} slug={b!r}")

    return {
        "slug_available": True,
        "agree": not mismatches,
        "mismatches": mismatches,
        "slug_doc_type": slug_parsed.doc_type,
    }


def split_paper_code(paper_code: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """把 Cambridge 两位 paper code 拆为 (component, variant)。

    注意：这是**暂定解释**，必须由 syllabus structure 表校验（见 research §8 待补项）。
    解释结果与原始 paper_code 同时保留，解释失败不丢信息。
    """
    if not paper_code:
        return None, None
    digits = re.sub(r"\D", "", paper_code)
    if len(digits) >= 2:
        return digits[0], digits[1]
    if len(digits) == 1:
        return digits[0], None
    return None, None
