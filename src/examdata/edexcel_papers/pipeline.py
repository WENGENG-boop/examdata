"""Edexcel IAL 试卷下载与切分。

下载：逐资源调用 ``SyncService.sync_resource``，不用 ``run()``——``run`` 会把
本轮没见到的候选标成 missing，而这里每科只同步一部分资源。文件名推导出的
paper code 回写到 ``Document.paper_code``；servlet 的 Unit 值（``Unit-1``）
留在 ``Document.attrs["board_specific"]`` 里。

切分：QP 用 ``index_questions(data, "qp")`` 建题号树；MS 按
(科目, 考季, 文件名 paper code) 配到 QP，再用 ``index_ms_questions`` 取每题的
评分区域 bbox（MS 是表格版式，通用 locator 抓不到合并题号，见该函数的说明），
合并进 ``Question.attrs["ms_regions"]``。只存原 PDF 与切分元数据，不渲染任何图片。

幂等：同一 revision 已切过就跳过；``force=True`` 只删本模块自己的派生数据
（其他来源的 Paper 一律跳过并记冲突），ParseRun 行保留作审计。
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable, Optional

import pymupdf
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..adapters.base import DiscoveredResource, SyllabusRef
from ..adapters.edexcel.adapter import EdexcelAdapter
from ..adapters.edexcel.classify import (
    DOC_MARK_SCHEME,
    DOC_QUESTION_PAPER,
    normalize_exam_series,
)
from ..core.config import Settings, get_settings
from ..core.db import is_locked_error, with_lock_retry
from ..core.fetch import FetchResult, Fetcher
from ..core.ids import identity_key
from ..core.models import (
    Artifact,
    ArtifactRevision,
    Difficulty,
    Document,
    DocumentRevision,
    ExamSeries,
    Formula,
    GeneratedExplanation,
    MarkScheme,
    MarkSchemeEntry,
    OfficialAnswer,
    Paper,
    ParseRun,
    Question,
    QuestionAsset,
    QuestionSimilarity,
    QuestionTaxonomy,
    Subject,
)
from ..core.storage import ContentAddressedStore
from ..paperqa.errors import LocationError
from ..paperqa.locator import decode_cipher_text, index_questions, is_ciphered
from ..sync.service import ResourceOutcome, SyncService

PARSER_VERSION = "edexcel-papers-1"

# 分值标记：整题用 "(Total for Question 3 = 6 marks)"，子题用结尾的 "(2)"。
_TOTAL_MARKER = re.compile(
    r"\(\s*Total for Question\s+(\d+)\s*=\s*(\d+)\s*marks?\s*\)", re.I
)
_TRAILING_MARKS = (
    re.compile(r"\(\s*(\d+)\s*marks?\s*\)\s*$", re.I),
    re.compile(r"\(\s*(\d+)\s*\)\s*$"),
    re.compile(r"\[\s*(\d+)\s*marks?\s*\]\s*$", re.I),
    re.compile(r"\[\s*(\d+)\s*\]\s*$"),
)
# 整行只有 "(2)" 的分值行；IAL 选择题把分值放在选项前、单独成行，结尾正则抓不到。
_MARK_LINE = re.compile(r"^[ \t]*\((\d+)\)[ \t]*$", re.M)

MAX_TEXT_CHARS = 20000


class PdfGuardFetcher(Fetcher):
    """把非 PDF 响应体降级成失败，避免把登录页/HTML 当试卷存下来。

    Pearson 对门禁文件可能返回 200 + HTML 登录页；这类响应体一旦落盘，
    后续切分会以 "PDF 打不开" 的形式失败，定位成本高。这里提前拦截。
    """

    def get(self, url: str, *, expect_binary: bool = False, **kwargs: Any) -> FetchResult:
        result = super().get(url, expect_binary=expect_binary, **kwargs)
        if (
            expect_binary
            and result.ok
            and result.content is not None
            and not result.content.startswith(b"%PDF-")
        ):
            return replace(
                result, status=0, error="non-PDF response body", content=None
            )
        return result


# -- 文件名 -> paper code ---------------------------------------------------


def derive_paper_code(url_or_path: str) -> tuple[Optional[str], Optional[str]]:
    """从文件名推导 (paper_code, unit_code)。

    ``wbi11-01-que-20240508.pdf`` -> ``("wbi11-01", "WBI11")``；
    ``WBI11_01_msc_20190307.pdf`` -> ``("wbi11-01", "WBI11")``；
    ``wbi11-01a-rms-20260305.pdf`` -> ``("wbi11-01a", "WBI11")``；
    ``ial-wbi11-01-oct19.pdf`` -> ``("wbi11-01", "WBI11")``。

    ``ial-`` 是 International A Level 家族前缀，不属于 paper code 本身。

    不能用 servlet 的 Unit 值当 paper code：那是 ``Unit-1`` 这类枚举名，
    同一 unit 的 QP 与 MS 会撞在一起。
    """
    name = url_or_path.rsplit("/", 1)[-1].split("?", 1)[0]
    if "." in name:
        name = name.rsplit(".", 1)[0]
    parts = re.split(r"[-_]", name)
    if len(parts) >= 3 and parts[0].lower() == "ial":
        parts = parts[1:]
    if len(parts) < 2 or not parts[0] or not parts[1]:
        return None, None
    return f"{parts[0].lower()}-{parts[1].lower()}", parts[0].upper()


# -- 分值解析 ---------------------------------------------------------------


def parse_question_marks(text: str, number_path: str) -> Optional[int]:
    """从区域文本里抽分值。

    顶层题（``1``）只有整题合计行 ``(Total for Question 1 = 6 marks)``；
    子题（``1(a)``）用结尾的 ``(2)`` / ``(2 marks)`` / ``[2 marks]``。
    先剥掉整题合计行，否则子题会把父题总分误当自己的分值。
    """
    if not text:
        return None
    body = text.strip()
    if "(" not in number_path:
        head = number_path.strip()
        for match in _TOTAL_MARKER.finditer(body):
            if match.group(1) == head:
                return int(match.group(2))
        return None
    stripped = _TOTAL_MARKER.sub(" ", body).rstrip()
    for pattern in _TRAILING_MARKS:
        match = pattern.search(stripped)
        if match:
            return int(match.group(1))
    return None


def _standalone_mark(text: str) -> Optional[int]:
    """取区域文本里第一行整行形如 ``(2)`` 的分值行。

    只对叶子节点使用：分值行紧跟题干、位于作答区之前；区域串入的
    后续题 ``(N)`` 行不会先出现，所以取第一行。
    """
    if not text:
        return None
    stripped = _TOTAL_MARKER.sub(" ", text)
    match = _MARK_LINE.search(stripped)
    return int(match.group(1)) if match else None


def _total_marks_from_pages(
    pdf: pymupdf.Document,
    regions: Iterable[dict[str, Any]],
    number_path: str,
    page_text: Optional[dict[int, str]] = None,
    ciphered: bool = False,
) -> Optional[int]:
    """区域文本没抓到合计行时，退到整页文本里找。

    合计行 ``(Total for Question 1 = 6 marks)`` 有时落在 locator 区域
    底边下方几 pt、甚至区域页之外，区域文本因此漏掉；先查区域页（从后
    往前），再兜底全 PDF 扫描。``page_text`` 缓存页文本，按卷复用。
    """
    pattern = re.compile(
        r"\(\s*Total for Question\s+"
        + re.escape(number_path)
        + r"\s*=\s*(\d+)\s*marks?\s*\)",
        re.I,
    )

    def text_of(page_no: int) -> Optional[str]:
        if page_text is not None and page_no in page_text:
            return page_text[page_no]
        try:
            page = pdf[page_no - 1]
        except (IndexError, ValueError):
            return None
        value = page.get_text()
        if ciphered:
            value = decode_cipher_text(value)
        if page_text is not None:
            page_text[page_no] = value
        return value

    region_pages: list[int] = []
    for region in regions or []:
        page_no = region.get("page")
        if page_no is not None and page_no not in region_pages:
            region_pages.append(page_no)
    for page_no in reversed(region_pages):
        text = text_of(page_no)
        if text:
            match = pattern.search(text)
            if match:
                return int(match.group(1))
    for page_no in range(1, len(pdf) + 1):
        if page_no in region_pages:
            continue
        text = text_of(page_no)
        if text:
            match = pattern.search(text)
            if match:
                return int(match.group(1))
    return None


def _question_marks(
    pdf: pymupdf.Document,
    nodes: list[dict[str, Any]],
    texts: dict[str, str],
    ciphered: bool = False,
) -> dict[str, Optional[int]]:
    """逐题定分值：区域解析 → 叶子独立行 → 整页合计行。"""
    has_child = {node["parent_path"] for node in nodes if node["parent_path"]}
    page_text: dict[int, str] = {}
    marks: dict[str, Optional[int]] = {}
    for node in nodes:
        path = node["number_path"]
        text = texts.get(path, "")
        value = parse_question_marks(text, path)
        if value is None and "(" in path and path not in has_child:
            value = _standalone_mark(text)
        if value is None:
            value = _total_marks_from_pages(pdf, node["regions"], path, page_text, ciphered)
        marks[path] = value
    return marks


# -- 题号树 -----------------------------------------------------------------


def split_path(number_path: str) -> tuple[str, Optional[str]]:
    """``1(a)(ii)`` -> ``("1(a)", "(ii)")``；顶层 ``1`` -> ``("1", None)``。"""
    index = number_path.rfind("(")
    if index <= 0:
        return number_path, None
    return number_path[:index], number_path[index:]


def kind_for_depth(depth: int) -> str:
    if depth <= 0:
        return "question"
    return "sub" if depth == 1 else "part"


def build_question_tree(index: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把 ``index_questions`` 的输出补全成父子关系（顺序保持不变）。"""
    nodes: list[dict[str, Any]] = []
    for item in index:
        path = item.get("question")
        if not path:
            continue
        parent, label = split_path(path)
        nodes.append(
            {
                "number_path": path,
                "number_label": label or path,
                "parent_path": parent if label else None,
                "depth": path.count("("),
                "kind": kind_for_depth(path.count("(")),
                "regions": item.get("regions") or [],
            }
        )
    return nodes


