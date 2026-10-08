"""重新解析：用新算法重跑历史资源，并与旧结果对比。

规格三条要求：
1. "系统需要支持使用新的解析能力重新处理已经保存的历史资源。"
2. "重新解析不应该要求重新从官方网站下载全部历史文件。"
3. "同时应能够比较新旧解析结果，避免升级算法后产生新的数据错误。"

第 2 条天然满足：解析只读本地 artifact（内容寻址存储），不触碰网络。
本模块负责第 1 和第 3 条。

**对比的做法**：重新解析前先对目标文档做一次"解析快照"（题数、分值、
层级、资产、评分条目等可比的量），重解析后再取一次，逐项 diff。
不比较具体的题号字符串——算法升级时题号本来就会变，
把"变了"当错误报出来只会淹没真正的回归（题数骤降、分值对不上）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime as _dt
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.config import Settings
from ..core.models import (
    Artifact,
    Document,
    DocumentRevision,
    MarkScheme,
    MarkSchemeEntry,
    Paper,
    Question,
    QuestionAsset,
)


def _target_models() -> dict[str, Any]:
    """自然键映射用到的模型。延迟导入，避免模块级循环。"""
    return {"question": Question, "mark_scheme_entry": MarkSchemeEntry, "paper": Paper}


@dataclass
class DocumentSnapshot:
    """一份文档的解析结果概览，用于新旧对比。"""

    document_id: int
    doc_type: str
    paper_id: Optional[int] = None
    questions: int = 0
    roots: int = 0
    max_depth: int = 0
    marks_total: Optional[int] = None
    marks_sum: int = 0
    assets: int = 0
    mark_scheme_entries: int = 0
    entries_linked: int = 0
    duplicate_paths: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "doc_type": self.doc_type,
            "paper_id": self.paper_id,
            "questions": self.questions,
            "roots": self.roots,
            "max_depth": self.max_depth,
            "marks_total": self.marks_total,
            "marks_sum": self.marks_sum,
            "assets": self.assets,
            "mark_scheme_entries": self.mark_scheme_entries,
            "entries_linked": self.entries_linked,
            "duplicate_paths": self.duplicate_paths,
        }


def snapshot(session: Session, document_id: int) -> DocumentSnapshot:
    doc = session.get(Document, document_id)
    if doc is None:
        raise ValueError(f"document {document_id} 不存在")
    snap = DocumentSnapshot(document_id=document_id, doc_type=doc.doc_type)

    paper = session.scalar(select(Paper).where(Paper.document_id == document_id))
    if paper is not None:
        snap.paper_id = paper.id
        snap.marks_total = paper.marks_total
        rows = session.execute(
            select(Question.number_path, Question.marks, Question.depth, Question.parent_id)
            .where(Question.paper_id == paper.id)
        ).all()
        snap.questions = len(rows)
        snap.roots = sum(1 for r in rows if r[3] is None)
        snap.max_depth = max((r[2] or 0 for r in rows), default=0)
        snap.marks_sum = sum(r[1] or 0 for r in rows if r[3] is None)
        paths = [r[0] for r in rows]
        snap.duplicate_paths = len(paths) - len(set(paths))
        qids = select(Question.id).where(Question.paper_id == paper.id)
        snap.assets = (
            session.scalar(
                select(func.count(QuestionAsset.id)).where(QuestionAsset.question_id.in_(qids))
            )
            or 0
        )

    ms = session.scalar(select(MarkScheme).where(MarkScheme.document_id == document_id))
    if ms is not None:
        snap.mark_scheme_entries = (
            session.scalar(
                select(func.count(MarkSchemeEntry.id)).where(
                    MarkSchemeEntry.mark_scheme_id == ms.id
                )
            )
            or 0
        )
        snap.entries_linked = (
            session.scalar(
                select(func.count(MarkSchemeEntry.id)).where(
                    MarkSchemeEntry.mark_scheme_id == ms.id,
                    MarkSchemeEntry.question_id.is_not(None),
                )
            )
            or 0
        )
    return snap


# 数值型指标：变化超过这个比例才算"显著"，否则视为算法噪声
_REGRESSION_FIELDS = (
    ("questions", 0.05),
    ("roots", 0.05),
    ("marks_sum", 0.05),
    ("assets", 0.10),
    ("mark_scheme_entries", 0.05),
    ("entries_linked", 0.05),
)


@dataclass
class SnapshotDiff:
    document_id: int
    before: dict[str, Any]
    after: dict[str, Any]
    changes: list[dict[str, Any]] = field(default_factory=list)
    regressions: list[str] = field(default_factory=list)

    @property
    def is_regression(self) -> bool:
        return bool(self.regressions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "before": self.before,
            "after": self.after,
            "changes": self.changes,
            "regressions": self.regressions,
            "is_regression": self.is_regression,
        }


def diff(before: DocumentSnapshot, after: DocumentSnapshot) -> SnapshotDiff:
    """逐项对比。只把"变差"标为回归，改善和中性变化都只记录。"""
    b, a = before.to_dict(), after.to_dict()
    changes: list[dict[str, Any]] = []
    regressions: list[str] = []

    for key in b:
        if b[key] == a[key]:
            continue
        entry = {"field": key, "before": b[key], "after": a[key]}
        if isinstance(b[key], (int, float)) and isinstance(a[key], (int, float)):
            base = abs(b[key]) or 1
            entry["delta"] = round(a[key] - b[key], 4)
            entry["ratio"] = round((a[key] - b[key]) / base, 4)
        changes.append(entry)

    # 结构性回归：这些一旦出现就是算法退化，不是"换了种解析方式"
    if a["duplicate_paths"] > b["duplicate_paths"]:
        regressions.append(
            f"重复题号路径从 {b['duplicate_paths']} 增加到 {a['duplicate_paths']}"
        )
    if b["entries_linked"] > 0 and a["entries_linked"] == 0:
        regressions.append("评分条目关联数归零（Mark Scheme 匹配失效）")
    for field_name, tolerance in _REGRESSION_FIELDS:
        bv, av = b[field_name], a[field_name]
        if not isinstance(bv, (int, float)) or not isinstance(av, (int, float)):
            continue
        if bv > 0 and av < bv * (1 - tolerance):
            regressions.append(
                f"{field_name} 显著下降：{bv} -> {av}（超过 {tolerance:.0%}）"
            )
    if a["questions"] == 0 and b["questions"] > 0:
        regressions.append("题目数归零")
    return SnapshotDiff(
        document_id=before.document_id,
        before=b,
        after=a,
        changes=changes,
        regressions=regressions,
    )


class ReparseOverrideConflict(RuntimeError):
    def __init__(self, override_id):
        self.override_id = override_id
        super().__init__("人工覆盖目标消失或歧义，旧结果已保留")


def reparse_documents(
    session: Session,
    *,
    document_ids: Optional[list[int]] = None,
    limit: Optional[int] = None,
    keep_history: bool = True,
    settings: Optional[Settings] = None,
) -> dict[str, Any]:
    """从本地 artifact 重建目标文档的当前版本，提交由调用方负责。

    目标和本地文件先校验，解析失败时保存点恢复旧派生数据。
    keep_history=False 删除目标文档的旧 ParseRun，但保留复核记录。
    """
    from ..parsing.pipeline import ParsePipeline, ParseStats

    if limit is not None and limit <= 0:
        raise ValueError("limit 必须大于 0")
    if document_ids is not None:
        if any(not isinstance(d, int) or isinstance(d, bool) or d <= 0 for d in document_ids):
            raise ValueError("document_ids 必须是正整数列表")
        targets = list(dict.fromkeys(document_ids))
        docs = list(session.scalars(select(Document).where(Document.id.in_(targets)).order_by(Document.id)))
        missing = set(targets) - {d.id for d in docs}
        if missing:
            raise ValueError(f"document 不存在: {sorted(missing)}")
        if limit is not None:
            docs = docs[:limit]
    else:
        stmt = select(Document).order_by(Document.id)
        if limit is not None:
            stmt = stmt.limit(limit)
        docs = list(session.scalars(stmt))

    empty = {
        "documents": 0, "regressed": 0, "parse_stats": ParseStats().to_dict(),
        "derived": {}, "relinked": {"papers": 0, "entries": 0, "linked": 0},
        "diffs": [], "overrides": {"remapped": 0, "conflicted": 0, "orphaned": 0, "applied": 0},
    }
    if not docs:
        return empty

    started_at = _dt.datetime.now(_dt.timezone.utc)
    pipe = ParsePipeline(session, settings=settings)
    revisions: list[DocumentRevision] = []
    for doc in docs:
        revision = (
            session.get(DocumentRevision, doc.current_revision_id)
            if doc.current_revision_id is not None else session.scalar(
                select(DocumentRevision).where(DocumentRevision.document_id == doc.id)
                .order_by(DocumentRevision.revision_no.desc(), DocumentRevision.id.desc()).limit(1)
            )
        )
        if revision is None or revision.document_id != doc.id:
            raise ValueError(f"document {doc.id} 无有效当前 revision")
        artifact = session.get(Artifact, revision.artifact_id)
        if artifact is None or not pipe._artifact_path(artifact.storage_key).is_file():
            raise ValueError(f"document {doc.id} 的本地 artifact 不存在")
        revisions.append(revision)

    targets = [d.id for d in docs]
    before = {d.id: snapshot(session, d.id) for d in docs}
    natural_keys = _capture_natural_keys(session, targets)
    protected = _capture_protected(session, targets, natural_keys)
    source_answers, expected_links = _capture_source_migration(session, targets)
    preserved_similarity = _capture_preserved_similarity(session, natural_keys["question"])
    linked_entries = list(session.scalars(
        select(MarkSchemeEntry.id).join(Question, Question.id == MarkSchemeEntry.question_id)
        .join(Paper, Paper.id == Question.paper_id).where(Paper.document_id.in_(targets))
    ))
    try:
        with session.begin_nested():
            # Prevent recycled integer IDs from applying an old override to a different row.
            from ..core.models import FieldOverride
            suspended = []
            for ov in session.scalars(select(FieldOverride)):
                if ov.target_id in natural_keys.get(ov.target_type, {}):
                    suspended.append((ov, ov.target_id, ov.active))
                    ov.active = False
                    ov.target_id = -ov.id
            session.flush()
            _purge_derived(session, targets, keep_history=keep_history)
            for revision in revisions:
                revision.parse_status = "pending"
                revision.parse_error = None
            session.flush()
            stats = pipe.run(document_ids=targets, revision_ids=[r.id for r in revisions], commit=False)
            if stats.failed or any(r.parse_status != "parsed" for r in revisions):
                raise RuntimeError("重新解析失败，旧结果已保留: " + "; ".join(stats.errors))

            new_entries = list(session.scalars(
                select(MarkSchemeEntry.id).join(MarkScheme, MarkScheme.id == MarkSchemeEntry.mark_scheme_id)
                .where(MarkScheme.document_id.in_(targets), MarkSchemeEntry.question_id.is_(None))
            ))
            relinked = _relink_mark_scheme_entries(session, linked_entries + new_entries, pipe=pipe)
            if any(session.get(MarkSchemeEntry, entry_id).question_id is None for entry_id in linked_entries
                   if session.get(MarkSchemeEntry, entry_id) is not None):
                raise RuntimeError("原评分关联无法安全恢复，旧结果已保留")
            _restore_protected(session, protected)
            _restore_preserved_similarity(session, preserved_similarity)
            for ov, old_id, active in suspended:
                new_id = _lookup_natural_key(session, ov.target_type, natural_keys[ov.target_type][old_id])
                if new_id is None:
                    raise ReparseOverrideConflict(ov.id)
                ov.target_id = new_id
                ov.active = active
            session.flush()
            remap = _remap_overrides(session, overrides=[ov for ov, _, _ in suspended])
            remap["remapped"] = sum(ov.target_id != old_id for ov, old_id, _ in suspended)
            migrated = _finish_source_migration(session, targets, source_answers, expected_links)
            derived = _rebuild_derived(session, targets, question_ids=migrated["question_ids"])
            if "error" in derived:
                raise RuntimeError("派生重建失败，旧结果已保留: " + derived["error"])
            results = [diff(before[d.id], snapshot(session, d.id)).to_dict() for d in docs]
            session.flush()
    except ReparseOverrideConflict as exc:
        from ..core.models import FieldOverride, ReviewTask
        ov = session.get(FieldOverride, exc.override_id)
        ov.conflict_detected = True
        ov.conflict_detail = str(exc)
        session.add(ReviewTask(target_type=ov.target_type, target_id=ov.target_id,
                               reason="override_target_missing_after_reparse", priority=1, status="open"))
        _record_reparse_failure(session, revisions, pipe.settings.parser_version, str(exc), started_at)
        session.flush()
        return {**empty, "documents": len(docs), "aborted": True, "reason": str(exc),
                "parse_stats": {**ParseStats().to_dict(), "failed": 1, "errors": [str(exc)]},
                "overrides": {"remapped": 0, "conflicted": 1, "orphaned": 0, "applied": 0}}

    except Exception as exc:
        _record_reparse_failure(session, revisions, pipe.settings.parser_version, str(exc), started_at)
        session.flush()
        return {**empty, "documents": len(docs), "aborted": True, "reason": str(exc),
                "parse_stats": {**ParseStats().to_dict(), "failed": 1, "errors": [str(exc)]}}

    return {
        "documents": len(docs),
        "regressed": sum(r["is_regression"] for r in results),
        "parse_stats": stats.to_dict(),
        "derived": derived,
        "relinked": relinked,
        "diffs": results,
        "overrides": remap,
        "source_migration": migrated,
    }


def _record_reparse_failure(session, revisions, parser_version, reason, started_at):
    from ..core.models import ParseRun
    for revision in revisions:
        session.add(ParseRun(document_revision_id=revision.id, parser_version=parser_version,
            status="failed", started_at=started_at, finished_at=_dt.datetime.now(_dt.timezone.utc),
            params={"operation": "reparse", "rolled_back": True, "error": reason}, stats={"failed": 1}))


def _relink_mark_scheme_entries(
    session: Session, entry_ids: list[int], *, pipe: Any
) -> dict[str, int]:
    """只恢复本轮断开的关联和本轮重建的评分条目。"""
    from ..markscheme.cambridge import link_entries_to_questions

    stats = {"papers": 0, "entries": 0, "linked": 0}
    ms_docs = list(session.scalars(
        select(MarkScheme).where(MarkScheme.id.in_(
            select(MarkSchemeEntry.mark_scheme_id).where(
                MarkSchemeEntry.id.in_(entry_ids), MarkSchemeEntry.question_id.is_(None)
            )
        ))
    ))
    for ms in ms_docs:
        doc = session.get(Document, ms.document_id)
        if doc is None:
            continue
        paper_doc = pipe._find_matching_paper(doc)
        if ms.matched_paper_document_id and (paper_doc is None or paper_doc.id != ms.matched_paper_document_id):
            continue
        if paper_doc is None:
            continue
        paper = session.scalar(select(Paper).where(Paper.document_id == paper_doc.id))
        if paper is None:
            continue
        questions = list(
            session.scalars(
                select(Question).where(Question.paper_id == paper.id).order_by(Question.id)
            ).all()
        )
        if not questions:
            continue
        pending = list(
            session.scalars(
                select(MarkSchemeEntry)
                .where(
                    MarkSchemeEntry.mark_scheme_id == ms.id,
                    MarkSchemeEntry.id.in_(entry_ids),
                    MarkSchemeEntry.question_id.is_(None),
                )
                .order_by(MarkSchemeEntry.id)
            ).all()
        )
        if not pending:
            continue
        # link_entries_to_questions 按索引返回，这里把 pending 当作 entries
        linked, _unmatched, _without = link_entries_to_questions(pending, questions)
        for idx, qid in linked:
            pending[idx].question_id = qid
            stats["linked"] += 1
        stats["papers"] += 1
        stats["entries"] += len(pending)
    session.flush()
    return stats


def _rebuild_derived(session: Session, document_ids: list[int], *, question_ids=None) -> dict[str, Any]:
    """仅重建目标题目，缺少安全目标接口的批量能力显式延期。"""
    from ..core.models import Difficulty, QuestionTaxonomy, Subject, TaxonomyNode
    from ..intelligence import classify_question, generate_for_question
    from ..intelligence.taxonomy import sync_taxonomy
    from ..intelligence.similarity import find_similar
    from ..intelligence.difficulty import MODEL_VERSION, SCALE, estimate

    out: dict[str, Any] = {
        "taxonomy": {"scanned": 0, "assigned": 0, "unassigned": 0},
        "difficulty": {"questions": 0, "written": 0},
        "explanation": {"scanned": 0, "generated": 0, "skipped_no_official": 0},
        "similarity": {},
    }
    try:
        with session.begin_nested():
            scope = Question.id.in_(question_ids or []) | Paper.document_id.in_(document_ids)
            rows = session.execute(
                select(Question, Subject.code, Document.board_id)
                .join(Paper, Paper.id == Question.paper_id)
                .join(Document, Document.id == Paper.document_id)
                .outerjoin(Subject, Subject.id == Document.subject_id)
                .where(scope).order_by(Question.id)
            ).all()
            sync_taxonomy(session, subject_codes={code for _, code, _ in rows if code})
            nodes = {(n.board_id, n.code): n for n in session.scalars(select(TaxonomyNode))}
            for question, code, board_id in rows:
                out["taxonomy"]["scanned"] += 1
                assigns = classify_question(question.stem_text or "", code or "")
                assigned = set(session.scalars(select(QuestionTaxonomy.node_id).where(
                    QuestionTaxonomy.question_id == question.id
                )))
                for assignment in assigns:
                    node = nodes.get((board_id, assignment.node_code))
                    if node is None:
                        continue
                    for node_id in (node.id, node.parent_id):
                        if node_id is None or node_id in assigned:
                            continue
                        assigned.add(node_id)
                        session.add(QuestionTaxonomy(
                            question_id=question.id, node_id=node_id, source="auto",
                            confidence=assignment.confidence if node_id == node.id else round(assignment.confidence * 0.9, 4),
                            assigned_by="keyword-v1", reviewed=False,
                        ))
                        out["taxonomy"]["assigned"] += 1
                if not assigned:
                    out["taxonomy"]["unassigned"] += 1
                session.flush()
                est = estimate(
                    marks=question.marks, stem_text=question.stem_text or "",
                    child_count=session.scalar(select(func.count(Question.id)).where(Question.parent_id == question.id)) or 0,
                    depth=question.depth or 0,
                    has_asset=session.scalar(select(QuestionAsset.id).where(QuestionAsset.question_id == question.id).limit(1)) is not None,
                    taxonomy_count=len(assigned),
                )
                for old in session.scalars(select(Difficulty).where(
                    Difficulty.question_id == question.id, Difficulty.source == "estimated"
                )):
                    session.delete(old)
                session.add(Difficulty(
                    question_id=question.id, source="estimated", value=est.value,
                    scale=SCALE, features=est.features, model_version=MODEL_VERSION,
                ))
                out["difficulty"]["questions"] += 1
                out["difficulty"]["written"] += 1
                out["explanation"]["scanned"] += 1
                if generate_for_question(session, question.id, replace=question.id in (question_ids or [])) is None:
                    out["explanation"]["skipped_no_official"] += 1
                else:
                    out["explanation"]["generated"] += 1
            session.flush()
            out["similarity"] = find_similar(session, question_ids=[q.id for q, _, _ in rows], replace=True)
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}", "status": "rolled_back"}
    return out


def _capture_natural_keys(session: Session, document_ids: list[int]) -> dict[str, dict[str, Any]]:
    """记录被重解析主体的自然键，用于事后把人工修正接回新行。

    自然键必须**完全由不会在重解析中变化的量组成**。这里有个陷阱：
    Paper 行和 MarkScheme 行也会被删除重建，所以 paper_id / mark_scheme_id
    同样是代理主键，不能进自然键。真正稳定的是 document_id
    （由 identity_key 决定，跨重解析不变）加上题号路径。

    - question: (document_id, number_path)
    - mark_scheme_entry: (document_id, number_path)
    """
    keys: dict[str, dict[str, Any]] = {"question": {}, "mark_scheme_entry": {}, "paper": {}}
    if not document_ids:
        return keys

    for paper in session.scalars(select(Paper).where(Paper.document_id.in_(document_ids))):
        keys["paper"][paper.id] = {"document_id": paper.document_id}
    for qid, doc_id, path in session.execute(
        select(Question.id, Paper.document_id, Question.number_path).join(
            Paper, Paper.id == Question.paper_id
        ).where(Paper.document_id.in_(document_ids))
    ).all():
        keys["question"][qid] = {"document_id": doc_id, "number_path": path}

    for eid, doc_id, path in session.execute(
        select(MarkSchemeEntry.id, MarkScheme.document_id, MarkSchemeEntry.number_path).join(
            MarkScheme, MarkScheme.id == MarkSchemeEntry.mark_scheme_id
        ).where(MarkScheme.document_id.in_(document_ids))
    ).all():
        keys["mark_scheme_entry"][eid] = {"document_id": doc_id, "number_path": path}
    return keys


def _remap_overrides(session, *, overrides):
    from ..core.models import ParseRun, ReviewTask
    from ..parsing.pipeline import ParsePipeline

    stats = {"remapped": 0, "conflicted": 0, "orphaned": 0, "applied": 0}
    applied_targets = set()
    pipe = ParsePipeline(session)
    for ov in overrides:
        if not ov.active:
            continue
        obj = session.get(_target_models()[ov.target_type], ov.target_id)
        run = session.get(ParseRun, obj.parse_run_id)
        if run is None:
            raise RuntimeError("人工覆盖目标缺少解析轮次，旧结果已保留")
        target = (ov.target_type, obj.id)
        if target not in applied_targets:
            pipe._apply_overrides(ov.target_type, obj, run)
            applied_targets.add(target)
        if ov.conflict_detected:
            stats["conflicted"] += 1
            session.add(ReviewTask(target_type=ov.target_type, target_id=obj.id,
                                   reason="override_conflict_after_reparse", priority=1, status="open"))
        else:
            stats["applied"] += 1
    session.flush()
    return stats


def _lookup_natural_key(session: Session, target_type: str, key: dict[str, Any]) -> Optional[int]:
    """按 (document_id, number_path) 找回重建后的新主键。"""
    doc_id = key["document_id"]
    if target_type == "paper":
        ids = list(session.scalars(select(Paper.id).where(Paper.document_id == doc_id)))
        return ids[0] if len(ids) == 1 else None
    path = key["number_path"]
    if target_type == "question":
        ids = list(session.scalars(
            select(Question.id)
            .join(Paper, Paper.id == Question.paper_id)
            .where(Paper.document_id == doc_id, Question.number_path == path)
        ))
        return ids[0] if len(ids) == 1 else None
    if target_type == "mark_scheme_entry":
        ids = list(session.scalars(
            select(MarkSchemeEntry.id)
            .join(MarkScheme, MarkScheme.id == MarkSchemeEntry.mark_scheme_id)
            .where(MarkScheme.document_id == doc_id, MarkSchemeEntry.number_path == path)
        ))
        return ids[0] if len(ids) == 1 else None
    return None





def _capture_preserved_similarity(session, question_keys):
    from ..core.models import QuestionSimilarity
    from ..intelligence.similarity import METHOD
    records = []
    for row in session.scalars(select(QuestionSimilarity).where(
        (QuestionSimilarity.question_a_id.in_(question_keys) | QuestionSimilarity.question_b_id.in_(question_keys)),
        QuestionSimilarity.method != METHOD
    )):
        endpoints = []
        for qid in (row.question_a_id, row.question_b_id):
            q = session.get(Question, qid)
            paper = session.get(Paper, q.paper_id)
            endpoints.append(({"document_id": paper.document_id, "number_path": q.number_path}, q.stem_text))
        records.append(({c.name: getattr(row, c.name) for c in row.__table__.columns}, endpoints))
    return records


def _restore_preserved_similarity(session, records):
    from ..core.models import QuestionSimilarity
    for values, endpoints in records:
        ids = []
        for key, stem in endpoints:
            qid = _lookup_natural_key(session, "question", key)
            if qid is None or session.get(Question, qid).stem_text != stem:
                raise RuntimeError("人工相似关系目标变化，旧结果已保留")
            ids.append(qid)
        low, high = sorted(ids)
        session.add(QuestionSimilarity(**{**values, "question_a_id": low, "question_b_id": high}))
    session.flush()


def _capture_source_migration(session, targets):
    from ..core.models import OfficialAnswer
    answers = []
    for row, question, paper in session.execute(
        select(OfficialAnswer, Question, Paper).join(Question, Question.id == OfficialAnswer.question_id)
        .join(Paper, Paper.id == Question.paper_id)
        .where(OfficialAnswer.source_document_id.in_(targets))
    ):
        answers.append(({"document_id": paper.document_id, "number_path": question.number_path},
                        row.source_document_id, row.content))
    links = []
    for entry, ms, question, paper in session.execute(
        select(MarkSchemeEntry, MarkScheme, Question, Paper)
        .join(MarkScheme, MarkScheme.id == MarkSchemeEntry.mark_scheme_id)
        .join(Question, Question.id == MarkSchemeEntry.question_id)
        .join(Paper, Paper.id == Question.paper_id)
        .where(MarkScheme.document_id.in_(targets))
    ):
        links.append(({"document_id": ms.document_id, "number_path": entry.number_path},
                      {"document_id": paper.document_id, "number_path": question.number_path}, entry.answer_text))
    return answers, links


def _finish_source_migration(session, targets, old_answers, expected_links):
    from ..core.models import GeneratedExplanation, OfficialAnswer, ReviewTask
    from ..markscheme.answers import rebuild_official_answers
    changed = set()
    for entry_key, question_key, old_text in expected_links:
        eid = _lookup_natural_key(session, "mark_scheme_entry", entry_key)
        qid = _lookup_natural_key(session, "question", question_key)
        if eid is None or qid is None or session.get(MarkSchemeEntry, eid).question_id != qid:
            raise RuntimeError("官方评分目标消失、歧义或身份变化，旧结果已保留")
        if session.get(MarkSchemeEntry, eid).answer_text != old_text:
            changed.add(qid)
    rebuilt = rebuild_official_answers(session, document_ids=targets)
    qids = set(session.scalars(select(MarkSchemeEntry.question_id).join(MarkScheme)
                              .where(MarkScheme.document_id.in_(targets), MarkSchemeEntry.question_id.is_not(None))))
    for key, source_id, content in old_answers:
        qid = _lookup_natural_key(session, "question", key)
        if qid is None:
            raise RuntimeError("官方答案目标消失或歧义，旧结果已保留")
        qids.add(qid)
        contents = set(session.scalars(select(OfficialAnswer.content).where(
            OfficialAnswer.question_id == qid, OfficialAnswer.source_document_id == source_id
        )))
        if content not in contents:
            changed.add(qid)
    for qid in changed:
        for explanation in session.scalars(select(GeneratedExplanation).where(GeneratedExplanation.question_id == qid)):
            reviewed = session.scalar(select(ReviewTask.id).where(
                ReviewTask.target_type == "generated_explanation", ReviewTask.target_id == explanation.id,
                ReviewTask.reason == "explanation_review", ReviewTask.status == "done"))
            if explanation.provider == "rule-based" and explanation.review_status == "pending" and reviewed is None:
                continue  # unreviewed generated content is replaced, not preserved as reviewed evidence
            exists = session.scalar(select(ReviewTask.id).where(
                ReviewTask.target_type == "generated_explanation", ReviewTask.target_id == explanation.id,
                ReviewTask.reason == "official_source_changed", ReviewTask.status == "open"
            ))
            if exists is None:
                session.add(ReviewTask(target_type="generated_explanation", target_id=explanation.id,
                                       reason="official_source_changed", status="open", priority=1))
        question = session.get(Question, qid)
        paper = session.get(Paper, question.paper_id)
        session.get(Document, paper.document_id).status = "needs_review"
    session.flush()
    return {"answers_rebuilt": rebuilt, "changed_questions": len(changed), "question_ids": sorted(qids)}


def _capture_protected(session, targets, keys):
    from ..core.models import Difficulty, Formula, GeneratedExplanation, OfficialAnswer, QuestionTaxonomy

    if session.scalar(select(OfficialAnswer.id).where(
        OfficialAnswer.source_document_id.in_(targets), OfficialAnswer.source != "mark_scheme"
    ).limit(1)):
        raise ValueError("官方来源类型没有迁移解析器，旧结果已保留")
    records = []
    qids = list(keys["question"])
    for model in (GeneratedExplanation, OfficialAnswer, QuestionTaxonomy, Difficulty, Formula):
        for row in session.scalars(select(model).where(model.question_id.in_(qids))):
            protect = (
                model in (GeneratedExplanation, OfficialAnswer)
                or (model is QuestionTaxonomy and (row.source != "auto" or row.reviewed))
                or (model is Difficulty and row.source != "estimated")
                or (model is Formula and row.source not in {"embedded", "ocr", "llm", "inline_text"})
            )
            if model is OfficialAnswer and row.source_document_id in targets:
                continue  # rebuilt from the new source entries after override migration
            if protect:
                records.append((model, {c.name: getattr(row, c.name) for c in model.__table__.columns},
                                keys["question"][row.question_id], session.get(Question, row.question_id).stem_text))
    return records


def _restore_protected(session, records):
    for model, values, key, stem in records:
        qid = _lookup_natural_key(session, "question", key)
        if qid is None or session.get(Question, qid).stem_text != stem:
            raise RuntimeError("受保护内容对应题目消失、歧义或正文变化，旧结果已保留")
        session.add(model(**{**values, "question_id": qid}))
    session.flush()


def _purge_derived(session: Session, document_ids: list[int], *, keep_history: bool) -> None:
    """清掉这些文档产出的派生数据，保留 artifact 与 document_revision。

    artifact（内容寻址的原始 PDF）与 revision（版本链）是"历史资源"本身，
    重解析绝不能删它们——否则就变成"重新下载"了。
    """
    if not document_ids:
        return
    paper_ids = list(
        session.scalars(select(Paper.id).where(Paper.document_id.in_(document_ids))).all()
    )
    ms_ids = list(
        session.scalars(select(MarkScheme.id).where(MarkScheme.document_id.in_(document_ids))).all()
    )
    q_ids = (
        list(session.scalars(select(Question.id).where(Question.paper_id.in_(paper_ids))).all())
        if paper_ids
        else []
    )

    if q_ids:
        from ..core.models import (
            Difficulty,
            Formula,
            GeneratedExplanation,
            OfficialAnswer,
            QuestionSimilarity,
            QuestionTaxonomy,
        )

        # 所有指向这些题的子表都要清掉。注意不能只按"来源文档"筛：
        # 重解析一份试卷时，它的 Mark Scheme 文档并不在 document_ids 里，
        # 但那些评分条目和官方答案正指向即将被删的题。
        for row in session.scalars(
            select(QuestionAsset).where(QuestionAsset.question_id.in_(q_ids))
        ).all():
            session.delete(row)
        for row in session.scalars(select(Formula).where(Formula.question_id.in_(q_ids))).all():
            session.delete(row)
        for row in session.scalars(
            select(OfficialAnswer).where(OfficialAnswer.question_id.in_(q_ids))
        ).all():
            session.delete(row)
        for row in session.scalars(
            select(MarkSchemeEntry).where(MarkSchemeEntry.question_id.in_(q_ids))
        ).all():
            # 只断开关联，条目本身属于 Mark Scheme 文档，留着等它自己被重解析
            row.question_id = None
        for row in session.scalars(
            select(QuestionTaxonomy).where(QuestionTaxonomy.question_id.in_(q_ids))
        ).all():
            session.delete(row)
        for row in session.scalars(
            select(Difficulty).where(Difficulty.question_id.in_(q_ids))
        ).all():
            session.delete(row)
        for row in session.scalars(
            select(GeneratedExplanation).where(GeneratedExplanation.question_id.in_(q_ids))
        ).all():
            session.delete(row)
        for row in session.scalars(
            select(QuestionSimilarity).where(
                QuestionSimilarity.question_a_id.in_(q_ids)
                | QuestionSimilarity.question_b_id.in_(q_ids)
            )
        ).all():
            session.delete(row)
        session.flush()

        # 题目自引用：先断父子，再删
        for q in session.scalars(select(Question).where(Question.id.in_(q_ids))).all():
            q.parent_id = None
        session.flush()
        for q in session.scalars(select(Question).where(Question.id.in_(q_ids))).all():
            session.delete(q)
        session.flush()

    if ms_ids:
        from ..core.models import OfficialAnswer

        for row in session.scalars(
            select(MarkSchemeEntry).where(MarkSchemeEntry.mark_scheme_id.in_(ms_ids))
        ).all():
            session.delete(row)
        for row in session.scalars(
            select(OfficialAnswer).where(OfficialAnswer.source_document_id.in_(document_ids))
        ).all():
            session.delete(row)
        session.flush()

    for pid in paper_ids:
        p = session.get(Paper, pid)
        if p is not None:
            session.delete(p)
    for mid in ms_ids:
        m = session.get(MarkScheme, mid)
        if m is not None:
            session.delete(m)
    session.flush()

    if not keep_history:
        from ..core.models import ParseRun, ReviewTask, ValidationFinding

        runs = list(session.scalars(select(ParseRun).where(
            ParseRun.document_revision_id.in_(select(DocumentRevision.id).where(
                DocumentRevision.document_id.in_(document_ids)
            ))
        )))
        run_ids = [run.id for run in runs]
        for finding in session.scalars(select(ValidationFinding).where(ValidationFinding.parse_run_id.in_(run_ids))):
            session.delete(finding)
        for task in session.scalars(select(ReviewTask).where(ReviewTask.parse_run_id.in_(run_ids))):
            task.parse_run_id = None
        session.flush()
        for run in runs:
            session.delete(run)
    session.flush()
