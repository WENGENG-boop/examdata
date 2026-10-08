"""溯源边。

规格要求能追踪"某一份试卷、某一道题、某一个答案、某一份评分标准或某一个
图片资源最初来自哪个考试局、哪个官方资源以及何时被系统发现和更新"。

设计取舍：**溯源是可推导的，因此做成投影而不是另写一遍**。
题目 -> parse_run -> document_revision -> (source_url, artifact, document)
这条链在解析时就已经完整落库；如果在这里再手写一遍来源，
只会多出一份可能与实际数据不一致的副本。

因此本模块从既有 FK 关系重建 provenance_edge：
- 幂等：同 (subject_type, subject_id, source_kind, source_ref) 只保留一条
- 可重建：任何时候删空这张表重跑，结果完全一致
- 只读既有事实，不引入新判断
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..core.models import (
    Artifact,
    Asset,
    Board,
    Document,
    DocumentRevision,
    MarkScheme,
    MarkSchemeEntry,
    OfficialAnswer,
    Paper,
    ParseRun,
    ProvenanceEdge,
    Question,
    QuestionAsset,
    Subject,
)

SOURCE_KIND = "official_resource"


def rebuild(session: Session, *, board: Optional[str] = None) -> dict[str, int]:
    """从既有 FK 关系重建溯源边。幂等。

    board 非空时只重建该考试局名下的主体：先删它们的旧边，再只投影它们，
    其它考试局的数据不受影响。
    """
    stats: dict[str, int] = {}

    board_id: Optional[int] = None
    if board is None:
        # 先清空，保证是纯投影
        session.execute(delete(ProvenanceEdge))
    else:
        board_id = session.scalar(select(Board.id).where(Board.key == board))
        if board_id is None:
            raise ValueError(f"考试局 {board!r} 不存在")
        _delete_board_edges(session, board_id)

    stats["questions"] = _link_questions(session, board_id)
    stats["mark_scheme_entries"] = _link_mark_scheme_entries(session, board_id)
    stats["assets"] = _link_assets(session, board_id)
    stats["official_answers"] = _link_official_answers(session, board_id)
    stats["papers"] = _link_papers(session, board_id)
    session.flush()
    return stats


def _board_question_ids(board_id: int):
    """该考试局全部题目的 id 子查询（question -> paper -> document -> board）。"""
    return (
        select(Question.id)
        .join(Paper, Paper.id == Question.paper_id)
        .join(Document, Document.id == Paper.document_id)
        .where(Document.board_id == board_id)
    )


def _delete_board_edges(session: Session, board_id: int) -> None:
    """只删该考试局主体的旧边，其它考试局的边不动。

    资产可能被多个考试局共用，无法只看 subject_id 判断归属，改按边上的
    attrs.question_id 过滤（重建是低频维护操作，Python 侧筛选可以接受）。
    """
    question_ids = _board_question_ids(board_id)
    ms_ids = (
        select(MarkSchemeEntry.id)
        .join(MarkScheme, MarkScheme.id == MarkSchemeEntry.mark_scheme_id)
        .join(Document, Document.id == MarkScheme.document_id)
        .where(Document.board_id == board_id)
    )
    answer_ids = (
        select(OfficialAnswer.id)
        .join(Question, Question.id == OfficialAnswer.question_id)
        .join(Paper, Paper.id == Question.paper_id)
        .join(Document, Document.id == Paper.document_id)
        .where(Document.board_id == board_id)
    )
    paper_ids = (
        select(Paper.id)
        .join(Document, Document.id == Paper.document_id)
        .where(Document.board_id == board_id)
    )
    for stype, ids in (
        ("question", question_ids),
        ("mark_scheme_entry", ms_ids),
        ("official_answer", answer_ids),
        ("paper", paper_ids),
    ):
        session.execute(
            delete(ProvenanceEdge).where(
                ProvenanceEdge.subject_type == stype,
                ProvenanceEdge.subject_id.in_(ids),
            )
        )

    board_qids = set(session.scalars(question_ids).all())
    if not board_qids:
        return
    stale_ids = [
        edge_id
        for edge_id, attrs in session.execute(
            select(ProvenanceEdge.id, ProvenanceEdge.attrs).where(
                ProvenanceEdge.subject_type == "asset"
            )
        ).all()
        if (attrs or {}).get("question_id") in board_qids
    ]
    if stale_ids:
        session.execute(delete(ProvenanceEdge).where(ProvenanceEdge.id.in_(stale_ids)))


def _revision_source(
    session: Session, parse_run_id: Optional[int]
) -> Optional[tuple[int, str, Optional[str], int]]:
    """parse_run -> (document_id, source_url, artifact_sha, revision_id)。"""
    if not parse_run_id:
        return None
    row = session.execute(
        select(
            DocumentRevision.document_id,
            DocumentRevision.source_url,
            Artifact.sha256,
            DocumentRevision.id,
        )
        .join(ParseRun, ParseRun.document_revision_id == DocumentRevision.id)
        .join(Artifact, Artifact.id == DocumentRevision.artifact_id)
        .where(ParseRun.id == parse_run_id)
    ).first()
    return row


def _add(
    session: Session,
    subject_type: str,
    subject_id: int,
    *,
    source_ref: Optional[str],
    source_url: Optional[str],
    run_id: Optional[int],
    attrs: dict[str, Any],
) -> int:
    session.add(
        ProvenanceEdge(
            subject_type=subject_type,
            subject_id=subject_id,
            source_kind=SOURCE_KIND,
            source_ref=source_ref,
            source_url=source_url,
            run_id=run_id,
            attrs=attrs,
        )
    )
    return 1


def _link_questions(session: Session, board_id: Optional[int] = None) -> int:
    n = 0
    stmt = select(
        Question.id, Question.parse_run_id, Question.number_path, Question.paper_id
    )
    if board_id is not None:
        stmt = (
            stmt.join(Paper, Paper.id == Question.paper_id)
            .join(Document, Document.id == Paper.document_id)
            .where(Document.board_id == board_id)
        )
    rows = session.execute(stmt).all()
    cache: dict[int, Any] = {}
    for qid, run_id, number_path, paper_id in rows:
        if run_id not in cache:
            cache[run_id] = _revision_source(session, run_id)
        src = cache[run_id]
        if src is None:
            continue
        doc_id, url, sha, rev_id = src
        n += _add(
            session,
            "question",
            qid,
            source_ref=f"document:{doc_id}#{number_path}",
            source_url=url,
            run_id=run_id,
            attrs={
                "document_id": doc_id,
                "revision_id": rev_id,
                "artifact_sha256": sha,
                "number_path": number_path,
                "paper_id": paper_id,
            },
        )
    return n


def _link_mark_scheme_entries(session: Session, board_id: Optional[int] = None) -> int:
    n = 0
    stmt = select(
        MarkSchemeEntry.id,
        MarkSchemeEntry.number_path,
        MarkScheme.document_id,
        MarkSchemeEntry.mark_scheme_id,
    ).join(MarkScheme, MarkScheme.id == MarkSchemeEntry.mark_scheme_id)
    if board_id is not None:
        stmt = stmt.join(Document, Document.id == MarkScheme.document_id).where(
            Document.board_id == board_id
        )
    rows = session.execute(stmt).all()
    for eid, number_path, doc_id, ms_id in rows:
        rev = session.scalar(
            select(DocumentRevision)
            .where(DocumentRevision.document_id == doc_id)
            .order_by(DocumentRevision.revision_no.desc())
            .limit(1)
        )
        n += _add(
            session,
            "mark_scheme_entry",
            eid,
            source_ref=f"document:{doc_id}#{number_path}",
            source_url=rev.source_url if rev else None,
            run_id=None,
            attrs={
                "document_id": doc_id,
                "revision_id": rev.id if rev else None,
                "mark_scheme_id": ms_id,
                "number_path": number_path,
            },
        )
    return n


def _link_assets(session: Session, board_id: Optional[int] = None) -> int:
    n = 0
    stmt = select(
        Asset.id,
        Asset.sha256,
        Asset.storage_key,
        QuestionAsset.question_id,
        QuestionAsset.page,
        QuestionAsset.role,
    ).join(QuestionAsset, QuestionAsset.asset_id == Asset.id)
    if board_id is not None:
        stmt = (
            stmt.join(Question, Question.id == QuestionAsset.question_id)
            .join(Paper, Paper.id == Question.paper_id)
            .join(Document, Document.id == Paper.document_id)
            .where(Document.board_id == board_id)
        )
    rows = session.execute(stmt).all()
    seen: set[tuple[int, int]] = set()
    for aid, sha, storage_key, qid, page, role in rows:
        if (aid, qid) in seen:
            continue
        seen.add((aid, qid))
        run_id = session.scalar(select(Question.parse_run_id).where(Question.id == qid))
        src = _revision_source(session, run_id)
        n += _add(
            session,
            "asset",
            aid,
            source_ref=f"sha256:{sha}",
            source_url=src[1] if src else None,
            run_id=run_id,
            attrs={
                "storage_key": storage_key,
                "question_id": qid,
                "page": page,
                "role": role,
                "document_id": src[0] if src else None,
            },
        )
    return n


def _link_official_answers(session: Session, board_id: Optional[int] = None) -> int:
    n = 0
    stmt = select(
        OfficialAnswer.id,
        OfficialAnswer.question_id,
        OfficialAnswer.source,
        OfficialAnswer.source_document_id,
    )
    if board_id is not None:
        stmt = (
            stmt.join(Question, Question.id == OfficialAnswer.question_id)
            .join(Paper, Paper.id == Question.paper_id)
            .join(Document, Document.id == Paper.document_id)
            .where(Document.board_id == board_id)
        )
    rows = session.execute(stmt).all()
    for aid, qid, source, src_doc_id in rows:
        doc_id = src_doc_id
        if doc_id is None:
            run_id = session.scalar(select(Question.parse_run_id).where(Question.id == qid))
            src = _revision_source(session, run_id)
            doc_id = src[0] if src else None
        rev = None
        if doc_id is not None:
            rev = session.scalar(
                select(DocumentRevision)
                .where(DocumentRevision.document_id == doc_id)
                .order_by(DocumentRevision.revision_no.desc())
                .limit(1)
            )
        n += _add(
            session,
            "official_answer",
            aid,
            source_ref=f"document:{doc_id}" if doc_id else None,
            source_url=rev.source_url if rev else None,
            run_id=None,
            attrs={
                "question_id": qid,
                "answer_source": source,
                "document_id": doc_id,
                "revision_id": rev.id if rev else None,
                "is_official": True,
            },
        )
    return n


def _link_papers(session: Session, board_id: Optional[int] = None) -> int:
    n = 0
    stmt = select(Paper.id, Paper.document_id, Paper.parse_run_id, Paper.paper_no)
    if board_id is not None:
        stmt = stmt.join(Document, Document.id == Paper.document_id).where(
            Document.board_id == board_id
        )
    rows = session.execute(stmt).all()
    for pid, doc_id, run_id, paper_no in rows:
        rev = session.scalar(
            select(DocumentRevision)
            .where(DocumentRevision.document_id == doc_id)
            .order_by(DocumentRevision.revision_no.desc())
            .limit(1)
        )
        n += _add(
            session,
            "paper",
            pid,
            source_ref=f"document:{doc_id}",
            source_url=rev.source_url if rev else None,
            run_id=run_id,
            attrs={
                "document_id": doc_id,
                "revision_id": rev.id if rev else None,
                "paper_no": paper_no,
            },
        )
    return n


def trace(session: Session, subject_type: str, subject_id: int) -> list[dict[str, Any]]:
    """查询某个主体的全部来源（需求：追踪某个题目/答案/图片来自哪里）。"""
    rows = session.scalars(
        select(ProvenanceEdge)
        .where(
            ProvenanceEdge.subject_type == subject_type,
            ProvenanceEdge.subject_id == subject_id,
        )
        .order_by(ProvenanceEdge.id)
    ).all()
    return [
        {
            "source_kind": r.source_kind,
            "source_ref": r.source_ref,
            "source_url": r.source_url,
            "run_id": r.run_id,
            "observed_at": r.observed_at.isoformat() if r.observed_at else None,
            "attrs": r.attrs,
        }
        for r in rows
    ]


def coverage(session: Session) -> dict[str, Any]:
    """溯源覆盖率：每个主体类型里有多少条记录有来源。

    按**去重主体**计数，不按边数：一个资产可能被多道题引用，
    每引用一次就写一条边，用边数会算出超过 100% 的覆盖率。
    """
    out: dict[str, Any] = {}
    for stype, model in (
        ("question", Question),
        ("mark_scheme_entry", MarkSchemeEntry),
        ("asset", Asset),
        ("official_answer", OfficialAnswer),
        ("paper", Paper),
    ):
        total = session.scalar(select(func.count(model.id))) or 0
        linked = (
            session.scalar(
                select(func.count(func.distinct(ProvenanceEdge.subject_id))).where(
                    ProvenanceEdge.subject_type == stype
                )
            )
            or 0
        )
        edges = (
            session.scalar(
                select(func.count(ProvenanceEdge.id)).where(
                    ProvenanceEdge.subject_type == stype
                )
            )
            or 0
        )
        out[stype] = {
            "total": total,
            "linked": linked,
            "edges": edges,
            "ratio": round(min(1.0, linked / total), 4) if total else 0.0,
        }
    return out