def _region_text(pdf: pymupdf.Document, regions: Iterable[dict[str, Any]], *, ciphered: bool = False) -> str:
    parts: list[str] = []
    for region in regions or []:
        page_no = region.get("page")
        bbox = region.get("bbox")
        if page_no is None or not bbox:
            continue
        try:
            page = pdf[page_no - 1]
        except (IndexError, ValueError):
            continue
        text = page.get_text(clip=pymupdf.Rect(bbox))
        if ciphered:
            text = decode_cipher_text(text)
        if text and text.strip():
            parts.append(text)
    return "\n".join(parts).strip()[:MAX_TEXT_CHARS]


# -- 身份与同步 -------------------------------------------------------------


def document_identity(
    adapter: EdexcelAdapter, ref: SyllabusRef, res: DiscoveredResource
) -> str:
    """镜像 ``SyncService._document_identity``。

    下载前要判断"这份文件是否已经落过盘"，而 SyncService 不暴露身份计算，
    只能按同样的字段重算一份。改 SyncService 的身份公式时必须同步这里。
    """
    meta = adapter.normalize_metadata(res)
    return identity_key(
        adapter.key,
        ref.qualification_key,
        ref.code,
        meta.get("year"),
        meta.get("series"),
        meta.get("paper_code"),
        meta.get("doc_type") or res.doc_type,
    )


@dataclass
class SyncSummary:
    total: int = 0
    created: int = 0
    revision: int = 0
    unchanged: int = 0
    skipped: int = 0
    gated: int = 0
    failed: int = 0
    robots: int = 0
    errors: list[str] = field(default_factory=list)


def _needs_download(
    session: Session,
    adapter: EdexcelAdapter,
    ref: SyllabusRef,
    res: DiscoveredResource,
    *,
    refresh: bool,
) -> bool:
    """这份 URL 的文件是否还需要下载。

    同一个身份键可能对应多份文件（实测 June-2021 每个 unit 同时有
    ``_msc_`` 与 ``_rms_`` 两份 mark scheme），所以"文档有 current_revision
    就跳过"是错的：后一份永远不会被下载。判定改为"这份 URL 的文件是否已经
    作为该文档的某个 revision 落过盘"。
    """
    if refresh:
        return True
    idkey = document_identity(adapter, ref, res)
    doc = session.scalar(select(Document).where(Document.identity_key == idkey))
    if doc is None or doc.current_revision_id is None:
        return True
    artifact_ids = set(
        session.scalars(
            select(DocumentRevision.artifact_id).where(
                DocumentRevision.document_id == doc.id
            )
        ).all()
    )
    artifact_ids.discard(None)
    if not artifact_ids:
        return True
    hit = session.scalar(
        select(ArtifactRevision.id)
        .where(
            ArtifactRevision.url == res.url,
            ArtifactRevision.artifact_id.in_(artifact_ids),
        )
        .limit(1)
    )
    return hit is None


