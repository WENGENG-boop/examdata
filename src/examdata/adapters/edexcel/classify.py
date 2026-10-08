"""Pearson Edexcel 的文件类型与元数据映射。

与 Cambridge 最大的实现差异：**Edexcel 的元数据是结构化的**。
资源记录里直接带 category 数组，给出 Document-Type / Exam-Series / Unit /
Specification-Code，不需要从锚文本里解析。

因此这里不做"锚文本正则匹配"，只做两件事：
1. 把 Edexcel 的 Document-Type 取值映射到系统统一词汇；
2. 从 category 数组抽取统一字段。

保留 Edexcel 特有属性（unit / spec_code / exam_series 原始值），
不为了统一而丢弃。
"""

from __future__ import annotations

import re
from typing import Any, Optional

DOC_QUESTION_PAPER = "question_paper"
DOC_MARK_SCHEME = "mark_scheme"
DOC_EXAMINER_REPORT = "examiner_report"
DOC_SPECIMEN_PAPER = "specimen_paper"
DOC_SPECIMEN_MARK_SCHEME = "specimen_mark_scheme"
DOC_SOURCE_MATERIAL = "source_material"
DOC_OTHER = "other"

# Edexcel 的 Document-Type 取值 -> 统一词汇。
# 注意大小写不统一（实测同时存在 "Mark-scheme" 与 "Mark-Scheme"），
# 因此查表前必须 lower()。
_DOC_TYPE_MAP: dict[str, str] = {
    "question-paper": DOC_QUESTION_PAPER,
    "modified-question-paper": DOC_QUESTION_PAPER,
    "mark-scheme": DOC_MARK_SCHEME,
    "examiner-report": DOC_EXAMINER_REPORT,
    "specimen-paper-and-mark-scheme": DOC_SPECIMEN_PAPER,
    "exemplar-material": DOC_SOURCE_MATERIAL,
    "sample-assessment-material": DOC_SOURCE_MATERIAL,
    "past-training-content": DOC_OTHER,
    "skills-for-learning-and-work": DOC_OTHER,
    "qualification-guides": DOC_OTHER,
    "scheme-of-work": DOC_OTHER,
    "specification": DOC_OTHER,
    "notice": DOC_OTHER,
}

# 从文件名推断的兜底（仅在 category 缺 Document-Type 时使用）。
# 实测后缀不可靠，所以只作兜底，绝不作为主判据。
_FILENAME_HINTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"[-_]rms[-_.]|[-_]msc[-_.]", re.I), DOC_MARK_SCHEME),
    (re.compile(r"[-_]pef[-_.]", re.I), DOC_EXAMINER_REPORT),
    (re.compile(r"[-_]que[-_.]", re.I), DOC_QUESTION_PAPER),
]

# 门禁路径前缀。实测 gating 字段恒为 false（IGCSE 全部 9,272 条），
# 因此**必须**用 URL 前缀判定，不能信 gating。
_SECURE_PREFIXES = ("/content/dam/secure/", "/content/dam/gold/", "/content/dam/silver/")


def category_value(categories: list[str], prefix: str) -> Optional[str]:
    """从 category 数组取某个前缀后的值。"""
    marker = prefix + "/"
    for c in categories or []:
        if isinstance(c, str) and c.startswith(marker):
            return c[len(marker):]
    return None


def map_doc_type(raw: Optional[str], url: str = "") -> tuple[str, float, str]:
    """把 Edexcel 的 Document-Type 映射到统一词汇。

    返回 (doc_type, confidence, method)。confidence 反映判据可靠程度：
    category 结构化字段最可信；文件名兜底只能给中等置信度。
    """
    if raw:
        mapped = _DOC_TYPE_MAP.get(raw.strip().lower())
        if mapped:
            return mapped, 0.95, "category"
    for pat, mapped in _FILENAME_HINTS:
        if pat.search(url):
            return mapped, 0.6, "filename"
    return DOC_OTHER, 0.2, "none"


def is_gated(url: str) -> bool:
    """门禁判定：只看 URL 前缀。

    实测 gating 字段不可信——IGCSE 全部 9,272 条记录 gating 都是 false，
    包括 /content/dam/secure/ 下的记录。信它会漏判全部登录墙资源。
    """
    return any(p in url for p in _SECURE_PREFIXES)


def normalize_exam_series(raw: Optional[str]) -> Optional[str]:
    """考季归一化：Edexcel 用 "June 2022" 与 "June-2022" 两种写法并存。

    统一成 "june 2022" 形式（与 Cambridge 侧一致），便于跨考试局检索。
    """
    if not raw:
        return None
    text = raw.strip()
    m = re.match(
        r"^(January|February|March|April|May|June|July|August|September|October|November|December)"
        r"[\s\-]+(\d{4})$",
        text,
        re.I,
    )
    if m:
        return f"{m.group(1).lower()} {m.group(2)}"
    return text.lower()


def series_year(raw: Optional[str]) -> Optional[int]:
    if not raw:
        return None
    m = re.search(r"(\d{4})", raw)
    return int(m.group(1)) if m else None


def extract_metadata(categories: list[str], url: str) -> dict[str, Any]:
    """从 category 数组抽统一字段，同时保留 Edexcel 特有属性。"""
    raw_doc_type = category_value(categories, "Pearson-UK:Document-Type")
    doc_type, confidence, method = map_doc_type(raw_doc_type, url)

    raw_series = category_value(categories, "Pearson-UK:Exam-Series")
    spec_code = category_value(categories, "Pearson-UK:Specification-Code")
    unit = category_value(categories, "Pearson-UK:Unit")
    subject = category_value(categories, "Pearson-UK:Qualification-Subject")
    family = category_value(categories, "Pearson-UK:Qualification-Family")
    category = category_value(categories, "Pearson-UK:Category")

    return {
        "doc_type": doc_type,
        "confidence": confidence,
        "classify_method": method,
        "raw_doc_type": raw_doc_type,
        "series": normalize_exam_series(raw_series),
        "year": series_year(raw_series),
        "subject_title": subject,
        "qualification_name": family,
        "spec_code": spec_code,
        "unit": unit,
        # 统一字段：Edexcel 的 unit 即试卷标识
        "paper_code": unit,
        "category": category,
        "is_gated": is_gated(url),
        "edexcel": {
            "specification_code": spec_code,
            "unit": unit,
            "category": category,
            "family": family,
            "raw_document_type": raw_doc_type,
            "raw_exam_series": raw_series,
            "gated": is_gated(url),
        },
    }


def identity_parts(meta: dict[str, Any], url: str) -> str:
    """身份键：用结构化字段，不用 URL。

    同一份文档在公开路径与门禁路径下的 URL 不同，且 Pearson 换路径会变；
    用 URL 做身份会导致同一文档被重复入库。
    """
    from ...core.ids import identity_key

    filename = url.rsplit("/", 1)[-1]
    return identity_key(
        "edexcel",
        meta.get("qualification_name") or "",
        meta.get("spec_code") or "",
        meta.get("series") or "",
        meta.get("unit") or "",
        meta.get("doc_type") or "",
        filename,
    )
