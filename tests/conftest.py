"""默认离线，数据库与文件写入使用进程私有 data root；显式配置仍受尊重。"""

from __future__ import annotations

import atexit
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine


@event.listens_for(Engine, "connect")
def _test_sqlite_temp_store(connection, _record):
    if isinstance(connection, sqlite3.Connection):
        connection.execute("PRAGMA temp_store=MEMORY")

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DATA_DIR = REPO_ROOT / ".data"
SOURCE_DB = SOURCE_DATA_DIR / "examdata.db"
PRIVATE_DATA_DIR: Path | None = None
# Keep SQLite temporary files in an existing writable test directory on Windows.
SQLITE_TEMP_DIR = REPO_ROOT / ".pytest_cache" / "sqlite-temp"
SQLITE_TEMP_DIR.mkdir(parents=True, exist_ok=True)
os.environ["SQLITE_TMPDIR"] = str(SQLITE_TEMP_DIR)
LIVE_TESTS = os.environ.get("EXAMDATA_TEST_LIVE") == "1"


def _sqlite_has_rows(path: Path) -> bool:
    try:
        conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    except sqlite3.Error:
        return False
    try:
        row = conn.execute(
            "SELECT 1 FROM question q JOIN paper p ON p.id=q.paper_id "
            "JOIN document d ON d.id=p.document_id "
            "JOIN document_revision r ON r.id=d.current_revision_id "
            "AND r.document_id=d.id "
            "WHERE r.parse_status IN ('parsed', 'needs_review') LIMIT 1"
        ).fetchone()
        return row is not None
    except sqlite3.Error:
        return False
    finally:
        conn.close()


def _make_copy(source: Path, destination: Path) -> bool:
    src = sqlite3.connect(f"{source.resolve().as_uri()}?mode=ro", uri=True)
    try:
        dst = sqlite3.connect(str(destination))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    return _sqlite_has_rows(destination)


def _cleanup() -> None:
    if PRIVATE_DATA_DIR is None:
        return
    from examdata.core import db

    if db._engine is not None:
        db._engine.dispose()
    shutil.rmtree(PRIVATE_DATA_DIR, ignore_errors=True)


if not os.environ.get("EXAMDATA_DATABASE_URL"):
    cache_dir = REPO_ROOT / ".pytest_cache"
    cache_dir.mkdir(exist_ok=True)
    PRIVATE_DATA_DIR = Path(tempfile.mkdtemp(prefix="examdata-tests-", dir=cache_dir))
    copy_db = PRIVATE_DATA_DIR / "examdata.db"
    os.environ["EXAMDATA_DATABASE_URL"] = f"sqlite:///{copy_db.as_posix()}"
    os.environ["EXAMDATA_DATA_DIR"] = str(PRIVATE_DATA_DIR)
    atexit.register(_cleanup)
    DB_AVAILABLE = False
    if SOURCE_DB.is_file():
        try:
            DB_AVAILABLE = _make_copy(SOURCE_DB, copy_db)
        except sqlite3.Error:
            for suffix in ("", "-wal", "-shm"):
                Path(f"{copy_db}{suffix}").unlink(missing_ok=True)
    for name in ("artifacts", "assets", "raw_pages"):
        source = SOURCE_DATA_DIR / name
        if source.is_dir():
            shutil.copytree(source, PRIVATE_DATA_DIR / name)
else:
    from sqlalchemy.engine import make_url

    configured = make_url(os.environ["EXAMDATA_DATABASE_URL"])
    if configured.get_backend_name() == "sqlite" and configured.database not in (None, "", ":memory:"):
        if Path(configured.database).resolve() == SOURCE_DB.resolve():
            raise RuntimeError("Refusing tests against the development database")
    DB_AVAILABLE = (
        bool(configured.database) and _sqlite_has_rows(Path(configured.database))
        if configured.get_backend_name() == "sqlite"
        else True
    )
    if not os.environ.get("EXAMDATA_DATA_DIR"):
        cache_dir = REPO_ROOT / ".pytest_cache"
        cache_dir.mkdir(exist_ok=True)
        PRIVATE_DATA_DIR = Path(tempfile.mkdtemp(prefix="examdata-tests-", dir=cache_dir))
        os.environ["EXAMDATA_DATA_DIR"] = str(PRIVATE_DATA_DIR)
        atexit.register(_cleanup)


from examdata.core.db import init_db
init_db()


@pytest.fixture(autouse=True)
def deny_live_http(monkeypatch):
    if LIVE_TESTS:
        return
    import httpx

    def reject(self, request):
        raise httpx.ConnectError("Live HTTP is disabled in tests", request=request)

    async def reject_async(self, request):
        raise httpx.ConnectError("Live HTTP is disabled in tests", request=request)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", reject)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", reject_async)


@pytest.fixture(scope="session")
def require_parsed_data():
    if not DB_AVAILABLE:
        pytest.skip("本地数据库没有已解析题目，跳过依赖语料的测试")


def _requires_corpus(item) -> bool:
    path = Path(str(getattr(item, "path", item.fspath)))
    name = item.originalname or item.name
    if "require_parsed_data" in item.fixturenames:
        return True
    if path.name == "test_intelligence.py":
        return bool({"session", "tx_session"} & set(item.fixturenames))
    if path.name == "test_classification_validation.py":
        return name in {
            "test_no_false_conflicts_on_real_corpus",
            "test_classification_finding_carries_evidence_when_present",
            "test_content_classifier_covers_every_pdf_document",
        }
    if path.name == "test_governance.py":
        if "clean_overrides" in item.fixturenames:
            return True
        return name in {
            "test_snapshot_reports_structure", "test_resolve_review_marks_finding_resolved",
            "test_provenance_covers_every_question", "test_provenance_rebuild_board_scope_keeps_other_boards",
            "test_provenance_trace_has_official_url", "test_provenance_trace_asset_points_to_question",
        }
    if path.name in {"test_api.py", "test_api_unified.py"}:
        return name in {
            "test_health", "test_search_papers_by_subject", "test_search_questions_filters",
            "test_question_detail_keeps_assets_and_mark_scheme", "test_asset_bytes_are_served",
            "test_paper_tree", "test_sample_by_count_is_reproducible", "test_sample_by_marks_target",
            "test_taxonomy_tree", "test_similar_questions_are_symmetric",
            "test_question_detail_includes_similar_and_difficulty", "test_monitor",
            "test_provenance_coverage_is_complete", "test_question_provenance_reaches_official_url",
            "test_asset_provenance_links_to_question", "test_question_explanation_separates_official_from_generated",
            "test_search_by_board_covers_both_boards_and_matches_questions",
            "test_search_board_aliases_are_equivalent", "test_search_passes_db_level_filters_through",
            "test_search_pagination_is_stable", "test_question_view_for_real_cambridge_question",
            "test_question_view_endpoint_is_shaped_like_a_real_request", "test_question_view_reports_missing_locator_honestly",
        }
    return False


def pytest_collection_modifyitems(config, items):
    for item in items:
        name = item.originalname or item.name
        if not LIVE_TESTS and name in {
            "test_paper_manifest_against_live_catalogue",
            "test_question_view_endpoint_is_shaped_like_a_real_request",
            "test_paper_manifest_branch_matches_resolve_schema",
        }:
            item.add_marker(pytest.mark.skip(reason="需要真实上游；默认离线"))
        if not DB_AVAILABLE and _requires_corpus(item):
            item.add_marker(pytest.mark.skip(reason="本地数据库没有已解析题目，跳过依赖语料的测试"))