def sync_resources(
    session: Session,
    settings: Settings,
    ref: SyllabusRef,
    resources: Iterable[DiscoveredResource],
    *,
    fetcher: Optional[Fetcher] = None,
    download: bool = True,
    refresh: bool = False,
) -> SyncSummary:
    """逐个资源同步。失败只记账，不中断整批。"""
    items = list(resources)
    summary = SyncSummary(total=len(items))
    guard = fetcher or PdfGuardFetcher(settings)
    owns_fetcher = fetcher is None
    store = ContentAddressedStore(settings.artifacts_dir)
    adapter = EdexcelAdapter(guard)
    try:
        for res in items:
            def _sync_one() -> ResourceOutcome:
                want = download and _needs_download(
                    session, adapter, ref, res, refresh=refresh
                )
                service = SyncService(
                    session, adapter, settings=settings, store=store, fetcher=guard
                )
                outcome = service.sync_resource(ref, res, download=want)
                session.commit()
                return outcome

            try:
                outcome = with_lock_retry(session, _sync_one)
            except Exception as exc:  # 单个资源失败不拖垮整批
                session.rollback()
                summary.failed += 1
                summary.errors.append(f"{res.url}: {exc}")
                continue

            action = outcome.action
            if action == "created":
                summary.created += 1
            elif action == "revision":
                summary.revision += 1
            elif action == "unchanged":
                summary.unchanged += 1
            elif action == "skipped":
                summary.skipped += 1
            elif action == "gated":
                summary.gated += 1
            elif action == "robots":
                summary.robots += 1
                summary.errors.append(f"{res.url}: robots.txt 禁止抓取")
            elif action == "failed":
                summary.failed += 1
                summary.errors.append(f"{res.url}: {outcome.detail or 'download failed'}")

            if action in {"created", "revision", "unchanged"} and outcome.document_id:
                try:
                    with_lock_retry(
                        session,
                        lambda: (
                            _update_paper_code(session, outcome.document_id, res),
                            session.commit(),
                        ),
                    )
                except Exception as exc:
                    session.rollback()
                    summary.errors.append(f"{res.url}: paper_code 更新失败 {exc}")
    finally:
        if owns_fetcher:
            guard.close()
    return summary


def _update_paper_code(session: Session, document_id: int, res: DiscoveredResource) -> None:
    """把 Document.paper_code 换成文件名推导的 code（servlet 的 Unit 值不可用）。"""
    code, _unit = derive_paper_code(res.url)
    if not code:
        return
    doc = session.get(Document, document_id)
    if doc is None:
        return
    doc.paper_code = code[:32]


# -- 切分 -------------------------------------------------------------------


@dataclass
class SplitSummary:
    papers: int = 0
    questions: int = 0
    mark_schemes: int = 0
    ms_entries: int = 0
    ms_matched: int = 0
    ms_unmatched: int = 0
    skipped: int = 0
    conflicts: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


def _now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def _subject(session: Session, slug: str) -> Optional[Subject]:
    return session.scalar(select(Subject).where(Subject.code == slug))


def _series_ids(session: Session, series: str) -> list[int]:
    text = (normalize_exam_series(series) or series).strip().lower()
    match = re.match(r"^([a-z]+)\s+(\d{4})$", text)
    if match:
        month, year = match.group(1), int(match.group(2))
        rows = session.scalars(
            select(ExamSeries.id).where(
                ExamSeries.year == year,
                func.lower(ExamSeries.session).contains(month),
            )
        ).all()
    else:
        rows = session.scalars(
            select(ExamSeries.id).where(func.lower(ExamSeries.session) == text)
        ).all()
    return list(rows)


def _documents(
    session: Session,
    subject_id: int,
    doc_type: str,
    series_ids: Optional[list[int]],
    limit: Optional[int],
) -> list[Document]:
    stmt = (
        select(Document)
        .where(
            Document.subject_id == subject_id,
            Document.doc_type == doc_type,
            Document.current_revision_id.isnot(None),
        )
        .order_by(Document.id)
    )
    if series_ids is not None:
        stmt = stmt.where(Document.series_id.in_(series_ids))
    docs = list(session.scalars(stmt))
    if limit is not None and limit > 0:
        docs = docs[:limit]
    return docs


def _paper_code_of(doc: Document, revision: Optional[DocumentRevision]) -> Optional[str]:
    if revision is not None and revision.source_url:
        code, _unit = derive_paper_code(revision.source_url)
        if code:
            return code
    code = (doc.paper_code or "").strip().lower()
    return code or None


_UNIT_TOKEN = re.compile(r"\b([A-Z]{2,4}\d{2})\b")


def _norm_paper_code(code: Optional[str]) -> str:
    """归一化 paper code：去掉版本尾字母或 rms/msc 尾段。

    ``wch13-01r`` -> ``wch13-01``；``wch15-01a`` -> ``wch15-01``；
    ``wbi11-01a-rms`` -> ``wbi11-01``；``wph15-rms`` -> ``wph15``；
    ``Unit-2`` -> ``unit-2``。
    """
    parts = [p for p in re.split(r"[-_]", (code or "").strip().lower()) if p]
    if parts and parts[-1] in {"rms", "msc"}:
        parts = parts[:-1]
    if parts and parts[-1][-1:].isalpha() and any(ch.isdigit() for ch in parts[-1]):
        parts[-1] = parts[-1].rstrip("abcdefghijklmnopqrstuvwxyz")
    return "-".join(parts)


def _paper_families(code: Optional[str], title: Optional[str]) -> set[str]:
    """单元家族集合：code 首段 + title 里的单元号（``WMA11`` 之类）。

    math 的 MS 有时把单元号写进 title 而 code 取自文件名里的另一单元号，
    QP 侧相反；两侧各取两个来源再求交，才不至于把 ``wma11`` 与 ``wdm11``
    这类互换的卷配错。
    """
    families: set[str] = set()
    if code:
        head = re.split(r"[-_]", code.strip().lower(), maxsplit=1)[0]
        if re.fullmatch(r"[a-z]{2,4}\d{2}", head):
            families.add(head)
    if title:
        for match in _UNIT_TOKEN.findall(title.upper()):
            families.add(match.lower())
    return families


def _lookup_qp(
    qp_index: dict[tuple[int, Optional[int], str], Document],
    doc: Document,
    paper_code: Optional[str],
) -> tuple[Optional[Document], float, Optional[str]]:
    """在 ``qp_index`` 里找 MS 对应的 QP：精确 → code 归一化 → 单元家族。

    返回 ``(qp_doc, confidence, method)``；不唯一或无命中时
    ``(None, 0.0, None)``。
    """
    if paper_code:
        exact = qp_index.get((doc.subject_id, doc.series_id, paper_code))
        if exact is not None:
            return exact, 1.0, "filename+series"
    same_series = [
        (code, qp_doc)
        for (subject_id, series_id, code), qp_doc in qp_index.items()
        if subject_id == doc.subject_id and series_id == doc.series_id
    ]
    if not same_series:
        return None, 0.0, None
    if paper_code:
        normalized = _norm_paper_code(paper_code)
        if normalized:
            hits = [
                qp_doc
                for code, qp_doc in same_series
                if _norm_paper_code(code) == normalized
            ]
            if len(hits) == 1:
                return hits[0], 0.85, "code-normalized"
    families = _paper_families(paper_code, doc.title)
    if families:
        hits = [
            qp_doc
            for code, qp_doc in same_series
            if families & _paper_families(code, qp_doc.title)
        ]
        if len(hits) == 1:
            return hits[0], 0.6, "unit-family"
    return None, 0.0, None


