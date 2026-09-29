"""解析落库流水线：把已存储的 PDF 变成结构化的题目与评分数据。

  DocumentRevision(已存储) -> ParseRun -> Paper / Question / Asset
                                       -> MarkScheme / MarkSchemeEntry
                                       -> OfficialAnswer
                                       -> ValidationFinding

设计要点：
- 解析产物是**可重建的派生数据**：重新解析会写入新的 ParseRun，
  历史 ParseRun 保留，便于新旧结果对比（需求：支持用新算法重解析历史资源）。
- 人工修正（FieldOverride）不会被下一次自动同步无条件覆盖。
- 校验发现写入 ValidationFinding，低置信度转 ReviewTask。
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import Settings, get_settings
from ..core.models import (
    Artifact,
    Asset,
    Document,
    DocumentRevision,
    MarkScheme,
    MarkSchemeEntry,
    OfficialAnswer,
    Paper,
    ParseRun,
    Question,
    QuestionAsset,
    ReviewTask,
    ValidationFinding,
)
from ..markscheme.cambridge import CambridgeMarkSchemeParser, link_entries_to_questions
from ..markscheme.base import MarkSchemeDraft
from .content_classify import classify_content, reconcile
from .metadata import extract_paper_metadata
from .pdfdoc import load_pdf
from .segment import QuestionTree, build_question_tree

# 低置信度阈值：低于此值转人工复核
REVIEW_CONFIDENCE = 0.6


@dataclass
class ParseStats:
    revisions: int = 0
    papers: int = 0
    questions: int = 0
    mark_schemes: int = 0
    entries: int = 0
    entries_linked: int = 0
    assets: int = 0
    findings: int = 0
    review_tasks: int = 0
    failed: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = dict(self.__dict__)
        d["errors"] = d["errors"][:50]
        return d


class ParsePipeline:
    """把 DocumentRevision 解析为结构化数据。"""

    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        from ..core.storage import ContentAddressedStore

        self.session = session
        self.settings = settings or get_settings()
        self.store = ContentAddressedStore()
        self.stats = ParseStats()

    # -- 对外入口 ---------------------------------------------------------

    def run(self, *, limit: Optional[int] = None, document_id: Optional[int] = None) -> ParseStats:
        stmt = (
            select(DocumentRevision)
            .where(DocumentRevision.parse_status == "pending")
            .order_by(DocumentRevision.id)
        )
        if document_id is not None:
            stmt = stmt.where(DocumentRevision.document_id == document_id)
        if limit:
            stmt = stmt.limit(limit)

        revisions = list(self.session.scalars(stmt).all())
        # 两阶段解析：必须先解析试卷，再解析评分标准。
        # 否则 Mark Scheme 找不到对应的 Paper/Question，条目无法挂到题目上。
        revisions.sort(key=self._phase_key)
        for rev in revisions:
            try:
                self.parse_revision(rev)
                self.session.commit()
            except Exception as exc:
                self.session.rollback()
                self.stats.failed += 1
                self.stats.errors.append(f"revision {rev.id}: {type(exc).__name__}: {exc}")
                self._mark_failed(rev.id, str(exc))
                self.session.commit()
        return self.stats

    def _phase_key(self, rev: DocumentRevision) -> int:
        """解析阶段排序键：试卷(0) -> 评分标准(1) -> 其他(2)。

        稳定排序，同阶段内仍按 revision id 升序。
        """
        doc = self.session.get(Document, rev.document_id)
        doc_type = doc.doc_type if doc is not None else ""
        if doc_type in ("question_paper", "specimen_paper"):
            return 0
        if doc_type in ("mark_scheme", "specimen_mark_scheme"):
            return 1
        return 2

    def _mark_failed(self, revision_id: int, error: str) -> None:
        rev = self.session.get(DocumentRevision, revision_id)
        if rev is not None:
            rev.parse_status = "failed"
            rev.parse_error = error[:1000]

    # -- 单条解析 ---------------------------------------------------------

    def parse_revision(self, rev: DocumentRevision) -> None:
        doc = self.session.get(Document, rev.document_id)
        if doc is None:
            self.stats.skipped += 1
            return

        artifact = (
            self.session.get(Artifact, rev.artifact_id) if rev.artifact_id else None
        )
        if artifact is None:
            rev.parse_status = "failed"
            rev.parse_error = "revision 无 artifact"
            self.stats.skipped += 1
            return

        path = self._artifact_path(artifact.storage_key)
        if not path.exists():
            rev.parse_status = "failed"
            rev.parse_error = f"文件缺失: {path}"
            self.stats.skipped += 1
            return

        parse_run = ParseRun(
            document_revision_id=rev.id,
            parser_version=self.settings.parser_version,
            params={"doc_type": doc.doc_type},
            status="running",
            started_at=_dt.datetime.now(_dt.timezone.utc),
            stats={},
        )
        self.session.add(parse_run)
        self.session.flush()

        self.stats.revisions += 1
        if doc.doc_type in ("question_paper", "specimen_paper"):
            self._parse_question_paper(doc, rev, parse_run, path)
        elif doc.doc_type in ("mark_scheme", "specimen_mark_scheme"):
            self._parse_mark_scheme(doc, rev, parse_run, path)
        else:
            parse_run.status = "skipped"
            self.stats.skipped += 1

        parse_run.status = "completed" if parse_run.status == "running" else parse_run.status
        parse_run.finished_at = _dt.datetime.now(_dt.timezone.utc)
        parse_run.stats = {"questions": self.stats.questions, "entries": self.stats.entries}

        rev.parse_status = "parsed"
        rev.parse_error = None
        # Document.status 的取值域是 ok / needs_review / failed。
        # 一份文档可能有多个 revision，只要**任一** revision 产生了 error/critical
        # 级发现，整份文档就是 needs_review，不能被后一个干净的 revision 覆盖回 ok。
        doc.status = "needs_review" if self._has_blocking_findings(doc.id) else "ok"

    def _has_blocking_findings(self, document_id: int) -> bool:
        """该文档的所有解析轮次中是否出现过 error/critical 级校验发现。"""
        row = self.session.scalar(
            select(ValidationFinding.id)
            .join(
                DocumentRevision,
                DocumentRevision.id == ParseRun.document_revision_id,
            )
            .join(ParseRun, ParseRun.id == ValidationFinding.parse_run_id)
            .where(
                DocumentRevision.document_id == document_id,
                ValidationFinding.severity.in_(["error", "critical"]),
            )
            .limit(1)
        )
        return row is not None

    def _artifact_path(self, storage_key: str):
        return self.settings.artifacts_dir / storage_key

    # -- 试卷 -------------------------------------------------------------

    def _parse_question_paper(self, doc, rev, parse_run, path) -> None:
        pdf = load_pdf(path)
        md = extract_paper_metadata(pdf)
        tree = build_question_tree(pdf, expected_total_marks=md.total_marks)

        # 回填文档元数据（封面页是权威来源）
        if md.subject_code:
            doc.attrs = {**(doc.attrs or {}), "cover_metadata": md.to_dict()}
        if md.year and not doc.year:
            doc.year = md.year

        paper = Paper(
            document_id=doc.id,
            paper_no=md.paper_number or doc.paper_code,
            duration_minutes=md.duration_minutes,
            marks_total=tree.total_marks or md.total_marks,
            question_count=len(tree.roots),
            parse_run_id=parse_run.id,
            page_count=len(pdf.pages),
            attrs={
                "declared_total_marks": md.total_marks,
                "front_matter_pages": tree.front_matter_pages,
                "bold_signal_available": tree.bold_signal_available,
            },
        )
        self.session.add(paper)
        self.session.flush()
        self.stats.papers += 1

        id_by_node: dict[int, int] = {}
        for order, node in enumerate(tree.walk(), 1):
            parent_qid = id_by_node.get(id(node.parent)) if node.parent is not None else None
            q = Question(
                paper_id=paper.id,
                parent_id=parent_qid,
                number_label=node.label,
                number_path=node.number_path,
                display_order=node.order or order,
                depth=node.depth,
                kind=node.kind,
                marks=node.marks,
                page_from=node.page_from,
                page_to=node.page_to,
                stem_text=node.text,
                bbox_from=node.bbox_from,
                bbox_to=node.bbox_to,
                parse_run_id=parse_run.id,
                parse_confidence=node.confidence,
                has_override=False,
                attrs={},
            )
            self.session.add(q)
            self.session.flush()
            id_by_node[id(node)] = q.id
            self.stats.questions += 1

            self._apply_overrides("question", q, parse_run)

        # 图形资产
        for node in tree.walk():
            qid = id_by_node.get(id(node))
            if qid is None:
                continue
            for i, asset_ref in enumerate(node.assets):
                asset = self._upsert_asset(asset_ref)
                self.session.add(
                    QuestionAsset(
                        question_id=qid,
                        asset_id=asset.id,
                        role=asset_ref.role,
                        page=asset_ref.page,
                        bbox=asset_ref.bbox,
                        reading_order=i,
                        caption=None,
                        confidence=1.0,
                    )
                )
                self.stats.assets += 1

        self._record_findings("document", doc.id, tree.findings, parse_run)
        self._record_classification_finding(doc, path, parse_run)

    def _record_classification_finding(
        self, doc: Document, path: Path, parse_run: ParseRun
    ) -> None:
        """交叉验证文件类型：页面判定 vs 文档内容判定。

        需求："文件类型判断不能只依赖文件名，还需要能够结合官方页面信息、
        文件本身信息以及文档内容进行判断。"——两个独立信号都拿到了，
        如果它们不一致，就不能装作没看见：写一条发现，让这份文件进待检查。

        只读不写 doc_type：页面标注是权威来源，内容判定只用于发现异常。
        """
        ev = classify_content(path)
        if ev.error or ev.doc_type is None:
            return

        final, confidence, method = reconcile(doc.doc_type, ev)
        if method != "conflict":
            return

        self._record_findings(
            "document",
            doc.id,
            [
                {
                    "rule": "doc_type_content_conflict",
                    "severity": "error",
                    "message": (
                        f"页面判定为 {doc.doc_type}，但 PDF 内容更像是 {ev.doc_type}"
                    ),
                    "evidence": {
                        "label_type": doc.doc_type,
                        "content_type": ev.doc_type,
                        "content_scores": ev.scores,
                        "matched": ev.matched,
                        "resolved_type": final,
                        "confidence": confidence,
                    },
                }
            ],
            parse_run,
        )

    def _upsert_asset(self, asset_ref) -> Asset:
        """资产按内容寻址存储后再落库，天然去重。"""
        mime = asset_ref.mime or None
        stored = self.store.put_bytes(asset_ref.data, mime)
        existing = self.session.scalar(
            select(Asset).where(Asset.sha256 == stored.sha256)
        )
        if existing is not None:
            return existing
        asset = Asset(
            # sha256 是 NOT NULL + UNIQUE，既是内容寻址键也是去重键
            sha256=stored.sha256,
            storage_key=stored.storage_key,
            kind=asset_ref.kind or "figure",
            mime=mime or stored.mime,
            width=asset_ref.width,
            height=asset_ref.height,
            attrs={
                "sha256": stored.sha256,
                "ext": asset_ref.ext,
                "size_bytes": stored.size_bytes,
            },
        )
        self.session.add(asset)
        self.session.flush()
        return asset

    # -- 评分标准 ---------------------------------------------------------

    def _parse_mark_scheme(self, doc, rev, parse_run, path) -> None:
        pdf = load_pdf(path)
        draft: MarkSchemeDraft = CambridgeMarkSchemeParser().parse(pdf, pdf_path=str(path))

        matched_doc = self._find_matching_paper(doc)
        ms = MarkScheme(
            document_id=doc.id,
            matched_paper_document_id=matched_doc.id if matched_doc else None,
            match_confidence=1.0 if matched_doc else 0.0,
            match_method="identity_sibling" if matched_doc else "unmatched",
            match_evidence={"paper_code": doc.paper_code, "year": doc.year},
            parse_run_id=parse_run.id,
        )
        self.session.add(ms)
        self.session.flush()
        self.stats.mark_schemes += 1

        questions: list[Question] = []
        if matched_doc is not None:
            paper = self.session.scalar(select(Paper).where(Paper.document_id == matched_doc.id))
            if paper is not None:
                questions = list(
                    self.session.scalars(
                        select(Question).where(Question.paper_id == paper.id)
                    ).all()
                )

        linked, unmatched, without = link_entries_to_questions(draft.entries, questions)
        link_map = {i: qid for i, qid in linked}
        # 已挂到题目、但评分标准里没有可提取答案文本的条目：需要人工补录
        missing_answers: list[str] = []

        for i, e in enumerate(draft.entries):
            qid = link_map.get(i)
            entry = MarkSchemeEntry(
                mark_scheme_id=ms.id,
                question_id=qid,
                number_label=e.number_label,
                number_path=e.number_path,
                marks=e.marks,
                answer_text=e.answer_text,
                acceptable_answers=e.acceptable_answers,
                method_marks=e.method_marks,
                accuracy_marks=e.accuracy_marks,
                independent_marks=e.independent_marks,
                ecf=e.ecf,
                guidance=e.guidance,
                raw=e.raw,
                parse_confidence=e.parse_confidence,
            )
            self.session.add(entry)
            self.session.flush()
            self.stats.entries += 1
            if qid is not None:
                self.stats.entries_linked += 1
                # 官方答案与系统生成内容严格分离。
                # content 为非空列：解析不出答案文本时只保留评分条目，
                # 不写入空答案，由校验层标记待人工补录。
                if e.answer_text and e.answer_text.strip():
                    self.session.add(
                        OfficialAnswer(
                            question_id=qid,
                            source="mark_scheme",
                            source_document_id=doc.id,
                            content=e.answer_text,
                            is_official=True,
                            attrs={"number_path": e.number_path, "marks": e.marks},
                        )
                    )
                else:
                    missing_answers.append(e.number_path)
            self._apply_overrides("mark_scheme_entry", entry, parse_run)

        findings = list(draft.findings)
        if missing_answers:
            findings.append(
                {
                    "rule": "ms_entry_missing_answer_text",
                    "severity": "warning",
                    "message": f"{len(missing_answers)} 条已关联题目的评分条目缺少答案文本",
                    "evidence": {"paths": missing_answers[:50]},
                }
            )
        if unmatched:
            findings.append(
                {
                    "rule": "ms_entries_unmatched",
                    "severity": "warning",
                    "message": f"{len(unmatched)} 条评分条目未匹配到题目",
                    "evidence": {"paths": unmatched[:50]},
                }
            )
        if questions and without:
            findings.append(
                {
                    "rule": "questions_without_mark_scheme",
                    "severity": "warning",
                    "message": f"{len(without)} 道题无评分条目",
                    "evidence": {"paths": without[:50]},
                }
            )
        # 两份独立文件的交叉校验：分值合计必须一致
        paper_marks = None
        if matched_doc is not None:
            p = self.session.scalar(select(Paper).where(Paper.document_id == matched_doc.id))
            paper_marks = p.marks_total if p else None
        if paper_marks and draft.metadata.get("total_marks") != paper_marks:
            findings.append(
                {
                    "rule": "marks_total_mismatch_cross_document",
                    "severity": "error",
                    "message": (
                        f"Mark Scheme 分值合计 {draft.metadata.get('total_marks')} "
                        f"!= 试卷总分 {paper_marks}"
                    ),
                }
            )

        self._record_findings("document", doc.id, findings, parse_run)

    def _find_matching_paper(self, doc: Document) -> Optional[Document]:
        """按同一身份（考试局/资格/科目/年份/季/Paper）找对应试卷。"""
        stmt = select(Document).where(
            Document.board_id == doc.board_id,
            Document.doc_type.in_(["question_paper", "specimen_paper"]),
            Document.paper_code == doc.paper_code,
        )
        if doc.subject_id is not None:
            stmt = stmt.where(Document.subject_id == doc.subject_id)
        if doc.year is not None:
            stmt = stmt.where(Document.year == doc.year)
        return self.session.scalar(stmt)

    # -- 校验与人工修正 ---------------------------------------------------

    def _record_findings(
        self, subject_type: str, subject_id: int, findings: list[dict], parse_run: ParseRun
    ) -> None:
        for f in findings:
            self.session.add(
                ValidationFinding(
                    subject_type=subject_type,
                    subject_id=subject_id,
                    rule_code=f.get("rule", "unknown"),
                    severity=f.get("severity", "warning"),
                    message=f.get("message", ""),
                    evidence=f.get("evidence"),
                    parse_run_id=parse_run.id,
                    status="open",
                )
            )
            self.stats.findings += 1
            if f.get("severity") in ("error", "critical"):
                rule = f.get("rule", "unknown")
                # 幂等：同一主体同一规则只保留一条**未处置**的待检查项。
                # 否则每次重新解析都会再插一条，队列里堆满同一问题的副本
                # （实测重解析同一文档 4 次后出现 4 条完全相同的记录）。
                # 已处置过的（done/dismissed）不在此列——问题复现时应该重新提醒。
                existing = self.session.scalar(
                    select(ReviewTask.id).where(
                        ReviewTask.target_type == subject_type,
                        ReviewTask.target_id == subject_id,
                        ReviewTask.reason == rule,
                        ReviewTask.status.in_(["open", "in_progress"]),
                    )
                )
                if existing is not None:
                    continue
                self.session.add(
                    ReviewTask(
                        target_type=subject_type,
                        target_id=subject_id,
                        reason=rule,
                        priority=1 if f.get("severity") == "critical" else 2,
                        status="open",
                        assignee=None,
                        resolution=None,
                        parse_run_id=parse_run.id,
                    )
                )
                self.stats.review_tasks += 1

    def _apply_overrides(self, target_type: str, obj: Any, parse_run: ParseRun) -> None:
        """重新应用人工修正。

        需求：人工确认过的字段不能被下一次自动同步无条件覆盖。
        这里按 parser_version 决定是否沿用：若 override 声明只对旧版本有效，
        则新版本解析结果优先，同时标记冲突待人工确认。
        """
        from ..core.models import FieldOverride

        overrides = self.session.scalars(
            select(FieldOverride).where(
                FieldOverride.target_type == target_type,
                FieldOverride.target_id == obj.id,
                FieldOverride.active.is_(True),
            )
        ).all()
        for ov in overrides:
            applies = ov.applies_to_parser_versions
            if applies and parse_run.parser_version not in applies:
                ov.conflict_detected = True
                ov.conflict_detail = (
                    f"解析器版本 {parse_run.parser_version} 与 override 适用范围不一致"
                )
                continue
            current = getattr(obj, ov.field_path, None)
            if current is not None and ov.source_value is not None and current != ov.source_value:
                ov.conflict_detected = True
                ov.conflict_detail = f"自动解析值 {current!r} 与人工值 {ov.value!r} 冲突"
                continue
            setattr(obj, ov.field_path, ov.value)
            if hasattr(obj, "has_override"):
                obj.has_override = True
