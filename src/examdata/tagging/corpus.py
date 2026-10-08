"""从库里取内容点与题目，拼成 BM25 文档与候选范围。

内容点文档（``doc_for``）由三段加权合并，权重固定：

    point.name × 3   —— 大纲条目本身，最短最准
    attrs.text × 1   —— 大纲原文（与 name 常重合，因此等价于把自身句子再加重一次）
    祖先链名字 × 1   —— unit / topic / subtopic 的名字，提供上下文

IDF 语料 = **该科目全部 point**：索引按科目分组构建，
单元约束只用来收窄候选，不改变 IDF 与文档长度统计，
这样同一道题无论落在哪个单元，分数量纲都一致。

单元约束的解析顺序：
1. ``paper.attrs["unit_code"]``（论文管道落库时写入，如 "WBI11"）；
2. ``document.paper_code`` 的前缀（如 "wbi11-01" → "WBI11"）；
3. 都没有 → 退化为该科目全部 point。

科目解析顺序：unit 节点的 ``attrs["subject"]`` → ``document.subject_id`` 对应
Subject 的 slug / code。都拿不到时该题不标注（计入 skipped_no_subject），
而不是拿全库内容点去猜。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Optional, Sequence

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..core.models import Board, Document, Paper, Question, Subject, TaxonomyNode
from .bm25 import Bm25Index, Doc

BOARD_KEY = "edexcel"

NAME_WEIGHT = 3.0
TEXT_WEIGHT = 1.0
ANCESTOR_WEIGHT = 1.0

MAX_ANCESTOR_DEPTH = 8

# 单元代码形如 WBI11 / WAC01：字母开头 + 两位以上数字，后面不能再跟字母数字。
_UNIT_PREFIX_RE = re.compile(r"^\s*([A-Za-z]{1,4}\d{2,3})(?![A-Za-z0-9])")


@dataclass(frozen=True)
class PointCandidate:
    """一个可被挂载的内容点（taxonomy_node.node_type == "point"）。"""

    node_id: int
    code: str
    name: str
    text: str
    subject: Optional[str]
    unit_code: Optional[str]
    ancestors: tuple[str, ...]


@dataclass(frozen=True)
class QuestionRef:
    """一道待标注的题，连同它的科目与单元线索。"""

    question_id: int
    number_label: str
    stem_text: str
    paper_code: Optional[str]
    subject_code: Optional[str]
    subject_slug: Optional[str]
    unit_code: Optional[str]


def doc_for(
    point: PointCandidate,
    *,
    name_weight: float = NAME_WEIGHT,
    text_weight: float = TEXT_WEIGHT,
    ancestor_weight: float = ANCESTOR_WEIGHT,
) -> Doc:
    fields: dict[str, tuple[float, str]] = {"name": (name_weight, point.name)}
    if point.text:
        fields["text"] = (text_weight, point.text)
    if point.ancestors:
        fields["ancestors"] = (ancestor_weight, " ".join(point.ancestors))
    return Doc(key=point.code, fields=fields)


def unit_code_from_paper(paper_attrs: Any, paper_code: Any) -> Optional[str]:
    """从 paper.attrs["unit_code"] 或 paper_code 前缀解析单元代码。"""
    if isinstance(paper_attrs, dict):
        value = paper_attrs.get("unit_code")
        if isinstance(value, str) and value.strip():
            return value.strip().upper()
    if isinstance(paper_code, str):
        match = _UNIT_PREFIX_RE.match(paper_code)
        if match:
            return match.group(1).upper()
    return None


def load_points(session: Session, *, board_key: str = BOARD_KEY) -> list[PointCandidate]:
    """读出该考试局全部内容点，并解析各自的祖先链与单元代码。"""
    board = session.scalar(select(Board).where(Board.key == board_key))
    if board is None:
        return []
    nodes = list(session.scalars(select(TaxonomyNode).where(TaxonomyNode.board_id == board.id)))
    by_id = {node.id: node for node in nodes}
    out: list[PointCandidate] = []
    for node in nodes:
        if node.node_type != "point":
            continue
        attrs = node.attrs if isinstance(node.attrs, dict) else {}
        chain: list[str] = []
        unit_code: Optional[str] = None
        parent_id = node.parent_id
        depth = 0
        while parent_id is not None and depth < MAX_ANCESTOR_DEPTH:
            parent = by_id.get(parent_id)
            if parent is None:
                break
            chain.append(parent.name)
            if unit_code is None and parent.node_type == "unit":
                unit_code = parent.code
            parent_id = parent.parent_id
            depth += 1
        if unit_code is None:
            fallback = attrs.get("unit_key")
            unit_code = fallback if isinstance(fallback, str) and fallback.strip() else None
        subject = attrs.get("subject")
        out.append(
            PointCandidate(
                node_id=node.id,
                code=node.code,
                name=node.name,
                text=str(attrs.get("text") or ""),
                subject=subject if isinstance(subject, str) else None,
                unit_code=unit_code.upper() if unit_code else None,
                ancestors=tuple(chain),
            )
        )
    out.sort(key=lambda point: point.code)
    return out


class SubjectCorpus:
    """单科目的内容点索引。IDF 语料 = 该科目全部 point。"""

    def __init__(self, subject: str, points: Sequence[PointCandidate]) -> None:
        self.subject = subject
        self.points = list(points)
        self.index = Bm25Index([doc_for(point) for point in self.points])
        self._position = {point.code: position for position, point in enumerate(self.points)}
        self._by_unit: dict[str, set[int]] = {}
        for position, point in enumerate(self.points):
            if point.unit_code:
                self._by_unit.setdefault(point.unit_code.upper(), set()).add(position)

    def candidate_positions(self, unit_code: Optional[str]) -> set[int]:
        """单元约束：命中该单元的后代 point；拿不到单元时退化为全科目。"""
        if unit_code:
            allowed = self._by_unit.get(unit_code.upper())
            if allowed:
                return set(allowed)
        return set(range(len(self.points)))

    def rank(self, text: Optional[str], allowed: set[int]) -> list[tuple[int, float]]:
        """按 BM25 降序返回 (位置, 分数)，只保留在 allowed 内且分数 > 0 的候选。"""
        out: list[tuple[int, float]] = []
        for code, score in self.index.score(text):
            position = self._position.get(code)
            if position is not None and position in allowed:
                out.append((position, score))
        return out


class CorpusSet:
    """按科目分组的语料集合，外加 unit → subject 的归属索引。"""

    def __init__(self, points: Iterable[PointCandidate]) -> None:
        self.points = list(points)
        grouped: dict[str, list[PointCandidate]] = {}
        for point in self.points:
            key = (point.subject or "").strip().lower()
            if key:
                grouped.setdefault(key, []).append(point)
        self._corpora = {key: SubjectCorpus(key, value) for key, value in grouped.items()}
        self._unit_subject: dict[str, str] = {}
        for point in self.points:
            if point.unit_code and point.subject:
                self._unit_subject.setdefault(point.unit_code.upper(), point.subject.strip().lower())

    @property
    def subjects(self) -> list[str]:
        return sorted(self._corpora)

    def corpus_for(self, subject: str | None) -> Optional[SubjectCorpus]:
        if not subject:
            return None
        return self._corpora.get(subject.strip().lower())

    def resolve_subject(
        self, *, unit_code: Optional[str], subject_candidates: Sequence[Optional[str]]
    ) -> Optional[str]:
        if unit_code:
            hit = self._unit_subject.get(unit_code.upper())
            if hit and hit in self._corpora:
                return hit
        for candidate in subject_candidates:
            if not candidate:
                continue
            key = candidate.strip().lower()
            if key in self._corpora:
                return key
        return None


def iter_questions(
    session: Session,
    *,
    board_key: str = BOARD_KEY,
    subject: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[QuestionRef]:
    """按题号顺序读出该考试局的题，附上科目与单元线索。"""
    stmt = (
        select(
            Question.id,
            Question.number_label,
            Question.stem_text,
            Document.paper_code,
            Paper.attrs,
            Subject.code,
            Subject.slug,
        )
        .join(Paper, Paper.id == Question.paper_id)
        .join(Document, Document.id == Paper.document_id)
        .join(Board, Board.id == Document.board_id)
        .join(Subject, Subject.id == Document.subject_id, isouter=True)
        .where(Board.key == board_key)
        .order_by(Question.id)
    )
    if subject:
        key = subject.strip().lower()
        stmt = stmt.where(or_(Subject.code == key, Subject.slug == key))
    if limit is not None:
        stmt = stmt.limit(limit)

    out: list[QuestionRef] = []
    for qid, number_label, stem, paper_code, paper_attrs, subject_code, subject_slug in session.execute(stmt):
        out.append(
            QuestionRef(
                question_id=qid,
                number_label=number_label or "",
                stem_text=stem or "",
                paper_code=paper_code,
                subject_code=subject_code,
                subject_slug=subject_slug,
                unit_code=unit_code_from_paper(paper_attrs, paper_code),
            )
        )
    return out


__all__ = [
    "ANCESTOR_WEIGHT",
    "BOARD_KEY",
    "CorpusSet",
    "NAME_WEIGHT",
    "PointCandidate",
    "QuestionRef",
    "SubjectCorpus",
    "TEXT_WEIGHT",
    "doc_for",
    "iter_questions",
    "load_points",
    "unit_code_from_paper",
]