def _artifact_path(
    session: Session, settings: Settings, artifact_id: Optional[int]
) -> Optional[Path]:
    if artifact_id is None:
        return None
    artifact = session.get(Artifact, artifact_id)
    if artifact is None or not artifact.storage_key:
        return None
    path = ContentAddressedStore(settings.artifacts_dir).path_for_key(artifact.storage_key)
    return path if path.exists() else None


def _own_run(session: Session, parse_run_id: Optional[int]) -> Optional[ParseRun]:
    if not parse_run_id:
        return None
    run = session.get(ParseRun, parse_run_id)
    if run is None or run.parser_version != PARSER_VERSION:
        return None
    return run


def _delete_question_data(session: Session, paper: Paper) -> None:
    """删掉本模块给这本 Paper 建的题、子表行与 MS 关联（自底向上，满足外键约束）。"""
    question_ids = list(
        session.scalars(select(Question.id).where(Question.paper_id == paper.id))
    )
    if question_ids:
        for model in (
            QuestionTaxonomy,
            QuestionAsset,
            Formula,
            MarkSchemeEntry,
            OfficialAnswer,
            GeneratedExplanation,
            Difficulty,
        ):
            session.execute(
                delete(model).where(model.question_id.in_(question_ids))
            )
        session.execute(
            delete(QuestionSimilarity).where(
                QuestionSimilarity.question_a_id.in_(question_ids)
                | QuestionSimilarity.question_b_id.in_(question_ids)
            )
        )
    depths = list(
        session.scalars(select(Question.depth).where(Question.paper_id == paper.id).distinct())
    )
    for depth in sorted(depths, reverse=True):
        session.execute(
            delete(Question).where(Question.paper_id == paper.id, Question.depth == depth)
        )


def _delete_mark_scheme(session: Session, mark_scheme: MarkScheme) -> None:
    session.execute(
        delete(MarkSchemeEntry).where(MarkSchemeEntry.mark_scheme_id == mark_scheme.id)
    )
    session.delete(mark_scheme)


def _delete_paper_data(session: Session, doc: Document, paper: Paper) -> None:
    """只删本模块的派生数据；调用方已确认 Paper 属于本模块。"""
    question_ids = list(
        session.scalars(select(Question.id).where(Question.paper_id == paper.id))
    )
    if question_ids:
        session.execute(
            delete(MarkSchemeEntry).where(MarkSchemeEntry.question_id.in_(question_ids))
        )
    for mark_scheme in session.scalars(
        select(MarkScheme).where(MarkScheme.matched_paper_document_id == doc.id)
    ):
        if _own_run(session, mark_scheme.parse_run_id) is not None:
            _delete_mark_scheme(session, mark_scheme)
    _delete_question_data(session, paper)
    session.delete(paper)


def _record_failed_run(
    session: Session, revision_id: int, *, params: dict[str, Any], message: str
) -> None:
    """解析失败要留下痕迹：新事务写 ParseRun(failed) + revision.parse_status。"""
    try:
        session.rollback()
        now = _now()
        session.add(
            ParseRun(
                document_revision_id=revision_id,
                parser_version=PARSER_VERSION,
                params=params,
                status="failed",
                started_at=now,
                finished_at=now,
                stats={},
                error=message[:2000],
            )
        )
        revision = session.get(DocumentRevision, revision_id)
        if revision is not None:
            revision.parse_status = "failed"
            revision.parse_error = message[:2000]
        session.commit()
    except Exception:
        session.rollback()


def _questions_for_doc(
    session: Session, document_id: int, cache: dict[int, dict[str, Question]]
) -> dict[str, Question]:
    if document_id in cache:
        return cache[document_id]
    out: dict[str, Question] = {}
    paper = session.scalar(select(Paper).where(Paper.document_id == document_id))
    if paper is not None:
        for question in session.scalars(select(Question).where(Question.paper_id == paper.id)):
            out[question.number_path] = question
    cache[document_id] = out
    return out


def _merge_ms_regions(question: Question, regions: Iterable[dict[str, Any]], sha256: str) -> None:
    attrs = dict(question.attrs or {})
    merged = [
        region
        for region in (attrs.get("ms_regions") or [])
        if isinstance(region, dict) and region.get("sha256") != sha256
    ]
    for region in regions or []:
        page_no = region.get("page")
        bbox = region.get("bbox")
        if page_no is None or not bbox:
            continue
        merged.append({"page": page_no, "bbox": list(bbox), "sha256": sha256})
    attrs["ms_regions"] = merged
    question.attrs = attrs


def _strip_ms_regions(session: Session, paper_document_id: int, shas: set[str]) -> None:
    """重切 MS 前先摘掉旧 MS 文件留下的区域，避免与新区域并存。"""
    if not shas:
        return
    paper = session.scalar(select(Paper).where(Paper.document_id == paper_document_id))
    if paper is None:
        return
    for question in session.scalars(select(Question).where(Question.paper_id == paper.id)):
        attrs = dict(question.attrs or {})
        kept = [
            region
            for region in (attrs.get("ms_regions") or [])
            if not (isinstance(region, dict) and region.get("sha256") in shas)
        ]
        if len(kept) != len(attrs.get("ms_regions") or []):
            attrs["ms_regions"] = kept
            question.attrs = attrs


def _ms_source_shas(session: Session, document_id: int) -> set[str]:
    rows = session.execute(
        select(Artifact.sha256)
        .join(DocumentRevision, DocumentRevision.artifact_id == Artifact.id)
        .where(DocumentRevision.document_id == document_id)
    ).all()
    return {row[0] for row in rows if row[0]}


def _existing_papers(session: Session, document_id: int) -> list[Paper]:
    return list(session.scalars(select(Paper).where(Paper.document_id == document_id)))


# -- Mark Scheme 题号索引 ---------------------------------------------------

