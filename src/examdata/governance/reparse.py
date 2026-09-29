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
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.models import (
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
    return {"question": Question, "mark_scheme_entry": MarkSchemeEntry}


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


def reparse_documents(
    session: Session,
    *,
    document_ids: Optional[list[int]] = None,
    limit: Optional[int] = None,
    keep_history: bool = True,
) -> dict[str, Any]:
    """重新解析历史文档，并返回新旧对比。

    不重新下载：清掉派生数据后由 ParsePipeline 从本地 artifact 重建。
    keep_history=True 时旧的 ParseRun 记录保留（它是溯源链的一环），
    只删除它产出的题目/条目等派生行。
    """
    from ..parsing.pipeline import ParsePipeline

    if document_ids:
        docs = [session.get(Document, d) for d in document_ids]
        docs = [d for d in docs if d is not None]
    else:
        stmt = select(Document).order_by(Document.id)
        if limit:
            stmt = stmt.limit(limit)
        docs = list(session.scalars(stmt).all())

    before = {d.id: snapshot(session, d.id) for d in docs}
    # 删除前记录自然键 -> 旧主键。人工修正挂在主键上，而重解析会重建题目行，
    # 主键必然变化；只有按自然键（试卷 + 题号路径）才能把修正接回新行。
    natural_keys = _capture_natural_keys(session, [d.id for d in docs])
    _purge_derived(session, [d.id for d in docs], keep_history=keep_history)

    pipe = ParsePipeline(session)
    stats = pipe.run()

    # 重新解析的语义是"从新的解析结果重新派生一切"。派生数据在 _purge_derived
    # 里被清掉了，如果这里不重建，重解析过的文档就会静默地缺少知识点/难度/相似题
    # ——数据看起来"成功"，实际上比重新解析前更不完整。
    derived = _rebuild_derived(session)
    relinked = _relink_mark_scheme_entries(session)

    remap = _remap_overrides(session, natural_keys)

    results: list[dict[str, Any]] = []
    regressed = 0
    for d in docs:
        after = snapshot(session, d.id)
        d_diff = diff(before[d.id], after)
        if d_diff.is_regression:
            regressed += 1
        results.append(d_diff.to_dict())

    return {
        "documents": len(docs),
        "regressed": regressed,
        "parse_stats": stats.to_dict(),
        "derived": derived,
        "relinked": relinked,
        "diffs": results,
        "overrides": remap,
    }


def _relink_mark_scheme_entries(session: Session) -> dict[str, int]:
    """把评分条目重新挂到重建后的题目上。

    这是重解析里最容易漏掉的一环：清题目时必须断开 MarkSchemeEntry.question_id
    （否则外键挡住删除），但**断开的关联不会自动恢复**——因为 Mark Scheme
    文档通常不在本次重解析范围内，它不会自己再跑一遍。

    只处理当前未关联的条目，不碰已有的关联：已有的是别处（可能人工）建立的，
    重新计算一遍可能把它们改坏。
    """
    from ..core.models import MarkScheme
    from ..markscheme.cambridge import link_entries_to_questions

    stats = {"papers": 0, "entries": 0, "linked": 0}
    ms_docs = list(
        session.scalars(
            select(MarkScheme).where(
                MarkScheme.id.in_(
                    select(MarkSchemeEntry.mark_scheme_id).where(
                        MarkSchemeEntry.question_id.is_(None)
                    )
                )
            )
        ).all()
    )
    if not ms_docs:
        return stats

    for ms in ms_docs:
        doc = session.get(Document, ms.document_id)
        if doc is None:
            continue
        # 找对应的试卷文档（与 pipeline._find_matching_paper 同一套身份条件）
        paper_doc = session.scalar(
            select(Document).where(
                Document.board_id == doc.board_id,
                Document.doc_type.in_(["question_paper", "specimen_paper"]),
                Document.paper_code == doc.paper_code,
                Document.subject_id == doc.subject_id,
            )
        )
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


def _rebuild_derived(session: Session) -> dict[str, Any]:
    """重建被 _purge_derived 清掉的智能层数据。

    按依赖顺序：知识点标注 -> 难度（用到标注数）-> 相似题。
    全部用 replace=True：这里要的是"与当前解析结果一致"，不是增量补。
    失败不抛出：派生数据缺失是**可降级**的（题目本身还在），
    不应该让整个重解析报失败；但要在返回值里如实报告。
    """
    out: dict[str, Any] = {}
    try:
        from ..intelligence import (
            assign_taxonomy,
            estimate_all,
            find_similar,
            generate_explanations,
            sync_taxonomy,
        )

        sync_taxonomy(session)
        out["taxonomy"] = assign_taxonomy(session, replace=True)
        out["difficulty"] = estimate_all(session, replace=True)
        out["similarity"] = find_similar(session, replace=True)
        # 解析生成依赖知识点与官方条目，必须排在最后
        out["explanation"] = generate_explanations(session, replace=True)
    except Exception as exc:  # pragma: no cover - 依赖数据缺失时的降级路径
        out["error"] = f"{type(exc).__name__}: {exc}"
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
    keys: dict[str, dict[str, Any]] = {"question": {}, "mark_scheme_entry": {}}
    if not document_ids:
        return keys

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


def _remap_overrides(session: Session, natural_keys: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """把人工修正重新挂到重解析后的新行上。

    三种结果，任何一种都不静默：
    - remapped：按自然键找到新行，修正继续生效（并重新把值写回）。
    - conflicted：目标主体被重建但自然键已不存在（题号路径变了），
      标记冲突并进待检查，**保留人工值**，由人来判断是算法改对了还是改错了。
    - orphaned：目标主体本就不在本次重解析范围内，保持原样。
    """
    from ..core.models import FieldOverride, ReviewTask

    stats = {"remapped": 0, "conflicted": 0, "orphaned": 0, "applied": 0}
    for target_type, old_map in natural_keys.items():
        if not old_map:
            continue
        model = _target_models()[target_type]
        for ov in session.scalars(
            select(FieldOverride).where(
                FieldOverride.target_type == target_type,
                FieldOverride.active.is_(True),
            )
        ).all():
            key = old_map.get(ov.target_id)
            if key is None:
                stats["orphaned"] += 1
                continue
            new_id = _lookup_natural_key(session, target_type, key)
            if new_id is None:
                ov.conflict_detected = True
                ov.conflict_detail = (
                    f"重解析后找不到对应主体（自然键 {key}），人工值 {ov.value!r} 保留待人工确认"
                )
                session.add(
                    ReviewTask(
                        target_type=target_type,
                        target_id=ov.target_id,
                        reason="override_target_missing_after_reparse",
                        priority=1,
                        status="open",
                    )
                )
                stats["conflicted"] += 1
                continue
            if new_id != ov.target_id:
                ov.target_id = new_id
                stats["remapped"] += 1
            obj = session.get(model, new_id)
            if obj is None:
                continue
            setattr(obj, ov.field_path, ov.value)
            if hasattr(obj, "has_override"):
                obj.has_override = True
            # 自然键匹配上并且已重新应用，说明修正仍然有效：
            # 清掉解析过程中可能留下的冲突标记，否则队列里会长期挂着
            # 一条"已解决但显示冲突"的记录。
            ov.conflict_detected = False
            ov.conflict_detail = None
            stats["applied"] += 1
    session.flush()
    return stats


def _lookup_natural_key(session: Session, target_type: str, key: dict[str, Any]) -> Optional[int]:
    """按 (document_id, number_path) 找回重建后的新主键。"""
    doc_id = key["document_id"]
    path = key["number_path"]
    if target_type == "question":
        return session.scalar(
            select(Question.id)
            .join(Paper, Paper.id == Question.paper_id)
            .where(Paper.document_id == doc_id, Question.number_path == path)
        )
    if target_type == "mark_scheme_entry":
        return session.scalar(
            select(MarkSchemeEntry.id)
            .join(MarkScheme, MarkScheme.id == MarkSchemeEntry.mark_scheme_id)
            .where(MarkScheme.document_id == doc_id, MarkSchemeEntry.number_path == path)
        )
    return None





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

    # 重新排队解析
    for rev in session.scalars(
        select(DocumentRevision).where(DocumentRevision.document_id.in_(document_ids))
    ).all():
        rev.parse_status = "pending"
        rev.parse_error = None
    if not keep_history:
        from ..core.models import ParseRun

        for run in session.scalars(
            select(ParseRun).where(
                ParseRun.document_revision_id.in_(
                    select(DocumentRevision.id).where(
                        DocumentRevision.document_id.in_(document_ids)
                    )
                )
            )
        ).all():
            session.delete(run)
    session.flush()
