"""检索与抽题：题目级数据底座对外的主要读取入口。

设计原则（需求文档"试卷检索能力"/"题目检索能力"/"随机抽题"）：
- 上层应用只依赖这里的统一概念，不需要理解各考试局原始站点结构。
- 检索维度覆盖考试局、考试体系、科目、科目代码、年份、考试季、Paper、
  Component、Variant、Level，以及题目级的题号、分值、层级、知识点、难度。
- 组卷/抽题只做"按条件选题"，不含任何学生端逻辑。
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.models import (
    Artifact,
    Asset,
    Board,
    Difficulty,
    Document,
    DocumentRevision,
    ExamSeries,
    MarkScheme,
    MarkSchemeEntry,
    OfficialAnswer,
    Paper,
    ParseRun,
    Question,
    QuestionAsset,
    QuestionSimilarity,
    QuestionTaxonomy,
    Qualification,
    ReviewTask,
    Subject,
    SyncRun,
    TaxonomyNode,
    ValidationFinding,
)


def _check_page(*, limit: int, offset: int) -> None:
    """分页参数校验：非法值直接报错，而不是交给数据库（负 limit 在 SQLite 等于不限制）。"""
    if limit < 1:
        raise ValueError(f"limit 必须大于等于 1（当前为 {limit}）")
    if offset < 0:
        raise ValueError(f"offset 不能为负数（当前为 {offset}）")


# --------------------------------------------------------------------------
# 试卷检索
# --------------------------------------------------------------------------


@dataclass
class PaperFilter:
    """试卷检索条件。所有字段可选，未给出的维度不参与过滤。"""

    board: Optional[str] = None
    qualification: Optional[str] = None
    subject_code: Optional[str] = None
    year: Optional[int] = None
    session: Optional[str] = None
    paper_code: Optional[str] = None
    component: Optional[str] = None
    variant: Optional[str] = None
    level: Optional[str] = None
    doc_type: Optional[str] = None
    limit: int = 50
    offset: int = 0


def _paper_stmt(f: PaperFilter, *, paginate: bool = True) -> Select:
    stmt = (
        select(Paper, Document, Subject, Board, ExamSeries)
        .join(Document, Document.id == Paper.document_id)
        .outerjoin(Subject, Subject.id == Document.subject_id)
        .join(Board, Board.id == Document.board_id)
        .outerjoin(ExamSeries, ExamSeries.id == Document.series_id)
    )
    if f.board:
        stmt = stmt.where(Board.key == f.board)
    if f.qualification:
        stmt = stmt.join(
            Qualification, Qualification.id == Document.qualification_id
        ).where(Qualification.key == f.qualification)
    if f.subject_code:
        stmt = stmt.where(Subject.code == f.subject_code)
    if f.year is not None:
        stmt = stmt.where(Document.year == f.year)
    if f.session:
        stmt = stmt.where(ExamSeries.session == f.session)
    if f.paper_code:
        stmt = stmt.where(Document.paper_code == f.paper_code)
    if f.component:
        stmt = stmt.where(Document.component == f.component)
    if f.variant:
        stmt = stmt.where(Document.variant == f.variant)
    if f.level:
        stmt = stmt.where(Document.level == f.level)
    if f.doc_type:
        stmt = stmt.where(Document.doc_type == f.doc_type)
    stmt = stmt.order_by(Document.year.desc(), Document.paper_code, Paper.id)
    if not paginate:
        return stmt
    return stmt.limit(f.limit).offset(f.offset)


def search_papers(session: Session, f: PaperFilter) -> list[dict[str, Any]]:
    """按考试信息检索试卷。"""
    _check_page(limit=f.limit, offset=f.offset)
    out: list[dict[str, Any]] = []
    for paper, doc, subject, board, series in session.execute(_paper_stmt(f)).all():
        out.append(
            {
                "paper_id": paper.id,
                "document_id": doc.id,
                "board": board.key,
                "board_name": board.name,
                "subject_code": subject.code if subject else None,
                "subject_title": subject.title if subject else None,
                "year": doc.year,
                "session": series.session if series else None,
                "paper_code": doc.paper_code,
                "component": doc.component,
                "variant": doc.variant,
                "level": doc.level,
                "doc_type": doc.doc_type,
                "title": doc.title,
                "duration_minutes": paper.duration_minutes,
                "marks_total": paper.marks_total,
                "question_count": paper.question_count,
                "page_count": paper.page_count,
                "status": doc.status,
            }
        )
    return out


def count_papers(session: Session, f: PaperFilter) -> int:
    """满足条件的试卷总数（分页用）。"""
    inner = _paper_stmt(f, paginate=False).subquery()
    return session.scalar(select(func.count()).select_from(inner)) or 0


# --------------------------------------------------------------------------
# 题目检索
# --------------------------------------------------------------------------


@dataclass
class QuestionFilter:
    """题目级检索条件。"""

    board: Optional[str] = None
    subject_code: Optional[str] = None
    year: Optional[int] = None
    session: Optional[str] = None
    paper_code: Optional[str] = None
    level: Optional[str] = None
    number_path: Optional[str] = None
    # 只取叶子题（可独立作答的最小单元）或只取大题
    leaves_only: bool = False
    roots_only: bool = False
    depth: Optional[int] = None
    marks_min: Optional[int] = None
    marks_max: Optional[int] = None
    keyword: Optional[str] = None
    taxonomy_code: Optional[str] = None
    taxonomy_source: Optional[str] = None
    difficulty_min: Optional[float] = None
    difficulty_max: Optional[float] = None
    difficulty_source: Optional[str] = None
    has_asset: Optional[bool] = None
    has_official_answer: Optional[bool] = None
    limit: int = 50
    offset: int = 0


def _question_stmt(f: QuestionFilter, *, paginate: bool = True) -> Select:
    stmt = (
        select(Question, Paper, Document, Board, Subject)
        .join(Paper, Paper.id == Question.paper_id)
        .join(Document, Document.id == Paper.document_id)
        .join(Board, Board.id == Document.board_id)
        .outerjoin(Subject, Subject.id == Document.subject_id)
    )
    if f.board:
        stmt = stmt.where(Board.key == f.board)
    if f.subject_code:
        stmt = stmt.where(Subject.code == f.subject_code)
    if f.year is not None:
        stmt = stmt.where(Document.year == f.year)
    if f.paper_code:
        stmt = stmt.where(Document.paper_code == f.paper_code)
    if f.level:
        stmt = stmt.where(Document.level == f.level)
    if f.session:
        stmt = stmt.join(ExamSeries, ExamSeries.id == Document.series_id).where(
            ExamSeries.session == f.session
        )
    if f.number_path:
        stmt = stmt.where(Question.number_path == f.number_path)
    if f.depth is not None:
        stmt = stmt.where(Question.depth == f.depth)
    if f.roots_only:
        stmt = stmt.where(Question.parent_id.is_(None))
    if f.leaves_only:
        parents = select(Question.parent_id).where(Question.parent_id.is_not(None))
        stmt = stmt.where(Question.id.not_in(parents))
    if f.marks_min is not None:
        stmt = stmt.where(Question.marks >= f.marks_min)
    if f.marks_max is not None:
        stmt = stmt.where(Question.marks <= f.marks_max)
    if f.keyword:
        escaped = (
            f.keyword.replace("\\", "\\\\")
            .replace("%", r"\%")
            .replace("_", r"\_")
        )
        stmt = stmt.where(Question.stem_text.ilike(f"%{escaped}%", escape="\\"))
    if f.taxonomy_code or f.taxonomy_source:
        taxonomy = select(QuestionTaxonomy.id).where(
            QuestionTaxonomy.question_id == Question.id
        )
        if f.taxonomy_code:
            taxonomy = taxonomy.join(
                TaxonomyNode, TaxonomyNode.id == QuestionTaxonomy.node_id
            ).where(TaxonomyNode.code == f.taxonomy_code)
            # 标签 code 只在 board 内唯一：给定 board 时必须把标签一起限定到
            # 该 board，否则别的 board 上的同名 code 会把题目带进来。
            # board_id 为空的旧节点保持原有行为，不因这次收窄而丢结果。
            if f.board:
                taxonomy = taxonomy.where(
                    (TaxonomyNode.board_id == Board.id)
                    | TaxonomyNode.board_id.is_(None)
                )
        if f.taxonomy_source:
            taxonomy = taxonomy.where(QuestionTaxonomy.source == f.taxonomy_source)
        stmt = stmt.where(taxonomy.exists())
    if (f.difficulty_min is not None or f.difficulty_max is not None
            or f.difficulty_source):
        difficulty = select(Difficulty.id).where(Difficulty.question_id == Question.id)
        if f.difficulty_min is not None:
            difficulty = difficulty.where(Difficulty.value >= f.difficulty_min)
        if f.difficulty_max is not None:
            difficulty = difficulty.where(Difficulty.value <= f.difficulty_max)
        if f.difficulty_source:
            difficulty = difficulty.where(Difficulty.source == f.difficulty_source)
        stmt = stmt.where(difficulty.exists())
    if f.has_asset is True:
        stmt = stmt.where(Question.id.in_(select(QuestionAsset.question_id).distinct()))
    elif f.has_asset is False:
        stmt = stmt.where(Question.id.not_in(select(QuestionAsset.question_id).distinct()))
    if f.has_official_answer is True:
        stmt = stmt.where(Question.id.in_(select(OfficialAnswer.question_id).distinct()))
    elif f.has_official_answer is False:
        stmt = stmt.where(
            Question.id.not_in(select(OfficialAnswer.question_id).distinct())
        )
    stmt = stmt.order_by(
        Document.year.desc(),
        Document.paper_code,
        Question.paper_id,
        Question.display_order,
        Question.id,
    )
    if not paginate:
        return stmt
    return stmt.limit(f.limit).offset(f.offset)


def search_questions(session: Session, f: QuestionFilter) -> list[dict[str, Any]]:
    """题目级检索。"""
    _check_page(limit=f.limit, offset=f.offset)
    return _question_rows(session, _question_stmt(f))


def _question_rows(session: Session, stmt: Select) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for q, paper, doc, board, subject in session.execute(stmt).all():
        out.append(
            {
                "question_id": q.id,
                "number_path": q.number_path,
                "depth": q.depth,
                "kind": q.kind,
                "marks": q.marks,
                "page_from": q.page_from,
                "page_to": q.page_to,
                "stem_text": q.stem_text,
                "board": board.key,
                "subject_code": subject.code if subject else None,
                "year": doc.year,
                "paper_code": doc.paper_code,
                "paper_id": paper.id,
            }
        )
    return out


def count_questions(session: Session, f: QuestionFilter) -> int:
    inner = _question_stmt(f, paginate=False).subquery()
    return session.scalar(select(func.count()).select_from(inner)) or 0


# --------------------------------------------------------------------------
# 单题 / 整卷完整内容
# --------------------------------------------------------------------------


def get_question_bundle(session: Session, question_id: int) -> Optional[dict[str, Any]]:
    """取出一道题的完整数据：题干、层级、图形资产、官方答案、评分条目。

    需求"题目被独立提取以后，不能因为拆分而丢失完成该题所需要的图片、公式或材料"。
    """
    q = session.get(Question, question_id)
    if q is None:
        return None
    paper = session.get(Paper, q.paper_id)
    doc = session.get(Document, paper.document_id) if paper else None

    children = list(
        session.scalars(
            select(Question)
            .where(Question.parent_id == q.id)
            .order_by(Question.display_order)
        ).all()
    )
    assets = [
        {
            "asset_id": asset.id,
            "storage_key": asset.storage_key,
            "mime": asset.mime,
            "kind": asset.kind,
            "width": asset.width,
            "height": asset.height,
            "role": qa.role,
            "page": qa.page,
            "bbox": qa.bbox,
        }
        for qa, asset in session.execute(
            select(QuestionAsset, Asset)
            .join(Asset, Asset.id == QuestionAsset.asset_id)
            .where(QuestionAsset.question_id == q.id)
            .order_by(QuestionAsset.reading_order)
        ).all()
    ]
    answers = [
        {"source": a.source, "content": a.content, "document_id": a.source_document_id}
        for a in session.scalars(
            select(OfficialAnswer).where(OfficialAnswer.question_id == q.id)
        ).all()
    ]
    entries = [
        {
            "mark_scheme_id": ms.id,
            "mark_scheme_document_id": msdoc.id,
            "number_path": e.number_path,
            "marks": e.marks,
            "answer_text": e.answer_text,
            "acceptable_answers": e.acceptable_answers,
            "method_marks": e.method_marks,
            "accuracy_marks": e.accuracy_marks,
            "independent_marks": e.independent_marks,
            "ecf": e.ecf,
            "guidance": e.guidance,
            "parse_confidence": e.parse_confidence,
        }
        for e, ms, msdoc in session.execute(
            select(MarkSchemeEntry, MarkScheme, Document)
            .join(MarkScheme, MarkScheme.id == MarkSchemeEntry.mark_scheme_id)
            .join(Document, Document.id == MarkScheme.document_id)
            .where(MarkSchemeEntry.question_id == q.id)
        ).all()
    ]
    taxonomy = [
        {
            "code": n.code,
            "name": n.name,
            "node_type": n.node_type,
            "source": qt.source,
            "confidence": qt.confidence,
        }
        for qt, n in session.execute(
            select(QuestionTaxonomy, TaxonomyNode)
            .join(TaxonomyNode, TaxonomyNode.id == QuestionTaxonomy.node_id)
            .where(QuestionTaxonomy.question_id == q.id)
        ).all()
    ]
    difficulty = [
        {"source": d.source, "value": d.value, "scale": d.scale, "features": d.features}
        for d in session.scalars(
            select(Difficulty).where(Difficulty.question_id == q.id)
        ).all()
    ]
    similar = similar_questions(session, q.id)
    return {
        "question": {
            "id": q.id,
            "number_label": q.number_label,
            "number_path": q.number_path,
            "depth": q.depth,
            "kind": q.kind,
            "marks": q.marks,
            "page_from": q.page_from,
            "page_to": q.page_to,
            "stem_text": q.stem_text,
            "parse_confidence": q.parse_confidence,
            "has_override": q.has_override,
            # 评分标准裁剪区（page/bbox/sha256），没有就是空列表，不改既有键。
            "ms_regions": list((q.attrs or {}).get("ms_regions") or []),
        },
        "paper": {
            "paper_id": paper.id if paper else None,
            "document_id": doc.id if doc else None,
            "paper_code": doc.paper_code if doc else None,
            "year": doc.year if doc else None,
            "doc_type": doc.doc_type if doc else None,
        },
        "children": [
            {"id": c.id, "number_path": c.number_path, "marks": c.marks, "depth": c.depth}
            for c in children
        ],
        "assets": assets,
        "official_answers": answers,
        "mark_scheme_entries": entries,
        "taxonomy": taxonomy,
        "difficulty": difficulty,
        "similar_questions": similar,
    }


def similar_questions(session: Session, question_id: int, *, limit: int = 10) -> list[dict[str, Any]]:
    """与某道题相似的其它题（需求：相似题识别）。

    相似度按 (question_a_id, question_b_id) 无序存储，这里两个方向都查。
    """
    out: list[dict[str, Any]] = []
    rows = session.execute(
        select(QuestionSimilarity, Question, Document, Paper)
        .join(
            Question,
            Question.id
            == func.coalesce(
                func.nullif(QuestionSimilarity.question_a_id, question_id),
                QuestionSimilarity.question_b_id,
            ),
        )
        .join(Paper, Paper.id == Question.paper_id)
        .join(Document, Document.id == Paper.document_id)
        .where(
            (QuestionSimilarity.question_a_id == question_id)
            | (QuestionSimilarity.question_b_id == question_id)
        )
        .order_by(QuestionSimilarity.score.desc())
        .limit(limit)
    ).all()
    for sim, other, doc, paper in rows:
        out.append(
            {
                "question_id": other.id,
                "number_path": other.number_path,
                "marks": other.marks,
                "stem_text": other.stem_text,
                "paper_id": paper.id,
                "paper_code": doc.paper_code,
                "year": doc.year,
                "document_id": doc.id,
                "score": sim.score,
                "method": sim.method,
            }
        )
    return out


def taxonomy_tree(session: Session, *, board: Optional[str] = None) -> list[dict[str, Any]]:
    """知识点体系（两层：topic -> subtopic），带题目计数。"""
    stmt = select(TaxonomyNode).order_by(TaxonomyNode.code)
    if board:
        stmt = stmt.join(Board, Board.id == TaxonomyNode.board_id).where(Board.key == board)
    nodes = list(session.scalars(stmt).all())
    counts = dict(
        session.execute(
            select(QuestionTaxonomy.node_id, func.count(QuestionTaxonomy.id)).group_by(
                QuestionTaxonomy.node_id
            )
        ).all()
    )
    by_id: dict[int, dict[str, Any]] = {
        n.id: {
            "id": n.id,
            "code": n.code,
            "name": n.name,
            "node_type": n.node_type,
            "source": n.source,
            "question_count": counts.get(n.id, 0),
            "children": [],
        }
        for n in nodes
    }
    roots: list[dict[str, Any]] = []
    for n in nodes:
        node = by_id[n.id]
        parent = by_id.get(n.parent_id) if n.parent_id else None
        if parent is None:
            roots.append(node)
        else:
            parent["children"].append(node)
    return roots


# --------------------------------------------------------------------------
# 标签（spec 知识点）-> 题目
# --------------------------------------------------------------------------


def _stem_excerpt(text: Optional[str], *, limit: int = 200) -> str:
    """题干摘要：压平空白并截断，列表页不携带整段正文。"""
    return " ".join((text or "").split())[:limit]


# --------------------------------------------------------------------------
# 答案解析：评分标准条目 -> 题目
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class AnswerEntry:
    """答案解析用到的最小条目视图（id / 题号路径 / 答案文本）。

    `official_answer` 行同样用它承载：`id` 是 official_answer.id，
    `number_path` 填题目的题号路径。
    """

    id: int
    number_path: str
    answer_text: Optional[str]


# 全小写罗马数字字符表；用于同一父题下 (i)(ii)(iii) 这类子标签的数值排序。
_ROMAN_VALUES = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}


def _entry_text(entry: AnswerEntry) -> Optional[str]:
    """条目的可用答案文本；空白一律视为缺失。"""
    text = (entry.answer_text or "").strip()
    return text or None


def _usable_entries(entries: Sequence[AnswerEntry]) -> list[AnswerEntry]:
    """按 id 去重、按 id 排序后留下有文本的条目。"""
    unique: dict[int, AnswerEntry] = {}
    for entry in entries:
        if _entry_text(entry) is not None:
            unique.setdefault(entry.id, entry)
    return [unique[entry_id] for entry_id in sorted(unique)]


def _strip_last_group(path: str) -> Optional[str]:
    """去掉末尾一个括号组：`1(a)(i)` -> `1(a)`；已是顶层题号时返回 None。"""
    match = re.search(r"\([^()]*\)$", path)
    if match is None:
        return None
    return path[: match.start()] or None


def _is_strict_descendant(path: str, ancestor: str) -> bool:
    """path 是否严格位于 ancestor 之下。

    题号语法是「主号 + 若干括号组」，因此只看前缀不够（`10(a)` 不是 `1` 的子题），
    剩余部分必须以 `(` 开头且括号组非空。
    """
    if not path.startswith(ancestor):
        return False
    rest = path[len(ancestor) :]
    return rest.startswith("(") and len(rest) > 2


def _roman_value(token: str) -> Optional[int]:
    """全小写罗马数字的数值；含非罗马字符时返回 None。"""
    if not token or any(ch not in _ROMAN_VALUES for ch in token):
        return None
    total = 0
    previous = 0
    for ch in reversed(token):
        value = _ROMAN_VALUES[ch]
        if value < previous:
            total -= value
        else:
            total += value
            previous = value
    return total


def _ordered_labels(labels: list[str]) -> list[str]:
    """同一父题下子标签的排序。

    整组都是罗马数字（(i)(ii)(iii)）时按数值，整组都是单字母（(a)(b)(c)）时按字母；
    其余（数字或混合）按「数字优先、再按文本」兜底。
    """
    tokens = [label[1:-1] if label.startswith("(") and label.endswith(")") else label for label in labels]
    if tokens and all(_roman_value(token) is not None for token in tokens):
        return sorted(labels, key=lambda label: _roman_value(label[1:-1]) or 0)
    if tokens and all(len(token) == 1 and token.isascii() and token.isalpha() for token in tokens):
        return sorted(labels)

    def fallback(label: str) -> tuple[int, int, str]:
        token = label[1:-1] if label.startswith("(") and label.endswith(")") else label
        if token.isdigit():
            return (0, int(token), token)
        return (1, 0, token)

    return sorted(labels, key=fallback)


def _ancestor_paths(number_path: str) -> list[str]:
    """严格祖先路径，由近到远：`1(a)(i)` -> [`1(a)`, `1`]。"""
    ancestors: list[str] = []
    current = _strip_last_group(number_path)
    while current:
        ancestors.append(current)
        current = _strip_last_group(current)
    return ancestors


def _descendant_blocks(root: str, entries: Sequence[AnswerEntry]) -> list[str]:
    """把 root 之下的条目按题号树序（父先于子）聚合成文本块。

    块内保留子题标签（相对 root 的括号组），例如 `(a) 5`、`(a)(i) 3`。
    """
    nodes: dict[str, list[AnswerEntry]] = {}
    for entry in entries:
        nodes.setdefault(entry.number_path, []).append(entry)
    # 中间层可能没有条目（如 root=1 时只有 1(a)(i)），因此要沿父链补齐节点。
    children: dict[str, set[str]] = {}
    for path in nodes:
        current = path
        parent = _strip_last_group(current)
        while parent is not None and (parent == root or _is_strict_descendant(parent, root)):
            children.setdefault(parent, set()).add(current)
            current = parent
            parent = _strip_last_group(current)

    blocks: list[str] = []

    def walk(parent: str) -> None:
        kids = children.get(parent)
        if not kids:
            return
        labels = _ordered_labels(sorted({kid[len(parent) :] for kid in kids}))
        for label in labels:
            child = parent + label
            # 展示用标签相对 root，保留层级：root=1 时子题显示 (b)(i) 而不是 (i)
            display = child[len(root) :]
            for entry in sorted(nodes.get(child, ()), key=lambda item: item.id):
                text = _entry_text(entry)
                if text is not None:
                    blocks.append(f"{display} {text}")
            walk(child)

    walk(root)
    return blocks


def resolve_answer(
    number_path: str,
    *,
    exact_entries: Sequence[AnswerEntry] = (),
    entries_by_path: Mapping[str, Sequence[AnswerEntry]] = {},
    official_entries: Sequence[AnswerEntry] = (),
) -> Optional[dict[str, Any]]:
    """把一道题解析到答案，优先级 exact -> ancestor -> descendants。

    - exact：题目自己的 official_answer，question_id 直连的 MS 条目，或同路径条目；
    - ancestor：`entries_by_path` 里最近的严格祖先路径（逐级去掉末尾括号组）；
    - descendants：`entries_by_path` 里严格位于该题之下的条目，按题号树序聚合。

    `entries_by_path` 只放「匹配到该题所在 QP 文档的 MS」的条目；条目文本为空白视为
    缺失，继续往下一级兜底。都没有则返回 None。
    """
    official = _usable_entries(official_entries)
    if official:
        return {
            "source": "exact",
            "text": "\n\n".join(_entry_text(entry) or "" for entry in official),
            "number_path": number_path,
            "entry_ids": [entry.id for entry in official],
        }
    exact = _usable_entries([*exact_entries, *entries_by_path.get(number_path, ())])
    if exact:
        return {
            "source": "exact",
            "text": "\n\n".join(_entry_text(entry) or "" for entry in exact),
            "number_path": number_path,
            "entry_ids": [entry.id for entry in exact],
        }
    for ancestor in _ancestor_paths(number_path):
        matched = _usable_entries(entries_by_path.get(ancestor, ()))
        if matched:
            return {
                "source": "ancestor",
                "text": "\n\n".join(_entry_text(entry) or "" for entry in matched),
                "number_path": ancestor,
                "entry_ids": [entry.id for entry in matched],
            }
    descendants = _usable_entries(
        [
            entry
            for path, path_entries in entries_by_path.items()
            if _is_strict_descendant(path, number_path)
            for entry in path_entries
        ]
    )
    blocks = _descendant_blocks(number_path, descendants)
    if blocks:
        return {
            "source": "descendants",
            "text": "\n\n".join(blocks),
            "number_path": number_path,
            "entry_ids": [entry.id for entry in descendants],
        }
    return None


def _page_answers(session: Session, rows: Sequence[Any]) -> list[Optional[dict[str, Any]]]:
    """按页批量解析答案：先一次性读入该页 QP 文档匹配到的全部 MS 条目，再逐题在内存里解析。

    条目按 QP 文档分组：同一页可能混有多份试卷，只有匹配到该题所在 QP 文档的
    MS 条目才参与解析，避免同题号条目跨卷串入。
    """
    question_ids = [question.id for _link, question, _paper, _doc, _subject, _series, _node in rows]
    document_ids = sorted({document.id for _link, _q, _paper, document, _s, _se, _n in rows})
    entries_by_doc: dict[int, dict[str, list[AnswerEntry]]] = {}
    if document_ids:
        for doc_id, entry_id, path, text in session.execute(
            select(
                MarkScheme.matched_paper_document_id,
                MarkSchemeEntry.id,
                MarkSchemeEntry.number_path,
                MarkSchemeEntry.answer_text,
            )
            .join(MarkSchemeEntry, MarkSchemeEntry.mark_scheme_id == MarkScheme.id)
            .where(MarkScheme.matched_paper_document_id.in_(document_ids))
            .order_by(MarkSchemeEntry.id)
        ):
            if path:
                entries_by_doc.setdefault(doc_id, {}).setdefault(path, []).append(
                    AnswerEntry(entry_id, path, text)
                )
    exact_by_question: dict[int, list[AnswerEntry]] = {}
    official_by_question: dict[int, list[AnswerEntry]] = {}
    if question_ids:
        for entry_id, question_id, path, text in session.execute(
            select(
                MarkSchemeEntry.id,
                MarkSchemeEntry.question_id,
                MarkSchemeEntry.number_path,
                MarkSchemeEntry.answer_text,
            )
            .where(MarkSchemeEntry.question_id.in_(question_ids))
            .order_by(MarkSchemeEntry.id)
        ):
            exact_by_question.setdefault(question_id, []).append(
                AnswerEntry(entry_id, path or "", text)
            )
        for answer_id, question_id, content in session.execute(
            select(OfficialAnswer.id, OfficialAnswer.question_id, OfficialAnswer.content)
            .where(OfficialAnswer.question_id.in_(question_ids))
            .order_by(OfficialAnswer.id)
        ):
            official_by_question.setdefault(question_id, []).append(
                AnswerEntry(answer_id, "", content)
            )
    return [
        resolve_answer(
            question.number_path,
            exact_entries=exact_by_question.get(question.id, ()),
            entries_by_path=entries_by_doc.get(document.id, {}),
            official_entries=official_by_question.get(question.id, ()),
        )
        for _link, question, _paper, document, _subject, _series, _node in rows
    ]


def tagged_questions(
    session: Session,
    *,
    board: str,
    taxonomy_code: str,
    subject_code: Optional[str] = None,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    session_name: Optional[str] = None,
    paper_code: Optional[str] = None,
    min_confidence: Optional[float] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """某个 spec 标签下的全部题目（题号、分值、来源试卷）。

    标签是 `taxonomy_node.code`，只在 board 内唯一，因此必须按
    (board, code) 定位节点；再沿 question_taxonomy -> question -> paper ->
    document 取回题目与来源试卷。`total` 是过滤后的总数，不受分页影响。

    每题的 `answer` 字段由 `resolve_answer` 按 exact / ancestor / descendants
    解析评分标准得到，解析所需的 MS 条目按页批量载入。
    """
    _check_page(limit=limit, offset=offset)
    stmt = (
        select(
            QuestionTaxonomy,
            Question,
            Paper,
            Document,
            Subject,
            ExamSeries,
            TaxonomyNode,
        )
        .join(TaxonomyNode, TaxonomyNode.id == QuestionTaxonomy.node_id)
        .join(Question, Question.id == QuestionTaxonomy.question_id)
        .join(Paper, Paper.id == Question.paper_id)
        .join(Document, Document.id == Paper.document_id)
        .outerjoin(Subject, Subject.id == Document.subject_id)
        .outerjoin(ExamSeries, ExamSeries.id == Document.series_id)
        .join(Board, Board.id == TaxonomyNode.board_id)
        .where(Board.key == board, TaxonomyNode.code == taxonomy_code)
    )
    if subject_code:
        stmt = stmt.where(Subject.code == subject_code)
    if year_from is not None:
        stmt = stmt.where(Document.year >= year_from)
    if year_to is not None:
        stmt = stmt.where(Document.year <= year_to)
    if session_name:
        stmt = stmt.where(ExamSeries.session == session_name)
    if paper_code:
        stmt = stmt.where(Document.paper_code == paper_code)
    if min_confidence is not None:
        stmt = stmt.where(QuestionTaxonomy.confidence >= min_confidence)

    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = session.execute(
        stmt.order_by(
            Document.year.desc(),
            Document.paper_code,
            Question.paper_id,
            Question.display_order,
            Question.id,
        )
        .limit(limit)
        .offset(offset)
    ).all()
    answers = _page_answers(session, rows)
    items = [
        {
            "question_id": question.id,
            "number_path": question.number_path,
            "marks": question.marks,
            "subject_code": subject.code if subject else None,
            "year": document.year,
            "session": series.session if series else None,
            "paper_code": document.paper_code,
            "taxonomy_code": node.code,
            "taxonomy_name": node.name,
            "confidence": link.confidence,
            "source": link.source,
            "assigned_by": link.assigned_by,
            "stem_excerpt": _stem_excerpt(question.stem_text),
            "answer": answer,
        }
        for (link, question, _paper, document, subject, series, node), answer in zip(rows, answers)
    ]
    return {"total": total, "items": items}


def _node_subject(node: TaxonomyNode, by_id: dict[int, TaxonomyNode]) -> Optional[str]:
    """节点所属科目：自身 attrs 优先，缺省沿 parent 链继承。

    spec 装载器写 `attrs["subject"]`，Cambridge 种子写
    `attrs["subject_code"]`，两种键都认，取第一个非空值。
    """
    seen: set[int] = set()
    current: Optional[TaxonomyNode] = node
    while current is not None and current.id not in seen:
        seen.add(current.id)
        attrs = current.attrs or {}
        value = attrs.get("subject") or attrs.get("subject_code")
        if value:
            return value
        current = by_id.get(current.parent_id) if current.parent_id else None
    return None


def _natural_key(code: str) -> tuple[Any, ...]:
    """code 的自然排序键：`1.2` 排在 `1.10` 前，且对任意字符串稳定。"""
    parts: list[tuple[int, Any]] = []
    for part in re.split(r"(\d+)", code):
        if not part:
            continue
        parts.append((0, int(part)) if part.isdigit() else (1, part))
    return tuple(parts)


def tag_overview(
    session: Session,
    *,
    board: str,
    subject_code: Optional[str] = None,
    include_zero: bool = True,
) -> list[dict[str, Any]]:
    """某个考试局的 spec 标签树（unit -> topic -> subtopic -> point）。

    每个节点带两个题数：

    - `direct_questions`：直接挂在该标签上的题数；
    - `subtree_questions`：该标签及其全部后代的题数（"这个标签下可选题数"）。

    计数在 Python 侧沿 parent 链聚合，排序用 code 自然序，结果确定可复现。
    `include_zero=False` 时剪掉整棵子树都没有题目的标签。
    """
    board_id = session.scalar(select(Board.id).where(Board.key == board))
    if board_id is None:
        return []
    nodes = list(
        session.scalars(
            select(TaxonomyNode).where(TaxonomyNode.board_id == board_id)
        ).all()
    )
    by_id = {node.id: node for node in nodes}
    if subject_code:
        kept = {n.id for n in nodes if _node_subject(n, by_id) == subject_code}
        nodes = [n for n in nodes if n.id in kept]
    else:
        kept = set(by_id)
    direct = dict(
        session.execute(
            select(
                QuestionTaxonomy.node_id,
                func.count(func.distinct(QuestionTaxonomy.question_id)),
            )
            .join(TaxonomyNode, TaxonomyNode.id == QuestionTaxonomy.node_id)
            .where(TaxonomyNode.board_id == board_id)
            .group_by(QuestionTaxonomy.node_id)
        ).all()
    )

    children: dict[Optional[int], list[TaxonomyNode]] = {}
    for node in nodes:
        parent_id = node.parent_id if node.parent_id in kept else None
        children.setdefault(parent_id, []).append(node)

    def build(node: TaxonomyNode) -> dict[str, Any]:
        branch = [
            build(child)
            for child in sorted(
                children.get(node.id, []), key=lambda n: _natural_key(n.code)
            )
        ]
        own = direct.get(node.id, 0)
        return {
            "id": node.id,
            "code": node.code,
            "name": node.name,
            "node_type": node.node_type,
            "direct_questions": own,
            "subtree_questions": own + sum(
                child["subtree_questions"] for child in branch
            ),
            "children": branch,
        }

    def prune(node: dict[str, Any]) -> dict[str, Any]:
        node["children"] = [
            prune(child)
            for child in node["children"]
            if child["subtree_questions"] > 0
        ]
        return node

    roots = [
        build(root)
        for root in sorted(children.get(None, []), key=lambda n: _natural_key(n.code))
    ]
    if include_zero:
        return roots
    return [prune(root) for root in roots if root["subtree_questions"] > 0]


def _current_revision_pdf(session: Session, document: Document) -> bytes:
    """文档当前发布版本的原始 PDF 字节。"""
    if document.current_revision_id is None:
        raise ValueError(f"文档 {document.id} 没有当前版本（current revision），无法裁剪")
    revision = session.get(DocumentRevision, document.current_revision_id)
    if revision is None or revision.document_id != document.id:
        raise ValueError(f"文档 {document.id} 的当前版本记录缺失或不一致，无法裁剪")
    artifact = session.get(Artifact, revision.artifact_id)
    if artifact is None:
        raise ValueError(f"文档 {document.id} 的当前版本没有内容对象，无法裁剪")
    path = get_settings().artifacts_dir / artifact.storage_key
    if not path.is_file():
        raise ValueError(f"内容对象文件缺失：{path}")
    return path.read_bytes()


def _ms_crops(session: Session, question: Question) -> list[dict[str, Any]]:
    """按 `question.attrs["ms_regions"]` 存的 sha256/page/bbox 渲染评分标准区。"""
    regions = list((question.attrs or {}).get("ms_regions") or [])
    if not regions:
        raise ValueError(f"题目 {question.id} 没有 ms_regions（评分标准裁剪区），无法裁剪")
    import pymupdf

    data_cache: dict[str, bytes] = {}
    crops: list[dict[str, Any]] = []
    for index, region in enumerate(regions, 1):
        sha256 = region.get("sha256")
        if not sha256:
            raise ValueError(f"题目 {question.id} 的 ms_regions 第 {index} 项缺少 sha256")
        if sha256 not in data_cache:
            artifact = session.scalar(select(Artifact).where(Artifact.sha256 == sha256))
            if artifact is None:
                raise ValueError(
                    f"题目 {question.id} 的 ms_regions 指向的内容对象不存在"
                    f"（sha256={str(sha256)[:12]}）"
                )
            path = get_settings().artifacts_dir / artifact.storage_key
            if not path.is_file():
                raise ValueError(f"内容对象文件缺失：{path}")
            data_cache[sha256] = path.read_bytes()
        page_no = region.get("page")
        bbox = region.get("bbox")
        if isinstance(page_no, float) and page_no.is_integer():
            page_no = int(page_no)
        if (
            not isinstance(page_no, int)
            or not isinstance(bbox, (list, tuple))
            or len(bbox) != 4
        ):
            raise ValueError(
                f"题目 {question.id} 的 ms_regions 第 {index} 项 page/bbox 不完整"
            )
        with pymupdf.open(stream=data_cache[sha256], filetype="pdf") as pdf:
            if not 1 <= page_no <= len(pdf):
                raise ValueError(
                    f"题目 {question.id} 的 ms_regions 第 {index} 项页码 {page_no} "
                    f"超出文档范围（共 {len(pdf)} 页）"
                )
            page = pdf[page_no - 1]
            # 存储坐标是未旋转的 PDF 用户空间；渲染要用页面的旋转后坐标。
            clip = pymupdf.Rect(bbox) * page.rotation_matrix
            pixmap = page.get_pixmap(
                matrix=pymupdf.Matrix(1.5, 1.5), clip=clip, alpha=False
            )
            png = pixmap.tobytes("png")
            del pixmap
        crops.append({"page": page_no, "bbox": tuple(float(v) for v in bbox), "png": png})
    return crops


def question_crops(
    session: Session, question_id: int, *, role: str = "qp"
) -> list[dict[str, Any]]:
    """把一道题在原始 PDF 上的裁剪区渲染成 PNG（页从 1 开始，bbox 为 PDF 用户空间）。

    - role="qp"：读文档当前版本的原始 PDF，用左栏编号算法重新定位后裁剪；
    - role="ms"：按 `question.attrs["ms_regions"]` 存好的 sha256/page/bbox
      直接渲染——评分标准版式与题目不同，存储区是唯一可信来源。

    缺题、缺版本、缺内容对象或定位失败都抛 `ValueError`，不返回空列表。
    """
    if role not in {"qp", "ms"}:
        raise ValueError(f"role 只能是 'qp' 或 'ms'（当前为 {role!r}）")
    question = session.get(Question, question_id)
    if question is None:
        raise ValueError(f"题目 {question_id} 不存在")
    if role == "ms":
        return _ms_crops(session, question)

    paper = session.get(Paper, question.paper_id)
    document = session.get(Document, paper.document_id) if paper else None
    if document is None:
        raise ValueError(f"题目 {question_id} 没有对应的试卷文档，无法裁剪")
    data = _current_revision_pdf(session, document)

    from ..paperqa.errors import LocationError
    from ..paperqa.locator import crop_question

    try:
        crops = crop_question(data, question.number_path, "qp")
    except LocationError as exc:
        raise ValueError(
            f"题目 {question_id}（{question.number_path}）在 PDF 中定位失败：{exc}"
        ) from exc
    return [{"page": crop.page, "bbox": crop.bbox, "png": crop.png} for crop in crops]


def get_paper_tree(session: Session, paper_id: int) -> Optional[dict[str, Any]]:
    """整张试卷的题目树（含层级、分值、资产数量）。"""
    paper = session.get(Paper, paper_id)
    if paper is None:
        return None
    doc = session.get(Document, paper.document_id)
    rows = list(
        session.scalars(
            select(Question)
            .where(Question.paper_id == paper_id)
            .order_by(Question.display_order)
        ).all()
    )
    ids = [q.id for q in rows] or [0]
    asset_counts = dict(
        session.execute(
            select(QuestionAsset.question_id, func.count(QuestionAsset.id))
            .where(QuestionAsset.question_id.in_(ids))
            .group_by(QuestionAsset.question_id)
        ).all()
    )
    nodes = {
        q.id: {
            "id": q.id,
            "number_path": q.number_path,
            "label": q.number_label,
            "depth": q.depth,
            "kind": q.kind,
            "marks": q.marks,
            "page_from": q.page_from,
            "page_to": q.page_to,
            "asset_count": asset_counts.get(q.id, 0),
            "children": [],
        }
        for q in rows
    }
    roots: list[dict[str, Any]] = []
    for q in rows:
        node = nodes[q.id]
        parent = nodes.get(q.parent_id) if q.parent_id else None
        if parent is None:
            roots.append(node)
        else:
            parent["children"].append(node)
    return {
        "paper": {
            "id": paper.id,
            "paper_no": paper.paper_no,
            "marks_total": paper.marks_total,
            "question_count": paper.question_count,
            "duration_minutes": paper.duration_minutes,
            "page_count": paper.page_count,
            "document_id": paper.document_id,
            "paper_code": doc.paper_code if doc else None,
            "year": doc.year if doc else None,
            "doc_type": doc.doc_type if doc else None,
        },
        "roots": roots,
    }


# --------------------------------------------------------------------------
# 随机抽题 / 自动组题基础能力
# --------------------------------------------------------------------------


@dataclass
class PaperComposition:
    """组卷结果：选中的题目与分值合计。"""

    questions: list[dict[str, Any]] = field(default_factory=list)
    marks_total: int = 0
    requested_marks: Optional[int] = None


def sample_questions(
    session: Session,
    f: QuestionFilter,
    *,
    count: Optional[int] = None,
    marks_target: Optional[int] = None,
    seed: Optional[int] = None,
) -> PaperComposition:
    """按条件随机抽题。

    两种模式：
    - count：抽固定题数；
    - marks_target：累加分值直到达到或超过目标分，返回实际总分。
    """
    pool = [q for q in _question_rows(session, _question_stmt(f, paginate=False))
            if q["marks"]]
    if not pool:
        return PaperComposition(requested_marks=marks_target)

    rng = random.Random(seed)
    rng.shuffle(pool)

    picked: list[dict[str, Any]] = []
    total = 0
    for q in pool:
        if count is not None and len(picked) >= count:
            break
        if marks_target is not None and total >= marks_target:
            break
        picked.append(q)
        total += q["marks"] or 0
    return PaperComposition(questions=picked, marks_total=total, requested_marks=marks_target)


# --------------------------------------------------------------------------
# 运维视图：同步状态与待检查队列
# --------------------------------------------------------------------------


def sync_status(session: Session) -> list[dict[str, Any]]:
    """各考试局的数据同步与解析状态概览（需求"后台监控"）。

    需要能看出：最后同步时间、已发现资源数、新增/更新数、解析成功/失败数、
    待检查数量与主要错误原因 —— 页面结构变化导致采集失效时能快速发现。
    """
    out: list[dict[str, Any]] = []
    for board in session.scalars(select(Board).order_by(Board.key)).all():
        doc_ids = select(Document.id).where(Document.board_id == board.id)
        rev_ids = select(DocumentRevision.id).where(
            DocumentRevision.document_id.in_(doc_ids)
        )
        last_run = session.scalar(
            select(SyncRun)
            .where(SyncRun.board_id == board.id)
            .order_by(SyncRun.started_at.desc())
            .limit(1)
        )
        counts = dict(
            session.execute(
                select(DocumentRevision.parse_status, func.count(DocumentRevision.id))
                .where(DocumentRevision.id.in_(rev_ids))
                .group_by(DocumentRevision.parse_status)
            ).all()
        )
        # 待检查项与校验发现必须按考试局分别统计。
        # 之前这两个数没按 board 过滤，导致每个考试局显示同一份全局数字——
        # 监控视图因此完全看不出"是哪个考试局出了问题"。
        # 它们通过 parse_run -> document_revision -> document 归属到考试局；
        # 没有 parse_run 的（如人工修正冲突）按 subject_type/subject_id 兜底。
        open_reviews = session.scalar(
            select(func.count(ReviewTask.id)).where(
                ReviewTask.status == "open",
                ReviewTask.parse_run_id.in_(
                    select(ParseRun.id).where(
                        ParseRun.document_revision_id.in_(rev_ids)
                    )
                ),
            )
        ) or 0
        open_errors = session.scalar(
            select(func.count(ValidationFinding.id)).where(
                ValidationFinding.severity.in_(["error", "critical"]),
                ValidationFinding.status == "open",
                ValidationFinding.parse_run_id.in_(
                    select(ParseRun.id).where(
                        ParseRun.document_revision_id.in_(rev_ids)
                    )
                ),
            )
        ) or 0
        out.append(
            {
                "board": board.key,
                "name": board.name,
                "accessibility": board.accessibility,
                "documents": session.scalar(
                    select(func.count(Document.id)).where(Document.board_id == board.id)
                )
                or 0,
                "papers": session.scalar(
                    select(func.count(Paper.id)).where(Paper.document_id.in_(doc_ids))
                )
                or 0,
                "questions": session.scalar(
                    select(func.count(Question.id))
                    .join(Paper, Paper.id == Question.paper_id)
                    .where(Paper.document_id.in_(doc_ids))
                )
                or 0,
                "parsed": counts.get("parsed", 0),
                "pending": counts.get("pending", 0),
                "failed": counts.get("failed", 0),
                "open_review_tasks": open_reviews,
                "open_errors": open_errors,
                "last_sync_at": last_run.finished_at.isoformat()
                if last_run and last_run.finished_at
                else None,
                "last_sync_status": last_run.status if last_run else None,
                "last_sync_stats": last_run.stats if last_run else None,
            }
        )
    return out


def review_queue(session: Session, *, limit: int = 100) -> list[dict[str, Any]]:
    """待人工检查队列（需求"低置信度或存在冲突的数据应进入待检查状态"）。"""
    rows = session.scalars(
        select(ReviewTask)
        .where(ReviewTask.status == "open")
        .order_by(ReviewTask.priority, ReviewTask.id)
        .limit(limit)
    ).all()
    return [
        {
            "id": r.id,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "reason": r.reason,
            "priority": r.priority,
            "status": r.status,
        }
        for r in rows
    ]


def board_health(session: Session) -> list[dict[str, Any]]:
    """采集健康度：每个考试局的资源候选状态分布，用于发现"静默失效"。"""
    from ..core.models import ResourceCandidate

    out: list[dict[str, Any]] = []
    for board in session.scalars(select(Board).order_by(Board.key)).all():
        by_status = dict(
            session.execute(
                select(ResourceCandidate.status, func.count(ResourceCandidate.id))
                .where(ResourceCandidate.board_id == board.id)
                .group_by(ResourceCandidate.status)
            ).all()
        )
        out.append({"board": board.key, "candidates": by_status})
    return out