# IAL 的 MS 是横向表格页，题号是左栏的**合并** token（"1(a)(i)"），实测
# x0 落在页宽 3%~13%；`paperqa.locator` 的启发式只认"大题号 + 独立 (a)"
# 两段式（Edexcel QP 版式），在 MS 上只会在 "Level 1 / 1-2" 这类说明表里
# 给出假锚点，所以这里按表格行再扫一遍，取与 QP 题号吻合更多的一侧。
_MS_NUMBER = re.compile(r"^[1-9]\d{0,2}(?:\([a-z]{1,4}\))*$")
_MS_MAIN = re.compile(r"^[1-9]\d{0,2}$")
_MS_PART = re.compile(r"^(?:\([a-z]{1,4}\))+$")
# rms 变体的紧凑题号 "1bii"；字符类收紧到题目实际会用到的段号与罗马
# 数字，避免把 "1st"/"2nd"/"3rd"、"150o" 这类正文 token 误当题号。
_MS_COMPACT = re.compile(r"^[1-9]\d{0,2}[a-jivx]{1,10}$")
_MS_ROMAN = re.compile(r"i{1,3}|iv|v|vi{1,3}|ix|x")
_MS_LEAD = re.compile(r"^[^\w(]*")
_MS_NUMBER_X = 0.20  # 题号列右界（页宽比例）
_MS_RULE_GAP = 6.0  # 裸数字题号与表格横线的最大间距
_MS_MERGE_GAP = 12.0  # 紧凑题号与罗马数字尾段（"3d"+"ii"）的最大间距
_MS_PART_GAP = 20.0  # 主号/分段词与相邻分段词的最大间距
_MS_BARE_MARGIN = 10.0  # 裸数字题号相对校准列右界的最大容差
_MS_COL_MIN = 5  # 列匹配例外：该 x 处全文档带括号题号 token 数达到此值则不门控
_MS_COL_TOL = 3.0  # 列匹配例外：与带括号题号列的 x 容差


def _ms_rules(
    page: pymupdf.Page, bounds: pymupdf.Rect, rotation: pymupdf.Matrix
) -> list[float]:
    """表格横线的 y（只取跨列的长横线，用于切行），坐标归一到可见页。"""
    rules: set[float] = set()
    for drawing in page.get_drawings():
        rect = pymupdf.Rect(drawing["rect"]) * rotation
        if rect.height < 1.5 and rect.width > bounds.width * 0.4:
            rules.add(round(rect.y0, 1))
    return sorted(rules)


def _normalize_ms_token(text: str) -> str:
    """MS 题号 token 归一：去前导装饰、尾点（"1."）与 "." 后分段（"1.(a)"）。"""
    token = _MS_LEAD.sub("", text)
    if token.endswith(".") and _MS_NUMBER.match(token[:-1]):
        token = token[:-1]
    return re.sub(r"^([1-9]\d{0,2})\.(?=\()", r"\1", token)


def _ms_notes_question(words: list[tuple]) -> str | None:
    """识别 "Notes for question N" 段落头并返回 N，用于延续题号上下文。"""
    texts = [text.strip().lower() for _rect, text in words]
    if "notes" not in texts[:5]:
        return None
    try:
        position = texts.index("question", 0, 8)
    except ValueError:
        return None
    for _rect, text in words[position + 1 : position + 3]:
        token = _normalize_ms_token(text)
        if _MS_MAIN.match(token):
            return token
    return None


def _ms_extend(base: str | None, token: str, accepted) -> str | None:
    """把独立分段 token（"(a)"/"(i)"）挂到 base 下：逐级回溯祖先。

    base="7(c)(i)" + "(ii)" -> "7(c)(ii)"；base="7(c)" + "(b)" -> "7(b)"。
    """
    path = base
    while path:
        candidate = path + token
        if accepted(candidate):
            return candidate
        head, sep, _tail = path.rpartition("(")
        if not sep:
            return None
        path = head
    return None


