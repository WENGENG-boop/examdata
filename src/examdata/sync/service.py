"""同步编排服务。

把适配器的"发现"结果变成可追溯、可增量、可重放的持久化数据：

  发现资源 -> 计算身份键 -> 与库内比对 -> 仅对新增/变更发起下载
  -> 内容寻址存储 -> 生成 Artifact/ArtifactRevision -> Document/DocumentRevision
  -> 分类落库 -> 记录 provenance 与 SyncRun 统计

关键设计：
- identity_key 不依赖 URL 或站点 id（Cambridge 换文件时 /Images/{id} 会变），
  而是由 考试局|资格|科目代码|年份|考试季|Paper|文档类型 决定。
  因此"文件被替换"会被识别为**同一文档的新版本**，而不是新文档。
- 未在本轮发现中出现的候选标记为 missing，但不删除（保留版本历史）。
- 部分失败不阻塞其他资源。
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..adapters.base import BoardAdapter, DiscoveredResource, SyllabusRef
from ..core.config import Settings, get_settings
from ..core.fetch import Fetcher, RobotsDisallowed
from ..core.ids import identity_key
from ..core.models import (
    Artifact,
    ArtifactRevision,
    Board,
    DocClassification,
    Document,
    DocumentRevision,
    ExamSeries,
    Qualification,
    ResourceCandidate,
    ResourceSource,
    Subject,
    SyncRun,
)
from ..core.storage import ContentAddressedStore

CANDIDATE_NEW = "new"
CANDIDATE_SEEN = "seen"
CANDIDATE_MISSING = "missing"
CANDIDATE_ERROR = "error"
# 已知不可下载（登录墙 / robots 禁止）。与 error 分开：
# 这是站点明示的访问限制，不是采集故障。
CANDIDATE_SKIPPED = "skipped"


@dataclass
class SyncStats:
    """一轮同步的统计。"""

    syllabuses: int = 0
    discovered: int = 0
    new_documents: int = 0
    new_revisions: int = 0
    unchanged: int = 0
    duplicates: int = 0
    downloaded: int = 0
    download_failed: int = 0
    missing: int = 0
    bytes_downloaded: int = 0
    low_confidence: int = 0
    # 已识别但不可公开获取：登录墙档与 robots 禁止档。
    # 单列出来，避免把"站点要求登录"误报成"采集失败"。
    gated: int = 0
    robots_blocked: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["errors"] = d["errors"][:50]
        return d


@dataclass
class ResourceOutcome:
    url: str
    action: str  # created / revision / unchanged / failed / skipped
    document_id: Optional[int] = None
    identity_key: Optional[str] = None
    detail: Optional[str] = None


class SyncService:
    """一个考试局的同步编排。"""

    def __init__(
        self,
        session: Session,
        adapter: BoardAdapter,
        *,
        settings: Settings | None = None,
        store: ContentAddressedStore | None = None,
    ) -> None:
        self.session = session
        self.adapter = adapter
        self.settings = settings or get_settings()
        self.store = store or ContentAddressedStore()
        self.board: Optional[Board] = None
        self.sync_run: Optional[SyncRun] = None
        self.stats = SyncStats()
        self._sources: dict[str, ResourceSource] = {}
        self._qualifications: dict[str, Qualification] = {}
        self._subjects: dict[str, Subject] = {}
        self._series: dict[tuple[int, Optional[str]], ExamSeries] = {}
        self._seen_candidate_urls: set[str] = set()

    # -- 基础实体 ---------------------------------------------------------

    def ensure_board(self) -> Board:
        if self.board is not None:
            return self.board
        board = self.session.scalar(select(Board).where(Board.key == self.adapter.key))
        if board is None:
            board = Board(
                key=self.adapter.key,
                name=self.adapter.board_name or self.adapter.key,
                homepage=self.adapter.homepage,
                accessibility=self.adapter.accessibility,
                attrs={},
            )
            self.session.add(board)
            self.session.flush()
        self.board = board
        return board

    def ensure_qualification(self, ref: SyllabusRef) -> Qualification:
        key = ref.qualification_key
        if key in self._qualifications:
            return self._qualifications[key]
        board = self.ensure_board()
        qual = self.session.scalar(
            select(Qualification).where(
                Qualification.board_id == board.id, Qualification.key == key
            )
        )
        if qual is None:
            qual = Qualification(
                board_id=board.id, key=key, name=ref.qualification_name or key, attrs={}
            )
            self.session.add(qual)
            self.session.flush()
        self._qualifications[key] = qual
        return qual

    def ensure_subject(self, ref: SyllabusRef) -> Subject:
        if ref.slug in self._subjects:
            return self._subjects[ref.slug]
        qual = self.ensure_qualification(ref)
        subject = self.session.scalar(
            select(Subject).where(
                Subject.qualification_id == qual.id, Subject.code == ref.code
            )
        )
        if subject is None:
            subject = Subject(
                qualification_id=qual.id,
                code=ref.code,
                title=ref.title,
                slug=ref.slug,
                attrs=dict(ref.attrs or {}),
            )
            self.session.add(subject)
            self.session.flush()
        self._subjects[ref.slug] = subject
        return subject

    def ensure_series(self, year: Optional[int], session_name: Optional[str]) -> Optional[ExamSeries]:
        """取得/创建考季。

        specimen（样卷）这类资源没有考季，只有年份。exam_series 的
        year/session 都是 NOT NULL，因此宁可返回 None（Document.series_id
        本来就可空），也不要塞入 "unknown" 之类的假数据污染标准化字段。
        """
        if year is None or not session_name:
            return None
        key = (year, session_name)
        if key in self._series:
            return self._series[key]
        series = self.session.scalar(
            select(ExamSeries).where(
                ExamSeries.year == year, ExamSeries.session == session_name
            )
        )
        if series is None:
            series = ExamSeries(year=year, session=session_name, month=None, attrs={})
            self.session.add(series)
            self.session.flush()
        self._series[key] = series
        return series

    def ensure_source(self, ref: SyllabusRef) -> ResourceSource:
        url = ref.source_url
        if url in self._sources:
            return self._sources[url]
        board = self.ensure_board()
        src = self.session.scalar(
            select(ResourceSource).where(ResourceSource.url == url)
        )
        if src is None:
            src = ResourceSource(
                board_id=board.id,
                url=url,
                kind="past_papers_page",
                adapter_key=self.adapter.key,
                discovery_method="html_index",
                active=True,
                attrs={"slug": ref.slug, "code": ref.code},
            )
            self.session.add(src)
            self.session.flush()
        self._sources[url] = src
        return src

    # -- 文档与版本 -------------------------------------------------------

    def _document_identity(self, ref: SyllabusRef, res: DiscoveredResource) -> str:
        meta = self.adapter.normalize_metadata(res)
        return identity_key(
            self.adapter.key,
            ref.qualification_key,
            ref.code,
            meta.get("year"),
            meta.get("series"),
            meta.get("paper_code"),
            meta.get("doc_type") or res.doc_type,
        )

    def _upsert_candidate(self, source: ResourceSource, res: DiscoveredResource) -> ResourceCandidate:
        cand = self.session.scalar(
            select(ResourceCandidate).where(ResourceCandidate.url == res.url)
        )
        if cand is None:
            cand = ResourceCandidate(
                source_id=source.id,
                board_id=source.board_id,
                url=res.url,
                label=res.label,
                status=CANDIDATE_NEW,
                guessed_doc_type=res.doc_type,
                parsed_meta=dict(res.meta or {}),
                page_metadata={"page_url": res.page_url, "evidence": res.evidence},
                first_seen_run_id=self.sync_run.id if self.sync_run else None,
                last_seen_run_id=self.sync_run.id if self.sync_run else None,
                last_seen_at=_dt.datetime.now(_dt.timezone.utc),
            )
            self.session.add(cand)
            self.session.flush()
            return cand
        cand.label = res.label
        cand.guessed_doc_type = res.doc_type
        cand.parsed_meta = dict(res.meta or {})
        cand.page_metadata = {"page_url": res.page_url, "evidence": res.evidence}
        cand.last_seen_run_id = self.sync_run.id if self.sync_run else None
        cand.last_seen_at = _dt.datetime.now(_dt.timezone.utc)
        cand.status = CANDIDATE_SEEN
        return cand

    def sync_resource(
        self,
        ref: SyllabusRef,
        res: DiscoveredResource,
        *,
        download: bool = True,
    ) -> ResourceOutcome:
        board = self.ensure_board()
        subject = self.ensure_subject(ref)
        qual = self._qualifications[ref.qualification_key]
        source = self.ensure_source(ref)
        cand = self._upsert_candidate(source, res)
        self._seen_candidate_urls.add(res.url)

        meta = self.adapter.normalize_metadata(res)
        if res.confidence < 0.6:
            self.stats.low_confidence += 1

        year = meta.get("year")
        series_name = meta.get("series")
        series = self.ensure_series(year, series_name)
        idkey = self._document_identity(ref, res)

        doc = self.session.scalar(select(Document).where(Document.identity_key == idkey))
        is_new_doc = doc is None
        if doc is None:
            doc = Document(
                identity_key=idkey,
                board_id=board.id,
                qualification_id=qual.id,
                subject_id=subject.id,
                series_id=series.id if series else None,
                doc_type=res.doc_type,
                year=year,
                paper_code=meta.get("paper_code"),
                component=meta.get("component"),
                variant=meta.get("variant"),
                level=meta.get("level"),
                title=res.label,
                status="discovered",
                # 统一字段之外，保留考试局特有属性
                attrs={"board_specific": meta.get(self.adapter.key) or {}},
            )
            self.session.add(doc)
            self.session.flush()
            self.stats.new_documents += 1

        # 分类证据。按 (document, method) 幂等：重复 sync 不应累积多行，
        # 否则监控视图里同一份文件会出现若干条可能互相矛盾的判定。
        method = "label_grammar+slug_crosscheck"
        existing = self.session.scalar(
            select(DocClassification).where(
                DocClassification.document_id == doc.id,
                DocClassification.method == method,
            )
        )
        if existing is None:
            self.session.add(
                DocClassification(
                    document_id=doc.id,
                    doc_type=res.doc_type,
                    confidence=res.confidence,
                    evidence=dict(res.evidence or {}),
                    method=method,
                )
            )
        else:
            existing.doc_type = res.doc_type
            existing.confidence = res.confidence
            existing.evidence = dict(res.evidence or {})

        if not download:
            return ResourceOutcome(res.url, "skipped", doc.id, idkey, "download=False")

        # 已知需要登录的档：识别出它存在、登记文档，但不去抓。
        # 这不是"失败"——是站点明示的访问限制，记成失败会污染错误统计，
        # 让真正的问题淹没在几十条登录墙告警里。
        # 判定放在尝试之前：既省一次必然被拒的请求，也不违反 robots。
        if res.meta.get("is_gated"):
            cand.status = CANDIDATE_SKIPPED
            cand.error = "登录墙资源，仅登记不下载"
            self.stats.gated += 1
            return ResourceOutcome(res.url, "gated", doc.id, idkey, "登录墙")

        # 条件请求：无变化时零下载
        try:
            with Fetcher(self.settings) as fetcher:
                result = fetcher.get(
                    res.url,
                    etag=cand.etag,
                    last_modified=cand.last_modified,
                    expect_binary=True,
                )
        except RobotsDisallowed as exc:
            # robots 拒绝同样不是下载失败：这是遵守站点规则的正常结果
            cand.status = CANDIDATE_SKIPPED
            cand.error = f"robots: {exc}"
            self.stats.robots_blocked += 1
            return ResourceOutcome(res.url, "robots", doc.id, idkey, "robots 禁止")
        except Exception as exc:  # 单个资源失败不得中断整轮
            cand.status = CANDIDATE_ERROR
            cand.error = str(exc)[:500]
            self.stats.download_failed += 1
            self.stats.errors.append(f"{res.url}: {exc}")
            return ResourceOutcome(res.url, "failed", doc.id, idkey, str(exc)[:200])

        if result.not_modified:
            self.stats.unchanged += 1
            return ResourceOutcome(res.url, "unchanged", doc.id, idkey, "304 未修改")

        if not result.ok or result.content is None:
            cand.status = CANDIDATE_ERROR
            cand.error = result.error or f"HTTP {result.status}"
            self.stats.download_failed += 1
            self.stats.errors.append(f"{res.url}: {result.error or result.status}")
            return ResourceOutcome(res.url, "failed", doc.id, idkey, result.error)

        cand.etag = result.etag
        cand.last_modified = result.last_modified

        data = result.content
        mime = (result.content_type or "").split(";")[0].strip() or None
        stored = self.store.put_bytes(data, mime)
        self.stats.downloaded += 1
        self.stats.bytes_downloaded += len(data)

        # 内容寻址：同一份文件多处出现只存一份（sha256 唯一）
        artifact = self.session.scalar(
            select(Artifact).where(Artifact.sha256 == stored.sha256)
        )
        if artifact is None:
            artifact = Artifact(
                sha256=stored.sha256,
                size_bytes=len(data),
                mime=mime or self.store.guess_mime(stored.storage_key),
                storage_key=stored.storage_key,
                first_fetched_at=_dt.datetime.now(_dt.timezone.utc),
                source_url=res.url,
                attrs={"ext": stored.storage_key.rsplit(".", 1)[-1]},
            )
            self.session.add(artifact)
            self.session.flush()
        else:
            self.stats.duplicates += 1

        prev_rev = doc.current_revision_id
        revision = DocumentRevision(
            document_id=doc.id,
            artifact_id=artifact.id,
            revision_no=self._next_revision_no(doc.id),
            source_url=res.url,
            discovered_at=_dt.datetime.now(_dt.timezone.utc),
            status="stored",
            parser_version=self.settings.parser_version,
            parse_status="pending",
        )
        self.session.add(revision)
        self.session.flush()

        self.session.add(
            ArtifactRevision(
                artifact_id=artifact.id,
                url=res.url,
                etag=result.etag,
                last_modified=result.last_modified,
                fetched_at=_dt.datetime.now(_dt.timezone.utc),
                supersedes_id=prev_rev,
                change_kind="initial" if prev_rev is None else "content_changed",
            )
        )

        doc.current_revision_id = revision.id
        doc.status = "stored"
        doc.title = doc.title or res.label
        if is_new_doc:
            pass
        else:
            self.stats.new_revisions += 1

        return ResourceOutcome(
            res.url,
            "created" if is_new_doc else "revision",
            doc.id,
            idkey,
        )

    def _next_revision_no(self, document_id: int) -> int:
        existing = self.session.scalars(
            select(DocumentRevision.revision_no).where(
                DocumentRevision.document_id == document_id
            )
        ).all()
        return (max(existing) + 1) if existing else 1

    # -- 主流程 -----------------------------------------------------------

    def run(
        self,
        *,
        syllabus_limit: Optional[int] = None,
        resource_limit: Optional[int] = None,
        download: bool = True,
        syllabus_filter: Optional[str] = None,
    ) -> SyncStats:
        board = self.ensure_board()
        self.sync_run = SyncRun(
            board_id=board.id,
            adapter_key=self.adapter.key,
            status="running",
            started_at=_dt.datetime.now(_dt.timezone.utc),
            stats={},
        )
        self.session.add(self.sync_run)
        # 先固化本轮记录：后续单条资源回滚不会丢掉它
        self.session.commit()

        try:
            refs = list(self.adapter.discover_syllabuses())
            if syllabus_filter:
                refs = [r for r in refs if r.slug == syllabus_filter or r.code == syllabus_filter]
            if syllabus_limit:
                refs = refs[:syllabus_limit]
            self.stats.syllabuses = len(refs)

            for ref in refs:
                try:
                    resources = list(self.adapter.discover_resources(ref))
                except Exception as exc:
                    self.stats.errors.append(f"{ref.slug}: 发现失败 {exc}")
                    continue
                if resource_limit:
                    resources = resources[:resource_limit]
                self.stats.discovered += len(resources)
                for res in resources:
                    try:
                        self.sync_resource(ref, res, download=download)
                        # 每条资源独立提交：单条失败只丢弃它自己，不影响本轮其他成果
                        self.session.commit()
                    except Exception as exc:
                        self.session.rollback()
                        # 回滚会让已缓存的基础实体失效，必须清空后重建，
                        # 否则后续资源会引用已回滚的 id 而触发外键错误
                        self._invalidate_caches()
                        self.stats.errors.append(f"{res.url}: {type(exc).__name__}: {exc}")
                        self.stats.download_failed += 1

            # 未在本轮出现的候选标记为 missing（保留，不删除）
            self._mark_missing(board.id)

            self.sync_run.status = "completed"
        except Exception as exc:
            self.sync_run.status = "failed"
            self.sync_run.error = str(exc)[:1000]
            raise
        finally:
            self.sync_run.finished_at = _dt.datetime.now(_dt.timezone.utc)
            self.sync_run.stats = self.stats.to_dict()
            self.session.commit()
        return self.stats

    def _invalidate_caches(self) -> None:
        """回滚后清空缓存的基础实体，并重建 board / sync_run 引用。"""
        self._sources.clear()
        self._subjects.clear()
        self._qualifications.clear()
        self._series.clear()
        self.board = None
        self.ensure_board()
        if self.sync_run is not None:
            run_id = self.sync_run.id
            self.sync_run = self.session.get(SyncRun, run_id)

    def _mark_missing(self, board_id: int) -> None:
        rows = self.session.scalars(
            select(ResourceCandidate).where(
                ResourceCandidate.board_id == board_id,
                ResourceCandidate.status.in_([CANDIDATE_NEW, CANDIDATE_SEEN]),
            )
        ).all()
        for cand in rows:
            if cand.url not in self._seen_candidate_urls:
                cand.status = CANDIDATE_MISSING
                self.stats.missing += 1
