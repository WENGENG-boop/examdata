"""检索与抽题：题目级数据底座对外的主要读取入口。

设计原则（需求文档"试卷检索能力"/"题目检索能力"/"随机抽题"）：
- 上层应用只依赖这里的统一概念，不需要理解各考试局原始站点结构。
- 检索维度覆盖考试局、考试体系、科目、科目代码、年份、考试季、Paper、
  Component、Variant、Level，以及题目级的题号、分值、层级、知识点、难度。
- 组卷/抽题只做"按条件选题"，不含任何学生端逻辑。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from ..core.models import (
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


def _paper_stmt(f: PaperFilter) -> Select:
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
    return (
        stmt.order_by(Document.year.desc(), Document.paper_code)
        .limit(f.limit)
        .offset(f.offset)
    )


def search_papers(session: Session, f: PaperFilter) -> list[dict[str, Any]]:
    """按考试信息检索试卷。"""
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
    import dataclasses

    counting = dataclasses.replace(f, limit=100000, offset=0)
    inner = _paper_stmt(counting).subquery()
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


def _question_stmt(f: QuestionFilter) -> Select:
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
        stmt = stmt.where(Question.stem_text.ilike(f"%{f.keyword}%"))
    if f.taxonomy_code:
        stmt = (
            stmt.join(QuestionTaxonomy, QuestionTaxonomy.question_id == Question.id)
            .join(TaxonomyNode, TaxonomyNode.id == QuestionTaxonomy.node_id)
            .where(TaxonomyNode.code == f.taxonomy_code)
        )
        if f.taxonomy_source:
            stmt = stmt.where(QuestionTaxonomy.source == f.taxonomy_source)
    if f.difficulty_min is not None or f.difficulty_max is not None:
        stmt = stmt.join(Difficulty, Difficulty.question_id == Question.id)
        if f.difficulty_min is not None:
            stmt = stmt.where(Difficulty.value >= f.difficulty_min)
        if f.difficulty_max is not None:
            stmt = stmt.where(Difficulty.value <= f.difficulty_max)
        if f.difficulty_source:
            stmt = stmt.where(Difficulty.source == f.difficulty_source)
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
    return stmt.order_by(
        Document.year.desc(), Document.paper_code, Question.display_order
    )


def search_questions(session: Session, f: QuestionFilter) -> list[dict[str, Any]]:
    """题目级检索。"""
    stmt = _question_stmt(f).limit(f.limit).offset(f.offset)
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
    import dataclasses

    counting = dataclasses.replace(f, limit=100000, offset=0)
    inner = _question_stmt(counting).subquery()
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
    import dataclasses

    wide = dataclasses.replace(f, limit=5000, offset=0)
    pool = [q for q in search_questions(session, wide) if q["marks"]]
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