def _ms_anchors(
    pdf: pymupdf.Document, wanted: set[str] | None = None
) -> list[tuple[int, str, tuple]]:
    """扫出 MS 表格左栏的题号锚点：``(页序, 题号, 词框)``。

    只认每行最靠左的两个词；裸数字（"7"）必须紧贴表格横线下方才算题号，
    否则会把答案里 Level 表、数据表的行首数字当成题号；同行前缀出现
    "Level" 的行直接跳过。页面按 /Rotate 归一到可见坐标系（词框随之
    变换）。

    版式变体：math 的 MS 题号带尾点（"1."、"1.(a)"）；分段（"(a)"/"(i)"）
    可能单独成行，按 "Notes for question N" 段落头或上一条题号维护的
    base 回溯祖先补全（"7(c)" + "(ii)" -> "7(c)(ii)"）；紧凑题号（"1bii"，
    部分 rms 版式）可与同行的罗马数字尾段（"3d"+"ii"）合并；给了
    ``wanted`` 时按去括号映射决定是否合并。
    """
    anchors: list[tuple[int, str, tuple]] = []
    compact_map: dict[str, str] | None = None
    if wanted is not None:
        compact_map = {
            path.replace("(", "").replace(")", ""): path for path in wanted if path
        }

    def accepted(candidate: str) -> bool:
        if compact_map is None:
            return bool(
                _MS_NUMBER.match(candidate) or _MS_COMPACT.fullmatch(candidate)
            )
        return (
            candidate in compact_map
            or candidate.replace("(", "").replace(")", "") in compact_map
        )

    # 预扫标定：带字母的题号 token（"1(a)"、"1bii"、"(a)"）是可靠的题号列
    # 样本，取其每页最大 x0 作右界；裸数字题号超过右界 + 容差即视为正文数字
    # （数据值、公式、"1 mark"、"Aspect 1" 等），不再当锚点。页面无带字母
    # 题号（如纯 MCQ 答案页）则不设右界，不做门控。带括号题号 token 的 x0
    # 另存为全文档候选列：题号列偶与页校准列不同（分节混排页），该 x 处
    # 带括号题号足够多时例外放行（见下方门控）。
    page_calib: dict[int, float] = {}
    paren_cols: list[float] = []
    for index, page in enumerate(pdf):
        if index == 0:
            continue
        bounds = page.rect
        rotation = page.rotation_matrix
        for word in page.get_text("words"):
            rect = pymupdf.Rect(word[:4]) * rotation
            if not bounds.height * 0.04 < rect.y0 < bounds.height * 0.9:
                continue
            if rect.x0 >= bounds.width * _MS_NUMBER_X:
                continue
            token = _normalize_ms_token(word[4])
            if not any(ch.isalpha() for ch in token):
                continue
            if not (
                _MS_NUMBER.match(token)
                or _MS_COMPACT.fullmatch(token)
                or _MS_PART.fullmatch(token)
            ):
                continue
            if "(" in token and (
                _MS_NUMBER.match(token) or _MS_PART.fullmatch(token)
            ):
                paren_cols.append(rect.x0)
            if index not in page_calib or rect.x0 > page_calib[index]:
                page_calib[index] = rect.x0

    for index, page in enumerate(pdf):
        if index == 0:
            continue
        bounds = page.rect
        rotation = page.rotation_matrix
        rules = _ms_rules(page, bounds, rotation)
        threshold = page_calib.get(index)
        lines: dict[int, list] = {}
        for word in page.get_text("words"):
            rect = pymupdf.Rect(word[:4]) * rotation
            if not bounds.height * 0.04 < rect.y0 < bounds.height * 0.9:
                continue
            lines.setdefault(round(rect.y0 / 3), []).append((rect, word[4]))
        base: str | None = None
        for key in sorted(lines):
            words = sorted(lines[key], key=lambda item: item[0].x0)
            notes = _ms_notes_question(words)
            if notes is not None:
                base = notes
                continue
            for position, (head, text) in enumerate(words[:2]):
                if head.x0 >= bounds.width * _MS_NUMBER_X:
                    break
                token = _normalize_ms_token(text)
                rect = head
                if position == 0 and _MS_PART.fullmatch(token):
                    # 独立分段行（"(a)"、"(c)(i)"）：挂到当前 base 下。
                    if len(words) > 1:
                        nrect, ntext = words[1]
                        ntoken = _normalize_ms_token(ntext)
                        if (
                            _MS_PART.fullmatch(ntoken)
                            and nrect.x0 - head.x1 < _MS_PART_GAP
                        ):
                            token = token + ntoken
                            rect = pymupdf.Rect(
                                head.x0,
                                min(head.y0, nrect.y0),
                                nrect.x1,
                                max(head.y1, nrect.y1),
                            )
                    candidate = _ms_extend(base, token, accepted)
                    if candidate is not None:
                        anchors.append(
                            (index, candidate, (rect.x0, rect.y0, rect.x1, rect.y1))
                        )
                        base = candidate
                        break
                    continue
                if not (_MS_NUMBER.match(token) or _MS_COMPACT.fullmatch(token)):
                    continue
                if any(
                    word_text.strip().lower() == "level"
                    for _, word_text in words[:position]
                ):
                    break
                if (
                    _MS_MAIN.fullmatch(token)
                    and threshold is not None
                    and rect.x0 > threshold + _MS_BARE_MARGIN
                    and sum(
                        1 for col in paren_cols if abs(col - rect.x0) <= _MS_COL_TOL
                    )
                    < _MS_COL_MIN
                ):
                    # 超出校准右界的裸数字是正文数字：拒绝，也不参与随后的合并；
                    # 例外：该 x 处全文档带括号题号 token ≥ _MS_COL_MIN（题号列
                    # 与页校准列不同的分节混排页），仍视为题号。
                    break
                if _MS_MAIN.match(token) and position + 1 < len(words):
                    # "2." + "(a)" 同行：主号与分段合并成完整题号。
                    nrect, ntext = words[position + 1]
                    ntoken = _normalize_ms_token(ntext)
                    if (
                        _MS_PART.fullmatch(ntoken)
                        and nrect.x0 - head.x1 < _MS_PART_GAP
                    ):
                        candidate = token + ntoken
                        if accepted(candidate) or not accepted(token):
                            token = candidate
                            rect = pymupdf.Rect(
                                head.x0,
                                min(head.y0, nrect.y0),
                                nrect.x1,
                                max(head.y1, nrect.y1),
                            )
                elif _MS_COMPACT.fullmatch(token) and position + 1 < len(words):
                    nrect, ntext = words[position + 1]
                    if (
                        _MS_ROMAN.fullmatch(ntext)
                        and nrect.x0 - head.x1 < _MS_MERGE_GAP
                    ):
                        candidate = token + ntext
                        if _MS_COMPACT.fullmatch(candidate) and (
                            accepted(candidate) or not accepted(token)
                        ):
                            token = candidate
                            rect = pymupdf.Rect(
                                head.x0,
                                min(head.y0, nrect.y0),
                                nrect.x1,
                                max(head.y1, nrect.y1),
                            )
                if any(ch.isalpha() for ch in token) or any(
                    0 <= rect.y0 - y <= _MS_RULE_GAP for y in rules
                ):
                    anchors.append(
                        (index, token, (rect.x0, rect.y0, rect.x1, rect.y1))
                    )
                    base = token
                    if compact_map is not None:
                        base = compact_map.get(
                            token.replace("(", "").replace(")", ""), token
                        )
                break
    return anchors


def _ms_index_from_locator(data: bytes, wanted: set[str]) -> list[dict[str, Any]]:
    try:
        items = index_questions(data, "ms")
    except LocationError:
        return []
    return [
        {"question": item["question"], "regions": [dict(r) for r in item["regions"]]}
        for item in items
        if item.get("question") in wanted and item.get("regions")
    ]


def _ms_index_from_table(
    pdf: pymupdf.Document, anchors: list[tuple[int, str, tuple]], wanted: set[str]
) -> list[dict[str, Any]]:
    """每行区域 = 题号词框 ∪ 题号到下一行边界（横线或下一个题号）之间的词。

    锚点与区域在可见坐标系（/Rotate 归一）计算；落库前把 bbox 转回未旋转
    用户空间，与 ``paperqa.locator`` 的分析坐标系一致。紧凑题号按去括号
    映射回 QP 路径（"1bii" → "1(b)(ii)"）。
    """
    compact = {path.replace("(", "").replace(")", ""): path for path in wanted}
    layout: dict[int, tuple[pymupdf.Rect, list[float], pymupdf.Matrix]] = {}
    regions: dict[str, list[dict[str, Any]]] = {}
    for index, number, head in anchors:
        path = number if number in wanted else compact.get(number)
        if path is None:
            continue
        page = pdf[index]
        if index not in layout:
            bounds = page.rect
            layout[index] = (
                bounds,
                _ms_rules(page, bounds, page.rotation_matrix),
                page.rotation_matrix,
            )
        bounds, rules, rotation = layout[index]
        edges = [y for y in rules if y > head[1] + 4]
        edges += [
            other[2][1]
            for other in anchors
            if other[0] == index and other[2][1] > head[1] + 4
        ]
        bottom = min(edges) if edges else bounds.height * 0.94
        boxes = [head[:4]]
        for word in page.get_text("words"):
            rect = pymupdf.Rect(word[:4]) * rotation
            if (
                head[1] - 3 <= (rect.y0 + rect.y1) / 2 <= bottom
                and rect.x1 > bounds.width * 0.03
            ):
                boxes.append((rect.x0, rect.y0, rect.x1, rect.y1))
        x0 = max(0.0, min(box[0] for box in boxes) - 3)
        y0 = max(0.0, min(box[1] for box in boxes) - 3)
        x1 = min(bounds.width, max(box[2] for box in boxes) + 3)
        y1 = min(bounds.height, max(box[3] for box in boxes) + 3)
        bbox = pymupdf.Rect(x0, y0, x1, y1) * page.derotation_matrix
        regions.setdefault(path, []).append(
            {
                "page": index + 1,
                "bbox": [
                    round(bbox.x0, 1),
                    round(bbox.y0, 1),
                    round(bbox.x1, 1),
                    round(bbox.y1, 1),
                ],
            }
        )
    return [{"question": path, "regions": rows} for path, rows in regions.items()]


