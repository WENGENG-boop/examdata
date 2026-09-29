"""数据模型（Schema 脊柱）。

设计原则（对应需求文档）：
1. 统一而不抹平差异：统一字段单独成列，考试局特有属性一律进 attrs JSON 列。
2. 来源可追溯：任何实体都能通过 provenance_edge 追到官方 URL、发现时间与运行批次。
3. 版本化：artifact/document 均保留版本链，官方更新不覆盖历史。
4. 官方内容与系统生成内容严格分离：official_answer 与 generated_explanation 分表。
5. 派生数据可重建，人工修正独立存储：field_override 与派生行分离，重解析后重新应用。
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON, list[Any]: JSON}


class TimestampMixin:
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


# --------------------------------------------------------------------------
# 维度层
# --------------------------------------------------------------------------


class Board(Base, TimestampMixin):
    """考试局，例如 Cambridge International、Pearson Edexcel、College Board。"""

    __tablename__ = "board"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    homepage: Mapped[Optional[str]] = mapped_column(String(1024))
    # 可行性分级：public / partial_public / login_walled / unsupported_public
    accessibility: Mapped[str] = mapped_column(String(32), default="public", nullable=False)
    attrs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Qualification(Base, TimestampMixin):
    """考试体系/资格：IGCSE、AS and A Level、O Level、AP、IB DP、SAT 等。"""

    __tablename__ = "qualification"
    __table_args__ = (UniqueConstraint("board_id", "key", name="uq_qualification_board_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    board_id: Mapped[int] = mapped_column(ForeignKey("board.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(96), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    attrs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    board: Mapped[Board] = relationship()


class Subject(Base, TimestampMixin):
    """科目。code 为考试局官方科目代码（如 Cambridge 0580）。"""

    __tablename__ = "subject"
    __table_args__ = (
        UniqueConstraint("qualification_id", "code", name="uq_subject_qualification_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    qualification_id: Mapped[int] = mapped_column(
        ForeignKey("qualification.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    slug: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    attrs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    qualification: Mapped[Qualification] = relationship()


class ExamSeries(Base, TimestampMixin):
    """考季：年份 + 季节 + 月份。"""

    __tablename__ = "exam_series"
    __table_args__ = (UniqueConstraint("year", "session", name="uq_series_year_session"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # june / november / march / may / october ...
    session: Mapped[str] = mapped_column(String(32), nullable=False)
    month: Mapped[Optional[int]] = mapped_column(Integer)
    attrs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


# --------------------------------------------------------------------------
# 来源与发现层
# --------------------------------------------------------------------------


class ResourceSource(Base, TimestampMixin):
    """逻辑入口：一个可被适配器巡检的官方页面。"""

    __tablename__ = "resource_source"
    __table_args__ = (UniqueConstraint("url", name="uq_source_url"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    board_id: Mapped[int] = mapped_column(ForeignKey("board.id"), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    # family_index / syllabus_papers / subject_index / api ...
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    adapter_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    discovery_method: Mapped[str] = mapped_column(String(64), default="html")
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_checked_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime)
    # 静默失效检测：连续多少次巡检无新增
    consecutive_empty_runs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    attrs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class SyncRun(Base, TimestampMixin):
    """一次同步运行。"""

    __tablename__ = "sync_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    board_id: Mapped[int] = mapped_column(ForeignKey("board.id"), nullable=False, index=True)
    adapter_key: Mapped[str] = mapped_column(String(64), nullable=False)
    # running / success / partial / failed
    status: Mapped[str] = mapped_column(String(32), default="running", nullable=False, index=True)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    finished_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime)
    stats: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[Optional[str]] = mapped_column(Text)


class ResourceCandidate(Base, TimestampMixin):
    """发现的资源条目（尚未下载）。"""

    __tablename__ = "resource_candidate"
    __table_args__ = (
        UniqueConstraint("url", name="uq_candidate_url"),
        Index("ix_candidate_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[Optional[int]] = mapped_column(ForeignKey("resource_source.id"), index=True)
    board_id: Mapped[int] = mapped_column(ForeignKey("board.id"), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    # 页面给出的锚文本/标题，是分类的主信号
    label: Mapped[Optional[str]] = mapped_column(String(1024))
    # new / updated / duplicate / gone / deleted / failed
    status: Mapped[str] = mapped_column(String(32), default="new", nullable=False)
    guessed_doc_type: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    # 已解析出的考试元数据（subject_code, year, series, paper_code ...）
    parsed_meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    page_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    etag: Mapped[Optional[str]] = mapped_column(String(255))
    last_modified: Mapped[Optional[str]] = mapped_column(String(128))
    first_seen_run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sync_run.id"))
    last_seen_run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sync_run.id"))
    last_seen_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime)
    # 内容哈希（下载后回填），用于 duplicate 判定
    content_sha256: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    error: Mapped[Optional[str]] = mapped_column(Text)


# --------------------------------------------------------------------------
# 文件层
# --------------------------------------------------------------------------


class Artifact(Base, TimestampMixin):
    """内容寻址的原始文件。同一份文件多处出现只存一份。"""

    __tablename__ = "artifact"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    mime: Mapped[Optional[str]] = mapped_column(String(128))
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    first_fetched_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(2048))
    attrs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ArtifactRevision(Base, TimestampMixin):
    """同一 URL 上文件的变更链：官方替换文件时保留历史。"""

    __tablename__ = "artifact_revision"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    artifact_id: Mapped[int] = mapped_column(ForeignKey("artifact.id"), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    etag: Mapped[Optional[str]] = mapped_column(String(255))
    last_modified: Mapped[Optional[str]] = mapped_column(String(128))
    fetched_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    supersedes_id: Mapped[Optional[int]] = mapped_column(ForeignKey("artifact_revision.id"))
    # new / updated / unchanged
    change_kind: Mapped[str] = mapped_column(String(32), default="new", nullable=False)


class Document(Base, TimestampMixin):
    """逻辑文件身份（如 Cambridge IGCSE 0580 June 2024 Paper 11 Question Paper）。

    identity_key 不依赖 URL，实现跨来源去重。
    """

    __tablename__ = "document"
    __table_args__ = (UniqueConstraint("identity_key", name="uq_document_identity"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    identity_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    board_id: Mapped[int] = mapped_column(ForeignKey("board.id"), nullable=False, index=True)
    qualification_id: Mapped[Optional[int]] = mapped_column(ForeignKey("qualification.id"))
    subject_id: Mapped[Optional[int]] = mapped_column(ForeignKey("subject.id"), index=True)
    series_id: Mapped[Optional[int]] = mapped_column(ForeignKey("exam_series.id"), index=True)
    # 统一字段
    doc_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    year: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    paper_code: Mapped[Optional[str]] = mapped_column(String(32), index=True)
    component: Mapped[Optional[str]] = mapped_column(String(32))
    variant: Mapped[Optional[str]] = mapped_column(String(32))
    level: Mapped[Optional[str]] = mapped_column(String(64))
    title: Mapped[Optional[str]] = mapped_column(String(1024))
    # 当前发布的 revision
    current_revision_id: Mapped[Optional[int]] = mapped_column(ForeignKey("document_revision.id"))
    # ok / needs_review / failed
    status: Mapped[str] = mapped_column(String(32), default="ok", nullable=False, index=True)
    attrs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class DocumentRevision(Base, TimestampMixin):
    """document 与 artifact 的版本绑定。"""

    __tablename__ = "document_revision"
    __table_args__ = (UniqueConstraint("document_id", "revision_no", name="uq_docrev_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("document.id"), nullable=False, index=True)
    artifact_id: Mapped[int] = mapped_column(ForeignKey("artifact.id"), nullable=False, index=True)
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(2048))
    discovered_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    # active / superseded / gone / deleted
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    parser_version: Mapped[Optional[str]] = mapped_column(String(32))
    # 解析流水线状态：pending / parsed / failed / needs_review
    parse_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    parse_error: Mapped[Optional[str]] = mapped_column(Text)


class DocClassification(Base, TimestampMixin):
    """文件类型判定结果，含多信号证据。"""

    __tablename__ = "doc_classification"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("document.id"), nullable=False, index=True)
    doc_type: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # 各信号及其权重，例如 {"label_regex": 0.9, "slug_crosscheck": 0.05}
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    method: Mapped[str] = mapped_column(String(32), default="label", nullable=False)


# --------------------------------------------------------------------------
# 题目层
# --------------------------------------------------------------------------


class Paper(Base, TimestampMixin):
    """一份试卷（对应某个 document）。"""

    __tablename__ = "paper"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("document.id"), nullable=False, index=True)
    paper_no: Mapped[Optional[str]] = mapped_column(String(32))
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    marks_total: Mapped[Optional[int]] = mapped_column(Integer)
    question_count: Mapped[Optional[int]] = mapped_column(Integer)
    parse_run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("parse_run.id"), index=True)
    page_count: Mapped[Optional[int]] = mapped_column(Integer)
    attrs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Question(Base, TimestampMixin):
    """题目节点。自引用构成题目树（大题 -> 小问 -> 子小问）。"""

    __tablename__ = "question"
    __table_args__ = (
        Index("ix_question_paper_order", "paper_id", "display_order"),
        Index("ix_question_number", "paper_id", "number_path"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("paper.id"), nullable=False, index=True)
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("question.id"), index=True)
    # 原始题号标签，如 "1" / "(a)" / "(ii)"
    number_label: Mapped[str] = mapped_column(String(64), nullable=False)
    # 完整路径，如 "1(a)(ii)"，便于检索与对齐
    number_path: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    depth: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # question / sub / part
    kind: Mapped[str] = mapped_column(String(32), default="question", nullable=False)
    marks: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    page_from: Mapped[Optional[int]] = mapped_column(Integer)
    page_to: Mapped[Optional[int]] = mapped_column(Integer)
    stem_text: Mapped[Optional[str]] = mapped_column(Text)
    # 题目可能跨页：记录其覆盖的页面区间与边界证据
    bbox_from: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    bbox_to: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    parse_run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("parse_run.id"), index=True)
    parse_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # 是否被人工修正过（field_override 存在）
    has_override: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    attrs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    paper: Mapped[Paper] = relationship()
    children: Mapped[list["Question"]] = relationship(back_populates="parent")
    parent: Mapped[Optional["Question"]] = relationship(
        back_populates="children", remote_side="Question.id"
    )


class Asset(Base, TimestampMixin):
    """内容寻址的图片/图表资产。"""

    __tablename__ = "asset"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    # figure / table / diagram / graph / chem / photo / svg
    kind: Mapped[str] = mapped_column(String(32), default="figure", nullable=False)
    mime: Mapped[Optional[str]] = mapped_column(String(64))
    width: Mapped[Optional[int]] = mapped_column(Integer)
    height: Mapped[Optional[int]] = mapped_column(Integer)
    attrs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class QuestionAsset(Base, TimestampMixin):
    """题目与资产关联，保留页面位置与阅读顺序，确保拆分后不丢内容。"""

    __tablename__ = "question_asset"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("question.id"), nullable=False, index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id"), nullable=False, index=True)
    # figure / table / formula_image / source_material
    role: Mapped[str] = mapped_column(String(32), default="figure", nullable=False)
    page: Mapped[Optional[int]] = mapped_column(Integer)
    bbox: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    reading_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    caption: Mapped[Optional[str]] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)


class Formula(Base, TimestampMixin):
    """公式：优先嵌入 LaTeX，其次 OCR/LLM。"""

    __tablename__ = "formula"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("question.id"), nullable=False, index=True)
    latex: Mapped[Optional[str]] = mapped_column(Text)
    mathml: Mapped[Optional[str]] = mapped_column(Text)
    # embedded / ocr / llm / inline_text
    source: Mapped[str] = mapped_column(String(32), default="inline_text", nullable=False)
    page: Mapped[Optional[int]] = mapped_column(Integer)
    bbox: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)


# --------------------------------------------------------------------------
# 答案与评分层（官方 / 生成 严格分离）
# --------------------------------------------------------------------------


class MarkScheme(Base, TimestampMixin):
    """一份 Mark Scheme 文档及其与试卷的匹配关系。"""

    __tablename__ = "mark_scheme"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("document.id"), nullable=False, index=True)
    matched_paper_document_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("document.id"), index=True
    )
    match_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    match_method: Mapped[Optional[str]] = mapped_column(String(32))
    match_evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    parse_run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("parse_run.id"))


class MarkSchemeEntry(Base, TimestampMixin):
    """评分标准条目，挂到具体题目/小问。"""

    __tablename__ = "mark_scheme_entry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mark_scheme_id: Mapped[int] = mapped_column(
        ForeignKey("mark_scheme.id"), nullable=False, index=True
    )
    question_id: Mapped[Optional[int]] = mapped_column(ForeignKey("question.id"), index=True)
    number_label: Mapped[str] = mapped_column(String(64), nullable=False)
    number_path: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    marks: Mapped[Optional[int]] = mapped_column(Integer)
    answer_text: Mapped[Optional[str]] = mapped_column(Text)
    # 可接受答案 / 替代答案
    acceptable_answers: Mapped[list[Any]] = mapped_column(JSON, default=list)
    # 各考试局评分语汇（M/A/B/ECF 等）保留为结构化字段
    method_marks: Mapped[Optional[int]] = mapped_column(Integer)
    accuracy_marks: Mapped[Optional[int]] = mapped_column(Integer)
    independent_marks: Mapped[Optional[int]] = mapped_column(Integer)
    ecf: Mapped[Optional[bool]] = mapped_column(Boolean)
    guidance: Mapped[Optional[str]] = mapped_column(Text)
    # 原始条目（行/单元格），保证可回溯
    raw: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    parse_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)


class OfficialAnswer(Base, TimestampMixin):
    """官方答案/说明。is_official 恒为 True，与生成内容物理隔离。"""

    __tablename__ = "official_answer"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("question.id"), nullable=False, index=True)
    # mark_scheme / examiner_report / scoring_guideline / sample_response
    source: Mapped[str] = mapped_column(String(48), nullable=False)
    source_document_id: Mapped[Optional[int]] = mapped_column(ForeignKey("document.id"))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_official: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    attrs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class GeneratedExplanation(Base, TimestampMixin):
    """系统生成的解题解析。永不与官方内容同表同字段。"""

    __tablename__ = "generated_explanation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("question.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[Optional[str]] = mapped_column(String(128))
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    # 解题思路 / 主要步骤 / 最终结果 / 评分关键点 / 常见错误
    approach: Mapped[Optional[str]] = mapped_column(Text)
    steps: Mapped[list[Any]] = mapped_column(JSON, default=list)
    final_answer: Mapped[Optional[str]] = mapped_column(Text)
    marking_points: Mapped[list[Any]] = mapped_column(JSON, default=list)
    common_errors: Mapped[list[Any]] = mapped_column(JSON, default=list)
    # pending / approved / rejected
    review_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    is_official: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


# --------------------------------------------------------------------------
# 智能层
# --------------------------------------------------------------------------


class TaxonomyNode(Base, TimestampMixin):
    """知识点体系节点。official / auto / manual 三类来源明确区分。"""

    __tablename__ = "taxonomy_node"
    __table_args__ = (UniqueConstraint("board_id", "code", name="uq_taxonomy_board_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    board_id: Mapped[Optional[int]] = mapped_column(ForeignKey("board.id"), index=True)
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("taxonomy_node.id"), index=True)
    code: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    # topic / subtopic / skill
    node_type: Mapped[str] = mapped_column(String(32), default="topic", nullable=False)
    source: Mapped[str] = mapped_column(String(16), default="auto", nullable=False)
    attrs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class QuestionTaxonomy(Base, TimestampMixin):
    __tablename__ = "question_taxonomy"
    __table_args__ = (UniqueConstraint("question_id", "node_id", name="uq_question_taxonomy"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("question.id"), nullable=False, index=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("taxonomy_node.id"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(16), default="auto", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    assigned_by: Mapped[Optional[str]] = mapped_column(String(64))
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Difficulty(Base, TimestampMixin):
    """难度：官方与系统估计分开存储。"""

    __tablename__ = "difficulty"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("question.id"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(16), default="estimated", nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    scale: Mapped[str] = mapped_column(String(32), default="0-1", nullable=False)
    features: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    model_version: Mapped[Optional[str]] = mapped_column(String(32))


class QuestionSimilarity(Base, TimestampMixin):
    __tablename__ = "question_similarity"
    __table_args__ = (
        UniqueConstraint("question_a_id", "question_b_id", "method", name="uq_similarity"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_a_id: Mapped[int] = mapped_column(ForeignKey("question.id"), nullable=False, index=True)
    question_b_id: Mapped[int] = mapped_column(ForeignKey("question.id"), nullable=False, index=True)
    method: Mapped[str] = mapped_column(String(32), default="hybrid", nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    features: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


# --------------------------------------------------------------------------
# 治理层
# --------------------------------------------------------------------------


class ParseRun(Base, TimestampMixin):
    """一次解析运行。派生数据可按 parse_run 重建或回滚。"""

    __tablename__ = "parse_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_revision_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("document_revision.id"), index=True
    )
    parser_version: Mapped[str] = mapped_column(String(32), nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="running", nullable=False)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    finished_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime)
    stats: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[Optional[str]] = mapped_column(Text)


class ProvenanceEdge(Base, TimestampMixin):
    """通用溯源边：任意主体指向来源。"""

    __tablename__ = "provenance_edge"
    __table_args__ = (Index("ix_provenance_subject", "subject_type", "subject_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_type: Mapped[str] = mapped_column(String(48), nullable=False)
    subject_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_kind: Mapped[str] = mapped_column(String(48), nullable=False)
    source_ref: Mapped[Optional[str]] = mapped_column(String(2048))
    source_url: Mapped[Optional[str]] = mapped_column(String(2048))
    run_id: Mapped[Optional[int]] = mapped_column(Integer)
    observed_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    attrs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ValidationFinding(Base, TimestampMixin):
    """校验发现的问题。"""

    __tablename__ = "validation_finding"
    __table_args__ = (
        Index("ix_finding_subject", "subject_type", "subject_id"),
        Index("ix_finding_rule", "rule_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_type: Mapped[str] = mapped_column(String(48), nullable=False)
    subject_id: Mapped[int] = mapped_column(Integer, nullable=False)
    rule_code: Mapped[str] = mapped_column(String(64), nullable=False)
    # info / warning / error / critical
    severity: Mapped[str] = mapped_column(String(16), default="warning", nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    parse_run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("parse_run.id"), index=True)
    # open / resolved / ignored
    status: Mapped[str] = mapped_column(String(16), default="open", nullable=False)


class ReviewTask(Base, TimestampMixin):
    """人工待检查队列。"""

    __tablename__ = "review_task"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    target_type: Mapped[str] = mapped_column(String(48), nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(128), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    # open / in_progress / done / dismissed
    status: Mapped[str] = mapped_column(String(16), default="open", nullable=False, index=True)
    # 产出这条待检查项的解析轮次。没有它就无法按考试局统计待检查量
    # （需经 parse_run -> document_revision -> document 归属），
    # 也无法判断一条待检查项是否已被新一轮解析取代。
    parse_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("parse_run.id"), index=True
    )
    assignee: Mapped[Optional[str]] = mapped_column(String(128))
    resolution: Mapped[Optional[str]] = mapped_column(Text)


class FieldOverride(Base, TimestampMixin):
    """人工修正，字段路径级，与派生数据分离。

    重新解析后按 applies_to_parser_versions 策略重新应用；若新解析值与
    source_value（被覆盖时的原值）不一致，则标记冲突并进入待检查，
    绝不静默覆盖。
    """

    __tablename__ = "field_override"
    __table_args__ = (
        UniqueConstraint("target_type", "target_id", "field_path", name="uq_override_field"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    target_type: Mapped[str] = mapped_column(String(48), nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
    field_path: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[Any] = mapped_column(JSON, nullable=False)
    # 修正时被覆盖的原值，用于冲突检测
    source_value: Mapped[Any] = mapped_column(JSON)
    author: Mapped[Optional[str]] = mapped_column(String(128))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # "*" 表示适用于所有解析器版本；否则为版本列表
    applies_to_parser_versions: Mapped[Any] = mapped_column(JSON, default=lambda: "*")
    conflict_detected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    conflict_detail: Mapped[Optional[str]] = mapped_column(Text)
    # 修正说明、撤销人、撤销时间等审计信息。不塞进 conflict_detail：
    # 冲突详情是给"为什么这条修正没生效"用的，审计信息是给"谁在什么时候改的"用的。
    attrs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Job(Base, TimestampMixin):
    """可重试工作项（含死信）。"""

    __tablename__ = "job"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # pending / running / done / failed / dead
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    run_after: Mapped[Optional[dt.datetime]] = mapped_column(DateTime, index=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    board_id: Mapped[Optional[int]] = mapped_column(ForeignKey("board.id"), index=True)
