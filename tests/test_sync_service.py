"""抓取层 robots 语义测试。

覆盖两处曾经静默出错的地方：
1. **Fetcher**：命中 robots 禁止时返回 `robots_blocked=True` 的 FetchResult，
   而不是抛 RobotsDisallowed。否则调用方的 except 分支是死代码，
   `status=0` 的合规拒绝会被当成采集故障。
2. **SyncService**：robots 拒绝必须记成"跳过 + robots 统计"，
   绝不能落进 download_failed，否则合规拒绝会污染失败统计。

全程不联网：Fetcher 换成 MockTransport，SyncService 注入假抓取器。
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import Session

from examdata.adapters.base import DiscoveredResource, SyllabusRef
from examdata.core.config import Settings
from examdata.core.fetch import Fetcher, FetchResult, RobotsDisallowed
from examdata.core.models import (
    Artifact,
    ArtifactRevision,
    Base,
    DocClassification,
    Document,
    DocumentRevision,
    ResourceCandidate,
    ResourceSource,
    SyncRun,
)
from examdata.core.storage import ContentAddressedStore
from examdata.sync import service as sync_service
from examdata.sync.service import (
    CANDIDATE_ERROR,
    CANDIDATE_MISSING,
    CANDIDATE_SEEN,
    CANDIDATE_SKIPPED,
    SyncService,
)

SYLLABUS = SyllabusRef(
    slug="fake-maths-0001",
    code="0001",
    title="Fake Mathematics",
    qualification_key="fake-igcse",
    qualification_name="Fake IGCSE",
    source_url="https://example.invalid/maths/past-papers",
)
RESOURCE_URL = "https://example.invalid/papers/0001-01-qp.pdf"


@pytest.fixture()
def settings(tmp_path) -> Settings:
    """零间隔 + 私有数据目录：测试不联网、不写开发库。"""
    return Settings(
        data_dir=tmp_path,
        min_host_interval_seconds=0.0,
        host_interval_jitter_seconds=0.0,
        max_retries=1,
    )


@pytest.fixture()
def session():
    """进程内 SQLite：同步编排测试不需要真实开发库，也不落盘。"""
    engine = create_engine("sqlite://", future=True)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as db:
        assert db.scalar(text("PRAGMA foreign_keys")) == 1
        yield db
        assert db.execute(text("PRAGMA foreign_key_check")).all() == []
    engine.dispose()


def _mock_transport(fetcher: Fetcher, handler) -> None:
    """把抓取器的客户端换成 MockTransport，任何真实请求都会失败。"""
    fetcher._client.close()
    fetcher._client = httpx.Client(
        transport=httpx.MockTransport(handler), follow_redirects=True
    )


def _deny_robots(self, url: str) -> None:
    raise RobotsDisallowed(f"robots.txt 禁止抓取 {url}（robots: https://x/robots.txt）")


class FakeFetcher:
    """不做网络访问的假抓取器：回放预置结果并记录调用。"""

    def __init__(self, result: FetchResult) -> None:
        self.result = result
        self.calls: list[tuple[str, dict]] = []
        self.closed = False

    def get(self, url: str, **kwargs) -> FetchResult:
        self.calls.append((url, kwargs))
        return self.result

    def close(self) -> None:
        self.closed = True


class FakeAdapter:
    """最小适配器：只回放预置资源，发现阶段不发任何请求。"""

    key = "fake"
    board_name = "Fake Board"
    homepage = "https://example.invalid"
    accessibility = "public"

    def __init__(self, resources: list[DiscoveredResource]) -> None:
        self.resources = resources

    def discover_syllabuses(self):
        return [SYLLABUS]

    def discover_resources(self, ref):
        return list(self.resources)

    def normalize_metadata(self, res):
        return dict(res.meta)


class FailingAdapter(FakeAdapter):
    def discover_resources(self, ref):
        raise RuntimeError("synthetic discovery failure")


def _ok_result(url: str = RESOURCE_URL, content: bytes = b"%PDF-1.4 synthetic") -> FetchResult:
    return FetchResult(
        url=url,
        status=200,
        headers={"content-type": "application/pdf", "etag": '"synthetic"'},
        content=content,
    )


def _error_result(url: str = RESOURCE_URL) -> FetchResult:
    return FetchResult(url=url, status=503, error="HTTP 503")


def _resource(url: str = RESOURCE_URL, *, paper_code: str = "0001/01") -> DiscoveredResource:
    return DiscoveredResource(
        url=url,
        label=f"Question paper {paper_code} June 2024",
        doc_type="question_paper",
        confidence=0.9,
        meta={"year": 2024, "series": "june 2024", "paper_code": paper_code},
        evidence={"label": "Question paper"},
        page_url="https://example.invalid/maths/past-papers",
    )


def _robots_result(url: str = RESOURCE_URL) -> FetchResult:
    return FetchResult(
        url=url, status=0, error=f"robots.txt 禁止抓取 {url}", robots_blocked=True
    )


def _service(session, settings, tmp_path, resources, fetcher=None, adapter=None) -> SyncService:
    return SyncService(
        session,
        adapter or FakeAdapter(resources),
        settings=settings,
        store=ContentAddressedStore(tmp_path / "artifacts"),
        fetcher=fetcher,
    )


# --------------------------------------------------------------------------
# Fetcher：robots 拒绝的表达方式
# --------------------------------------------------------------------------


def test_robots_disallowed_is_flagged_not_raised(monkeypatch, settings):
    """robots 拒绝必须是 robots_blocked=True 的结果，且不发出任何请求。"""
    sent: list[httpx.Request] = []

    def handler(request):
        sent.append(request)
        return httpx.Response(200, text="ok")

    monkeypatch.setattr(Fetcher, "assert_allowed", _deny_robots)
    with Fetcher(settings) as fetcher:
        _mock_transport(fetcher, handler)
        result = fetcher.get(RESOURCE_URL, expect_binary=True)

    assert result.robots_blocked is True
    assert result.status == 0
    assert result.error and "robots" in result.error
    assert result.ok is False, "被 robots 拒绝的结果绝不能看起来像成功"
    assert sent == [], "命中 Disallow 时不得发出请求"


def test_normal_response_is_not_flagged(settings):
    """正常响应不能被误标成 robots 拒绝，否则统计会反向失真。"""
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /search\n")
        return httpx.Response(
            200, content=b"%PDF-1.4", headers={"content-type": "application/pdf"}
        )

    with Fetcher(settings) as fetcher:
        _mock_transport(fetcher, handler)
        result = fetcher.get(RESOURCE_URL, expect_binary=True)

    assert result.ok is True
    assert result.robots_blocked is False
    assert result.content == b"%PDF-1.4"


# --------------------------------------------------------------------------
# SyncService：robots 拒绝的落库与统计
# --------------------------------------------------------------------------


def test_robots_blocked_resource_is_skipped_not_failed(session, settings, tmp_path):
    """robots 拒绝记成 skipped + robots，不落 download_failed。"""
    res = _resource()
    fetcher = FakeFetcher(_robots_result(res.url))
    svc = _service(session, settings, tmp_path, [res], fetcher)

    outcome = svc.sync_resource(SYLLABUS, res)

    assert outcome.action == "robots"
    assert outcome.document_id is not None, "被拒绝的资源仍应保留发现记录"
    assert svc.stats.robots_blocked == 1
    assert svc.stats.download_failed == 0
    assert svc.stats.errors == []
    assert [url for url, _ in fetcher.calls] == [res.url]

    cand = session.scalar(
        select(ResourceCandidate).where(ResourceCandidate.url == res.url)
    )
    assert cand is not None
    assert cand.status == CANDIDATE_SKIPPED
    assert cand.error.startswith("robots:")


def test_raising_fetcher_uses_same_robots_semantics(session, settings, tmp_path):
    """抓取器若直接抛 RobotsDisallowed，处置必须与标志位路径一致。"""

    class RaisingFetcher(FakeFetcher):
        def get(self, url: str, **kwargs) -> FetchResult:
            raise RobotsDisallowed(f"robots.txt 禁止抓取 {url}")

    res = _resource()
    svc = _service(session, settings, tmp_path, [res], RaisingFetcher(_robots_result()))

    outcome = svc.sync_resource(SYLLABUS, res)

    assert outcome.action == "robots"
    assert svc.stats.robots_blocked == 1
    assert svc.stats.download_failed == 0

    cand = session.scalar(
        select(ResourceCandidate).where(ResourceCandidate.url == res.url)
    )
    assert cand.status == CANDIDATE_SKIPPED


def test_run_counts_robots_blocked_and_closes_fetcher(session, settings, tmp_path):
    """run() 的统计口径与抓取器生命周期。"""
    res = _resource()
    fetcher = FakeFetcher(_robots_result(res.url))
    svc = _service(session, settings, tmp_path, [res], fetcher)

    stats = svc.run()

    assert stats.robots_blocked == 1
    assert stats.download_failed == 0
    assert stats.downloaded == 0
    assert stats.errors == []
    assert fetcher.closed is True, "run() 结束必须释放抓取器"

    cand = session.scalar(
        select(ResourceCandidate).where(ResourceCandidate.url == res.url)
    )
    assert cand.status == CANDIDATE_SKIPPED
    assert "robots" in (cand.error or "")


def test_run_reuses_a_single_fetcher(monkeypatch, session, settings, tmp_path):
    """每条资源各建一个抓取器会丢掉 robots 缓存与限速状态。"""
    created: list[FakeFetcher] = []

    class CountingFetcher(FakeFetcher):
        def __init__(self, settings=None) -> None:
            super().__init__(_robots_result())
            created.append(self)

    monkeypatch.setattr(sync_service, "Fetcher", CountingFetcher)
    resources = [
        _resource("https://example.invalid/papers/0001-01-qp.pdf", paper_code="0001/01"),
        _resource("https://example.invalid/papers/0001-02-qp.pdf", paper_code="0001/02"),
    ]
    svc = _service(session, settings, tmp_path, resources)

    svc.run()

    assert len(created) == 1, "整轮同步只应创建一个抓取器"
    assert created[0].closed is True
    assert svc.stats.robots_blocked == 2
    assert svc.stats.download_failed == 0


def test_same_current_sha_is_idempotent_and_preserves_parse_status(session, settings, tmp_path):
    res = _resource()
    fetcher = FakeFetcher(_ok_result())
    svc = _service(session, settings, tmp_path, [res], fetcher)
    first = svc.sync_resource(SYLLABUS, res)
    session.commit()
    doc = session.get(Document, first.document_id)
    revision_id = doc.current_revision_id
    session.get(DocumentRevision, revision_id).parse_status = "parsed"
    session.commit()

    second = svc.sync_resource(SYLLABUS, res)
    session.commit()

    assert first.action == "created"
    assert second.action == "unchanged"
    assert doc.current_revision_id == revision_id
    assert session.get(DocumentRevision, revision_id).parse_status == "parsed"
    assert len(session.scalars(select(DocumentRevision)).all()) == 1
    assert len(session.scalars(select(ArtifactRevision)).all()) == 1
    assert len(session.scalars(select(DocClassification)).all()) == 1
    cand = session.scalar(select(ResourceCandidate))
    assert cand.content_sha256 == session.scalar(select(Artifact.sha256))
    assert cand.status == CANDIDATE_SEEN
    assert svc.stats.new_revisions == 0
    assert svc.stats.unchanged == 1
    assert svc.stats.downloaded == 2
    assert fetcher.calls[-1][1]["etag"] == '"synthetic"'


def test_identical_bytes_at_new_url_do_not_create_document_revision(session, settings, tmp_path):
    first_res = _resource()
    fetcher = FakeFetcher(_ok_result())
    svc = _service(session, settings, tmp_path, [first_res], fetcher)
    first = svc.sync_resource(SYLLABUS, first_res)
    session.commit()
    doc = session.get(Document, first.document_id)
    revision_id = doc.current_revision_id
    moved_res = _resource("https://example.invalid/papers/moved-qp.pdf")

    moved = svc.sync_resource(SYLLABUS, moved_res)
    session.commit()

    assert moved.action == "unchanged"
    assert doc.current_revision_id == revision_id
    assert len(session.scalars(select(Document)).all()) == 1
    assert len(session.scalars(select(DocumentRevision)).all()) == 1
    assert len(session.scalars(select(Artifact)).all()) == 1
    versions = session.scalars(select(ArtifactRevision).order_by(ArtifactRevision.id)).all()
    assert [version.url for version in versions] == [first_res.url, moved_res.url]
    assert [version.supersedes_id for version in versions] == [None, None]
    assert fetcher.calls[-1][1]["etag"] is None


def test_shared_artifact_still_creates_revision_for_another_document(session, settings, tmp_path):
    svc = _service(session, settings, tmp_path, [], FakeFetcher(_ok_result()))
    first = svc.sync_resource(SYLLABUS, _resource())
    second = svc.sync_resource(
        SYLLABUS, _resource("https://example.invalid/papers/second.pdf", paper_code="0001/02")
    )
    session.commit()

    assert first.action == second.action == "created"
    assert first.document_id != second.document_id
    assert len(session.scalars(select(DocumentRevision)).all()) == 2
    assert len(session.scalars(select(Artifact)).all()) == 1
    assert svc.stats.unchanged == 0
    assert svc.stats.duplicates == 1


def test_artifact_chain_is_url_local_and_uses_artifact_revision_ids(session, settings, tmp_path):
    res = _resource()
    fetcher = FakeFetcher(_ok_result(content=b"%PDF first"))
    svc = _service(session, settings, tmp_path, [res], fetcher)
    first = svc.sync_resource(SYLLABUS, res)
    session.commit()
    first_version = session.scalar(select(ArtifactRevision))
    first_version.id = 100
    session.commit()
    assert first_version.id != session.get(Document, first.document_id).current_revision_id

    fetcher.result = _ok_result(content=b"%PDF second")
    svc.sync_resource(SYLLABUS, res)
    session.commit()
    fetcher.result = _ok_result(content=b"%PDF first")
    svc.sync_resource(SYLLABUS, res)
    session.commit()

    versions = session.scalars(select(ArtifactRevision).order_by(ArtifactRevision.id)).all()
    assert [version.supersedes_id for version in versions] == [None, versions[0].id, versions[1].id]
    assert [version.change_kind for version in versions] == ["initial", "content_changed", "content_changed"]
    revisions = session.scalars(select(DocumentRevision).order_by(DocumentRevision.revision_no)).all()
    assert [revision.revision_no for revision in revisions] == [1, 2, 3]
    assert revisions[0].artifact_id == revisions[2].artifact_id
    assert revisions[1].artifact_id != revisions[0].artifact_id
    assert svc.stats.new_revisions == 2


def test_304_requires_matching_current_candidate_content(session, settings, tmp_path):
    res = _resource()
    fetcher = FakeFetcher(_ok_result())
    svc = _service(session, settings, tmp_path, [res], fetcher)
    svc.sync_resource(SYLLABUS, res)
    session.commit()
    cand = session.scalar(select(ResourceCandidate))
    cand.error = "previous failure"
    cand.status = CANDIDATE_ERROR
    fetcher.result = FetchResult(url=res.url, status=304, not_modified=True)

    outcome = svc.sync_resource(SYLLABUS, res)
    session.commit()

    assert outcome.action == "unchanged"
    assert cand.status == CANDIDATE_SEEN
    assert cand.error is None
    assert len(session.scalars(select(DocumentRevision)).all()) == 1
    assert svc.stats.downloaded == 1

    cand.content_sha256 = "outdated-content"
    outcome = svc.sync_resource(SYLLABUS, res)
    session.commit()
    assert outcome.action == "failed"
    assert cand.status == CANDIDATE_ERROR
    assert cand.etag is None
    assert fetcher.calls[-1][1]["etag"] is None
    assert session.scalar(select(Document.status)) == "stored"


def test_304_without_local_revision_is_failure(session, settings, tmp_path):
    svc = _service(
        session, settings, tmp_path, [],
        FakeFetcher(FetchResult(url=RESOURCE_URL, status=304, not_modified=True)),
    )
    outcome = svc.sync_resource(SYLLABUS, _resource())
    session.commit()

    assert outcome.action == "failed"
    assert svc.stats.unchanged == 0
    assert svc.stats.download_failed == 1
    assert session.scalar(select(Document.status)) == "failed"
    assert session.scalar(select(ResourceCandidate.status)) == CANDIDATE_ERROR


@pytest.mark.parametrize("download", [False, True])
def test_gated_is_classified_before_no_download(session, settings, tmp_path, download):
    res = _resource()
    res.meta["is_gated"] = True
    fetcher = FakeFetcher(_ok_result())
    svc = _service(session, settings, tmp_path, [res], fetcher)

    outcome = svc.sync_resource(SYLLABUS, res, download=download)
    session.commit()

    assert outcome.action == "gated"
    assert svc.stats.gated == 1
    assert svc.stats.download_failed == 0
    assert session.scalar(select(ResourceCandidate.status)) == CANDIDATE_SKIPPED
    assert session.scalar(select(Document.status)) == "discovered"
    assert fetcher.calls == []


def test_no_download_sets_candidate_skip_and_clears_old_failure(session, settings, tmp_path):
    res = _resource()
    fetcher = FakeFetcher(_error_result())
    svc = _service(session, settings, tmp_path, [res], fetcher)
    svc.sync_resource(SYLLABUS, res)
    session.commit()

    outcome = svc.sync_resource(SYLLABUS, res, download=False)
    session.commit()

    assert outcome.action == "skipped"
    assert session.scalar(select(ResourceCandidate.status)) == CANDIDATE_SKIPPED
    assert session.scalar(select(ResourceCandidate.error)) == "download=False"
    assert len(fetcher.calls) == 1


def test_failed_download_persists_status_then_recovers(session, settings, tmp_path):
    res = _resource()
    fetcher = FakeFetcher(_error_result())
    svc = _service(session, settings, tmp_path, [res], fetcher)
    failed = svc.sync_resource(SYLLABUS, res)
    session.commit()
    doc = session.get(Document, failed.document_id)

    assert failed.action == "failed"
    assert doc.status == "failed"
    assert session.scalar(select(ResourceCandidate.error)) == "HTTP 503"
    fetcher.result = _ok_result()
    recovered = svc.sync_resource(SYLLABUS, res)
    session.commit()
    assert recovered.action == "revision"
    assert doc.status == "stored"
    assert session.scalar(select(ResourceCandidate.error)) is None

    fetcher.result = _error_result()
    svc.sync_resource(SYLLABUS, res)
    session.commit()
    assert doc.status == "stored"
    assert doc.current_revision_id is not None
    assert len(session.scalars(select(DocumentRevision)).all()) == 1


def test_storage_failure_is_recorded_without_validators(session, settings, tmp_path, monkeypatch):
    res = _resource()
    svc = _service(session, settings, tmp_path, [res], FakeFetcher(_ok_result()))

    def fail_store(*args):
        raise OSError("synthetic storage failure")

    monkeypatch.setattr(svc.store, "put_bytes", fail_store)
    outcome = svc.sync_resource(SYLLABUS, res)
    session.commit()

    assert outcome.action == "failed"
    assert session.scalar(select(ResourceCandidate.etag)) is None
    assert session.scalar(select(ResourceCandidate.error)) == "synthetic storage failure"
    assert session.scalar(select(Document.status)) == "failed"
    assert session.scalars(select(Artifact)).all() == []


def test_reused_service_resets_stats_and_seen_urls_each_run(session, settings, tmp_path):
    res = _resource()
    svc = _service(session, settings, tmp_path, [res], FakeFetcher(_ok_result()))
    first_stats = svc.run()
    svc.adapter.resources = []

    second_stats = svc.run(download=False)

    assert first_stats is not second_stats
    assert first_stats.downloaded == 1
    assert first_stats.discovered == 1
    assert first_stats.missing == 0
    assert second_stats.downloaded == 0
    assert second_stats.discovered == 0
    assert second_stats.new_documents == 0
    assert second_stats.missing == 1
    assert session.scalar(select(ResourceCandidate.status)) == CANDIDATE_MISSING
    runs = session.scalars(select(SyncRun).order_by(SyncRun.id)).all()
    assert [run.stats["missing"] for run in runs] == [0, 1]
    assert [run.status for run in runs] == ["completed", "completed"]


def _another_ref(source_url="https://example.invalid/physics/past-papers"):
    return SyllabusRef(
        slug="fake-physics-0002", code="0002", title="Fake Physics",
        qualification_key="fake-igcse", qualification_name="Fake IGCSE",
        source_url=source_url,
    )


class CatalogAdapter(FakeAdapter):
    def __init__(self, refs, resources_by_slug):
        self.refs = refs
        self.resources_by_slug = resources_by_slug

    def discover_syllabuses(self):
        return self.refs

    def discover_resources(self, ref):
        result = self.resources_by_slug[ref.slug]
        if isinstance(result, Exception):
            raise result
        return iter(result)


@pytest.mark.parametrize("scope", ["filter", "syllabus_limit", "removed_syllabus"])
def test_missing_is_limited_to_fully_inspected_sources(session, settings, tmp_path, scope):
    other_ref = _another_ref()
    first_res = _resource()
    other_res = _resource("https://example.invalid/papers/physics.pdf")
    adapter = CatalogAdapter(
        [SYLLABUS, other_ref],
        {SYLLABUS.slug: [first_res], other_ref.slug: [other_res]},
    )
    svc = _service(session, settings, tmp_path, [], FakeFetcher(_ok_result()), adapter)
    svc.run()
    adapter.resources_by_slug = {SYLLABUS.slug: [], other_ref.slug: []}
    kwargs = {"download": False}
    if scope == "filter":
        kwargs["syllabus_filter"] = SYLLABUS.slug
    elif scope == "syllabus_limit":
        kwargs["syllabus_limit"] = 1
    else:
        adapter.refs = [SYLLABUS]

    stats = svc.run(**kwargs)

    candidates = {cand.url: cand for cand in session.scalars(select(ResourceCandidate))}
    assert stats.missing == 1
    assert candidates[first_res.url].status == CANDIDATE_MISSING
    assert candidates[other_res.url].status == CANDIDATE_SEEN


def test_resource_limit_cannot_mark_unprocessed_candidates_missing(session, settings, tmp_path):
    resources = [_resource(), _resource("https://example.invalid/papers/second.pdf", paper_code="0001/02")]
    svc = _service(session, settings, tmp_path, resources, FakeFetcher(_ok_result()))
    svc.run()

    stats = svc.run(resource_limit=1, download=False)

    assert stats.discovered == 1
    assert stats.missing == 0
    unprocessed = session.scalar(select(ResourceCandidate).where(ResourceCandidate.url == resources[1].url))
    assert unprocessed.status == CANDIDATE_SEEN


@pytest.mark.parametrize("limit_name", ["syllabus_limit", "resource_limit"])
def test_zero_limit_is_empty_not_unbounded(session, settings, tmp_path, limit_name):
    svc = _service(session, settings, tmp_path, [_resource()], FakeFetcher(_ok_result()))
    svc.run()

    stats = svc.run(download=False, **{limit_name: 0})

    assert stats.discovered == 0
    assert stats.missing == 0
    assert session.scalar(select(ResourceCandidate.status)) == CANDIDATE_SEEN


def test_failed_discovery_is_observable_and_does_not_mark_missing(session, settings, tmp_path):
    svc = _service(session, settings, tmp_path, [_resource()], FakeFetcher(_ok_result()))
    svc.run()
    svc.adapter = FailingAdapter([])

    stats = svc.run(download=False)

    assert stats.missing == 0
    assert session.scalar(select(ResourceCandidate.status)) == CANDIDATE_SEEN
    latest_run = session.scalar(select(SyncRun).order_by(SyncRun.id.desc()))
    assert latest_run.status == "failed"
    assert "synthetic discovery failure" in latest_run.error
    source = session.scalar(select(ResourceSource))
    assert source.last_checked_at is not None
    assert source.last_error == "synthetic discovery failure"


def test_partial_discovery_only_marks_successfully_inspected_source(session, settings, tmp_path):
    other_ref = _another_ref()
    resources = {SYLLABUS.slug: [_resource()], other_ref.slug: [_resource("https://example.invalid/other.pdf")]}
    adapter = CatalogAdapter([SYLLABUS, other_ref], resources)
    svc = _service(session, settings, tmp_path, [], FakeFetcher(_ok_result()), adapter)
    svc.run()
    adapter.resources_by_slug = {SYLLABUS.slug: [], other_ref.slug: RuntimeError("index failed")}

    stats = svc.run(download=False)

    assert stats.missing == 1
    assert session.scalar(select(SyncRun.status).order_by(SyncRun.id.desc())) == "partial"
    failed_candidate = session.scalar(select(ResourceCandidate).where(ResourceCandidate.url == "https://example.invalid/other.pdf"))
    assert failed_candidate.status == CANDIDATE_SEEN


def test_shared_source_partial_syllabus_scope_disables_missing(session, settings, tmp_path):
    other_ref = _another_ref(SYLLABUS.source_url)
    adapter = CatalogAdapter(
        [SYLLABUS, other_ref],
        {SYLLABUS.slug: [_resource()], other_ref.slug: [_resource("https://example.invalid/other.pdf")]},
    )
    svc = _service(session, settings, tmp_path, [], FakeFetcher(_ok_result()), adapter)
    svc.run()
    adapter.resources_by_slug[SYLLABUS.slug] = []

    stats = svc.run(download=False, syllabus_filter=SYLLABUS.slug)

    assert stats.missing == 0
    assert {cand.status for cand in session.scalars(select(ResourceCandidate))} == {CANDIDATE_SEEN}


def test_partial_resource_failure_persists_error_and_keeps_rollback_stats_clean(session, settings, tmp_path, monkeypatch):
    resources = [_resource(), _resource("https://example.invalid/second.pdf", paper_code="0001/02")]
    svc = _service(session, settings, tmp_path, resources, FakeFetcher(_ok_result()))
    original_next = svc._next_revision_no
    called = 0

    def fail_first(document_id):
        nonlocal called
        called += 1
        if called == 1:
            raise RuntimeError("synthetic revision failure")
        return original_next(document_id)

    monkeypatch.setattr(svc, "_next_revision_no", fail_first)
    stats = svc.run()

    assert stats.download_failed == 1
    assert stats.new_documents == 1
    assert stats.downloaded == 1
    assert session.scalar(select(SyncRun.status)) == "partial"
    candidates = {cand.url: cand for cand in session.scalars(select(ResourceCandidate))}
    assert candidates[resources[0].url].status == CANDIDATE_ERROR
    assert "synthetic revision failure" in candidates[resources[0].url].error
    assert candidates[resources[1].url].status == CANDIDATE_SEEN
    # 登记记录（文档行）在下载前提交，失败资源的文档保留并标记 failed；
    # 只有成功资源的文档带 revision。stats 仍保持回滚后的口径（new_documents=1）。
    docs = session.scalars(select(Document).order_by(Document.id)).all()
    assert len(docs) == 2
    assert docs[0].status == "failed"
    assert docs[0].current_revision_id is None
    assert docs[1].status == "stored"
    assert len(session.scalars(select(DocumentRevision)).all()) == 1


def test_top_level_discovery_failure_records_run_and_closes_fetcher(session, settings, tmp_path):
    class BrokenCatalog(FakeAdapter):
        def discover_syllabuses(self):
            raise RuntimeError("catalog failed")

    fetcher = FakeFetcher(_ok_result())
    svc = _service(session, settings, tmp_path, [], fetcher, BrokenCatalog([]))

    with pytest.raises(RuntimeError, match="catalog failed"):
        svc.run()

    run = session.scalar(select(SyncRun))
    assert run.status == "failed"
    assert run.finished_at is not None
    assert run.error == "catalog failed"
    assert run.stats["errors"] == ["RuntimeError: catalog failed"]
    assert fetcher.closed is True


@pytest.mark.parametrize("status", ["ok", "needs_review"])
@pytest.mark.parametrize("response", ["hash", "304"])
def test_unchanged_preserves_parsed_status(session, settings, tmp_path, status, response):
    svc = _service(session, settings, tmp_path, [_resource()], FakeFetcher(_ok_result()))
    svc.run()
    doc = session.scalar(select(Document))
    doc.status = status
    revision = session.get(DocumentRevision, doc.current_revision_id)
    revision.parse_status = "parsed"
    if response == "304":
        svc.fetcher.result = FetchResult(url=_resource().url, status=304)
    svc.run()
    assert doc.status == status
    assert revision.parse_status == "parsed"