def index_ms_questions(
    data: bytes, qp_paths: Iterable[str]
) -> tuple[list[dict[str, Any]], str]:
    """按 QP 题号索引 MS 区域，返回 ``(index, source)``。

    ``index`` 与 ``paperqa.locator.index_questions`` 同形（只保留能对上
    QP 题号的项）；``source`` ∈ {"table", "locator"}，取吻合题号更多的一侧。
    """
    wanted = {path for path in qp_paths if path}
    if not wanted:
        return [], "locator"
    stock = _ms_index_from_locator(data, wanted)
    with pymupdf.open(stream=data, filetype="pdf") as pdf:
        table = _ms_index_from_table(pdf, _ms_anchors(pdf, wanted), wanted)
    if len(table) >= len(stock):
        return table, "table"
    return stock, "locator"


def _split_qp(
    session: Session,
    settings: Settings,
    doc: Document,
    summary: SplitSummary,
    *,
    force: bool,
    slug: str,
) -> None:
    revision = session.get(DocumentRevision, doc.current_revision_id)
    if revision is None or revision.artifact_id is None:
        summary.skipped += 1
        return

    papers = _existing_papers(session, doc.id)
    foreign = [p for p in papers if _own_run(session, p.parse_run_id) is None]
    if foreign:
        summary.conflicts += 1
        summary.errors.append(
            f"document {doc.id}: paper from another parser; skipped (no changes)"
        )
        return
    if papers and not force:
        current = [
            p
            for p in papers
            if (run := _own_run(session, p.parse_run_id)) is not None
            and run.document_revision_id == doc.current_revision_id
        ]
        if current:
            summary.skipped += 1
            return
    for paper in papers:
        _delete_paper_data(session, doc, paper)
    session.flush()

    path = _artifact_path(session, settings, revision.artifact_id)
    if path is None:
        _record_failed_run(
            session,
            revision.id,
            params={"doc_type": DOC_QUESTION_PAPER, "subject": slug},
            message="artifact file is missing from the content store",
        )
        summary.failed += 1
        summary.errors.append(f"document {doc.id}: artifact file missing")
        return

    data = path.read_bytes()
    paper_code = _paper_code_of(doc, revision)
    unit_code = derive_paper_code(revision.source_url or "")[1]
    try:
        nodes = build_question_tree(index_questions(data, "qp"))
        with pymupdf.open(stream=data, filetype="pdf") as pdf:
            page_count = len(pdf)
            ciphered = is_ciphered(pdf)
            texts = {node["number_path"]: _region_text(pdf, node["regions"], ciphered=ciphered) for node in nodes}
            marks = _question_marks(pdf, nodes, texts, ciphered=ciphered)
    except Exception as exc:  # 版式不支持、PDF 损坏等
        _record_failed_run(
            session,
            revision.id,
            params={"doc_type": DOC_QUESTION_PAPER, "subject": slug},
            message=f"question index failed: {exc}",
        )
        summary.failed += 1
        summary.errors.append(f"document {doc.id}: {exc}")
        return

    depth0 = [node for node in nodes if node["depth"] == 0]
    marks_total = sum(
        value for node in depth0 if (value := marks.get(node["number_path"])) is not None
    )
    unparsed = sum(1 for node in nodes if marks.get(node["number_path"]) is None)

    try:
        run = ParseRun(
            document_revision_id=revision.id,
            parser_version=PARSER_VERSION,
            params={"doc_type": DOC_QUESTION_PAPER, "subject": slug},
            status="running",
            started_at=_now(),
            stats={},
        )
        session.add(run)
        session.flush()
        paper = Paper(
            document_id=doc.id,
            paper_no=paper_code,
            marks_total=marks_total,
            question_count=len(depth0),
            parse_run_id=run.id,
            page_count=page_count,
            attrs={"unit_code": unit_code, "source_parser": PARSER_VERSION},
        )
        session.add(paper)
        session.flush()

        by_path: dict[str, Question] = {}
        for order, node in enumerate(nodes):
            regions = node["regions"]
            first = regions[0] if regions else {}
            last = regions[-1] if regions else {}
            parent = by_path.get(node["parent_path"]) if node["parent_path"] else None
            question = Question(
                paper_id=paper.id,
                parent_id=parent.id if parent is not None else None,
                number_label=node["number_label"][:64],
                number_path=node["number_path"][:128],
                display_order=order,
                depth=node["depth"],
                kind=node["kind"],
                marks=marks.get(node["number_path"]),
                page_from=first.get("page"),
                page_to=last.get("page"),
                bbox_from=list(first["bbox"]) if first.get("bbox") else None,
                bbox_to=list(last["bbox"]) if last.get("bbox") else None,
                stem_text=texts.get(node["number_path"]) or None,
                parse_run_id=run.id,
                parse_confidence=1.0,
                has_override=False,
                attrs={"regions": regions, "unit_code": unit_code},
            )
            session.add(question)
            session.flush()
            by_path[node["number_path"]] = question

        run.status = "completed"
        run.finished_at = _now()
        run.stats = {
            "questions": len(nodes),
            "marks_unparsed": unparsed,
            "page_count": page_count,
        }
        revision.parse_status = "parsed"
        revision.parse_error = None
        doc.status = "ok"
        session.commit()
    except Exception as exc:
        if is_locked_error(exc):
            # 锁竞争是瞬时故障，不是解析失败：回滚后抛给调用方重试，
            # 不能记成 ParseRun(failed) 把这份卷判死刑。
            session.rollback()
            raise
        _record_failed_run(
            session,
            revision.id,
            params={"doc_type": DOC_QUESTION_PAPER, "subject": slug},
            message=f"question split failed: {exc}",
        )
        summary.failed += 1
        summary.errors.append(f"document {doc.id}: {exc}")
        return

    summary.papers += 1
    summary.questions += len(nodes)


