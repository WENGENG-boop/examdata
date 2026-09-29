"""Mark Scheme 解析与匹配的通用契约。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol


@dataclass
class MarkSchemeEntryDraft:
    """从 Mark Scheme 抽取的一条评分条目。"""

    number_label: str
    number_path: str
    answer_text: Optional[str] = None
    marks: Optional[int] = None
    acceptable_answers: list[str] = field(default_factory=list)
    method_marks: Optional[int] = None
    accuracy_marks: Optional[int] = None
    independent_marks: Optional[int] = None
    ecf: Optional[bool] = None
    guidance: Optional[str] = None
    partial_marks: Optional[str] = None
    raw: dict[str, Any] = field(default_factory=dict)
    parse_confidence: float = 0.0


@dataclass
class MarkSchemeDraft:
    """一份 Mark Scheme 的解析结果。"""

    entries: list[MarkSchemeEntryDraft] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    findings: list[dict[str, Any]] = field(default_factory=list)


class MarkSchemeParser(Protocol):
    """考试局各自的 Mark Scheme 解析器。"""

    key: str

    def parse(self, document) -> MarkSchemeDraft:  # pragma: no cover - 协议
        ...


@dataclass
class LinkResult:
    """题目级关联结果。"""

    linked: list[tuple[int, int]] = field(default_factory=list)  # (entry_idx, question_id)
    unmatched_entries: list[str] = field(default_factory=list)
    questions_without_entry: list[str] = field(default_factory=list)
    coverage: float = 0.0
    confidence: float = 0.0
    method: str = "exact_path"