def _split_ms(
    session: Session,
    settings: Settings,
    doc: Document,
    qp_index: dict[tuple[int, Optional[int], str], Document],
    summary: SplitSummary,
    cache: dict[int, dict[str, Question]],
    *,
    force: bool,
    slug: str,
) -> None:
    revision = session.get(DocumentRevision, doc.current_revision_id)
    if revision is None or revision.artifact_id is None:
        summary.skipped += 1
        return

    existing = list(
        session.scalars(select(MarkScheme).where(MarkScheme.document_id == doc.id))
    )
    foreign = [ms for ms in existing if _own_run(session, ms.parse_run_id) is None]
    if foreign:
        summary.conflicts += 1
        summary.errors.append(
            f"document {doc.id}: mark scheme from another parser; skipped (no changes)"
        )
        return
    if existing and not force:
        current = [
            ms
            for ms in existing
            if (run := _own_run(session, ms.parse_run_id)) is not None
            and run.document_revision_id == doc.current_revision_id
        ]
        if current:
            # 自愈：QP 曾解析失败时，MS 会被切成 0 条并记为 completed；即使 QP
            # 后来修好也不会重切。0 条且 QP 已有题目时不再跳过，落入下方重切。
            entries = session.scalar(
                select(func.count())
                .select_from(MarkSchemeEntry)
                .where(MarkSchemeEntry.mark_scheme_id.in_([ms.id for ms in current]))
            )
            code = _paper_code_of(doc, revision)
            qp, _qp_confidence, _qp_method = _lookup_qp(qp_index, doc, code)
            if not (
                entries == 0
                and qp is not None
                and _questions_for_doc(session, qp.id, cache)
            ):
                summary.skipped += 1
                return
    stale_shas = _ms_source_shas(session, doc.id)
    for mark_scheme in existing:
        _delete_mark_scheme(session, mark_scheme)
    session.flush()

    path = _artifact_path(session, settings, revision.artifact_id)
    if path is None:
        _record_failed_run(
            session,
            revision.id,
            params={"doc_type": DOC_MARK_SCHEME, "subject": slug},
            message="artifact file is missing from the content store",
        )
        summary.failed += 1
        summary.errors.append(f"document {doc.id}: artifact file missing")
        return

    data = path.read_bytes()
    paper_code = _paper_code_of(doc, revision)
    qp_doc, qp_confidence, qp_method = _lookup_qp(qp_index, doc, paper_code)
    questions = _questions_for_doc(session, qp_doc.id, cache) if qp_doc is not None else {}
    try:
        index, ms_index_source = index_ms_questions(data, questions)
        nodes = build_question_tree(index)
        with pymupdf.open(stream=data, filetype="pdf") as pdf:
            ciphered = is_ciphered(pdf)
            texts = {node["number_path"]: _region_text(pdf, node["regions"], ciphered=ciphered) for node in nodes}
    except Exception as exc:
        _record_failed_run(
            session,
            revision.id,
            params={"doc_type": DOC_MARK_SCHEME, "subject": slug},
            message=f"mark scheme index failed: {exc}",
        )
        summary.failed += 1
        summary.errors.append(f"document {doc.id}: {exc}")
        return

    try:
        run = ParseRun(
            document_revision_id=revision.id,
            parser_version=PARSER_VERSION,
            params={"doc_type": DOC_MARK_SCHEME, "subject": slug},
            status="running",
            started_at=_now(),
            stats={},
        )
        session.add(run)
        session.flush()
        mark_scheme = MarkScheme(
            document_id=doc.id,
            matched_paper_document_id=qp_doc.id if qp_doc is not None else None,
            match_confidence=qp_confidence,
            match_method=qp_method,
            match_evidence={
                "paper_code": paper_code,
                "normalized_code": _norm_paper_code(paper_code) or None,
                "families": sorted(_paper_families(paper_code, doc.title)),
                "series_id": doc.series_id,
                "candidates": sorted(
                    code
                    for (subject_id, series_id, code) in qp_index
                    if subject_id == doc.subject_id and series_id == doc.series_id
                ),
            },
            parse_run_id=run.id,
        )
        session.add(mark_scheme)
        session.flush()

        artifact = session.get(Artifact, revision.artifact_id)
        sha256 = artifact.sha256 if artifact is not None else ""
        if qp_doc is not None and stale_shas:
            _strip_ms_regions(session, qp_doc.id, stale_shas)
        matched = 0
        for node in nodes:
            question = questions.get(node["number_path"])
            if question is None:
                continue
            session.add(
                MarkSchemeEntry(
                    mark_scheme_id=mark_scheme.id,
                    question_id=question.id,
                    number_label=node["number_label"][:64],
                    number_path=node["number_path"][:128],
                    marks=None,
                    answer_text=texts.get(node["number_path"]) or None,
                    acceptable_answers=[],
                    raw={"regions": node["regions"]},
                    parse_confidence=1.0,
                )
            )
            _merge_ms_regions(question, node["regions"], sha256)
            matched += 1

        run.status = "completed"
        run.finished_at = _now()
        run.stats = {
            "entries": matched,
            "index_questions": len(nodes),
            "ms_index": ms_index_source,
            "matched_paper_document_id": qp_doc.id if qp_doc is not None else None,
            "match_method": qp_method,
        }
        revision.parse_status = "parsed"
        revision.parse_error = None
        doc.status = "ok"
        session.commit()
    except Exception as exc:
        if is_locked_error(exc):
            # 同 _split_qp：锁竞争回滚重试，不记 ParseRun(failed)。
            session.rollback()
            raise
        _record_failed_run(
            session,
            revision.id,
            params={"doc_type": DOC_MARK_SCHEME, "subject": slug},
            message=f"mark scheme split failed: {exc}",
        )
        summary.failed += 1
        summary.errors.append(f"document {doc.id}: {exc}")
        return

    summary.mark_schemes += 1
    summary.ms_entries += matched
    if qp_doc is not None:
        summary.ms_matched += 1
    else:
        summary.ms_unmatched += 1


def split_subject(
    session: Session,
    settings: Settings,
    slug: str,
    *,
    series: Optional[str] = None,
    limit: Optional[int] = None,
    force: bool = False,
) -> SplitSummary:
    """切一个科目的 QP 与 MS。QP 全部切完再切 MS（MS 要按题号对齐 QP）。"""
    summary = SplitSummary()
    subject = _subject(session, slug)
    if subject is None:
        raise LookupError(f"subject {slug} is not in the database; run sync first")

    series_ids = _series_ids(session, series) if series else None
    if series and not series_ids:
        return summary

    qp_docs = _documents(session, subject.id, DOC_QUESTION_PAPER, series_ids, limit)
    ms_docs = _documents(session, subject.id, DOC_MARK_SCHEME, series_ids, limit)

    qp_index: dict[tuple[int, Optional[int], str], Document] = {}
    for doc in qp_docs:
        revision = session.get(DocumentRevision, doc.current_revision_id)
        code = _paper_code_of(doc, revision)
        if code:
            qp_index[(doc.subject_id, doc.series_id, code)] = doc
        try:
            with_lock_retry(
                session,
                lambda: _split_qp(session, settings, doc, summary, force=force, slug=slug),
            )
        except Exception as exc:
            session.rollback()
            summary.failed += 1
            summary.errors.append(f"document {doc.id}: {exc}")
            continue

    cache: dict[int, dict[str, Question]] = {}
    for doc in ms_docs:
        try:
            with_lock_retry(
                session,
                lambda: _split_ms(
                    session, settings, doc, qp_index, summary, cache, force=force, slug=slug
                ),
            )
        except Exception as exc:
            session.rollback()
            summary.failed += 1
            summary.errors.append(f"document {doc.id}: {exc}")
            continue

    return summary
