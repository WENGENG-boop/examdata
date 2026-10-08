from __future__ import annotations

import base64
import importlib
import json
from contextlib import contextmanager
from io import BytesIO
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from zipfile import ZipFile

import pymupdf
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from examdata.api.security import install_security
from examdata.core.fetch import FetchResult
from examdata.core.models import (
    Asset, Base, Board, Document, ExamSeries, Paper, Qualification, Question, Subject,
)
from examdata.paperqa import query, resolve


CIE_ARGS = {"board": "cie", "subject": "9709", "year": 2026, "season": "Mar", "paper": "12"}
PEARSON_ARGS = {
    "board": "edexcel", "subject": "Economics", "year": 2024, "season": "Jun", "paper": "wec11-01",
}


def _pdf_bytes():
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((60, 100), "1 Synthetic question")
        return pdf.tobytes()


PDF = _pdf_bytes()


class FakeFetcher:
    def __init__(self, *, records=None, catalogue=None, status=200, data=PDF, error=None):
        self.records = records
        self.catalogue = catalogue
        self.status = status
        self.data = data
        self.error = error
        self.calls = []

    def post_form(self, url, data, **kwargs):
        self.calls.append(("POST", url))
        if self.error is not None:
            raise self.error
        catalogue = self.catalogue
        if catalogue is None:
            rows = [{"file": f"9709_m26_{role}_12.pdf"} for role in ("qp", "ms")]
            catalogue = {"total": len(rows), "rows": rows}
        return FetchResult(url, 200, text=json.dumps(catalogue))

    def get_text(self, url, **kwargs):
        self.calls.append(("CAT", url))
        records = self.records
        if records is None:
            records = [_record("/content/dam/pdf/Economics/wec11-01-que-20240510.pdf")]
        return FetchResult(url, 200, text=json.dumps({"searchResults": {"algoliaRecords": records}}))

    def get(self, url, **kwargs):
        self.calls.append(("GET", url))
        return FetchResult(url, self.status, content=self.data)


def _record(url):
    return {"url": url, "category": ["Pearson-UK:Document-Type/Question-paper"]}


@pytest.fixture
def api(monkeypatch, tmp_path):
    module = importlib.import_module("examdata.api.app")
    unified = importlib.import_module("examdata.api.unified")
    monkeypatch.delenv("EXAMDATA_API_KEY", raising=False)
    monkeypatch.delenv("EXAMDATA_CORS_ORIGINS", raising=False)
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    root = tmp_path / "artifacts"
    root.mkdir()
    monkeypatch.setattr(module, "get_settings", lambda: SimpleNamespace(artifacts_dir=root))

    @contextmanager
    def scope():
        with Session(engine) as session:
            yield session

    monkeypatch.setattr(module, "session_scope", scope)

    def dependency():
        with scope() as session:
            yield session

    app = FastAPI()
    app.include_router(module.app.router)
    app.dependency_overrides[module.get_session] = dependency
    app.dependency_overrides[unified.get_session] = dependency
    state = SimpleNamespace(app=app, module=module, unified=unified, engine=engine, root=root, scope=scope)
    try:
        yield state
    finally:
        engine.dispose()


def _patch_fetcher(api, monkeypatch, fetcher):
    for module in (api.module, api.unified):
        monkeypatch.setattr(module, "paperqa_query", lambda *args: query(*args, fetcher=fetcher))
        monkeypatch.setattr(module, "paperqa_resolve", lambda *args: resolve(*args, fetcher=fetcher))


def _asset(api, key):
    with api.scope() as session:
        asset = Asset(sha256="a" * 64, storage_key=key, mime="image/png")
        session.add(asset)
        session.commit()
        return asset.id


def test_health_is_anonymous_and_does_not_leak_database_errors(api, monkeypatch):
    monkeypatch.setenv("EXAMDATA_API_KEY", "test-key")
    install_security(api.app)
    with TestClient(api.app, root_path="/proxy") as client:
        response = client.get("/proxy/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "papers": 0}

        @contextmanager
        def broken_scope():
            raise RuntimeError("private-database-connection-details")
            yield

        monkeypatch.setattr(api.module, "session_scope", broken_scope)
        response = client.get("/proxy/health")
        assert response.status_code == 503
        assert response.json() == {"detail": "数据库不可用"}
        assert "private-database" not in response.text


@pytest.mark.parametrize("key", ["../secret.png", "ab/../../secret.png", r"..\secret.png", "/secret.png", r"C:\secret.png", "C:secret.png", r"\\server\share\secret.png"])
def test_asset_path_escape_is_denied(api, key):
    (api.root.parent / "secret.png").write_bytes(b"not-an-asset")
    asset_id = _asset(api, key)
    with TestClient(api.app) as client:
        response = client.get(f"/assets/{asset_id}")
    assert response.status_code == 403
    assert response.json() == {"detail": "资产路径无效"}
    assert b"not-an-asset" not in response.content


def test_asset_resolved_symlink_cannot_escape_root(api):
    outside = api.root.parent / "outside.png"
    outside.write_bytes(b"not-an-asset")
    link = api.root / "linked.png"
    try:
        link.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"The platform cannot create a symlink: {exc}")
    asset_id = _asset(api, "linked.png")
    with TestClient(api.app) as client:
        response = client.get(f"/assets/{asset_id}")
    assert response.status_code == 403


def test_asset_success_missing_and_directory_have_stable_statuses(api):
    path = api.root / "ab" / "image.png"
    path.parent.mkdir()
    path.write_bytes(b"synthetic-image")
    asset_id = _asset(api, "ab/image.png")
    with TestClient(api.app) as client:
        response = client.get(f"/assets/{asset_id}")
        assert response.status_code == 200
        assert response.content == b"synthetic-image"
        assert response.headers["content-type"].startswith("image/png")
        assert client.get("/assets/999999").status_code == 404
        path.unlink()
        assert client.get(f"/assets/{asset_id}").status_code == 410
        path.mkdir()
        assert client.get(f"/assets/{asset_id}").status_code == 410


def test_unified_question_link_carries_explicit_board_and_round_trips(api, monkeypatch):
    with api.scope() as session:
        board = Board(key="edexcel", name="Synthetic board")
        session.add(board)
        session.flush()
        qualification = Qualification(board_id=board.id, key="synthetic", name="Synthetic")
        series = ExamSeries(year=2024, session="june 2024", month=6)
        session.add_all([qualification, series])
        session.flush()
        subject = Subject(qualification_id=qualification.id, code="1234", title="Synthetic")
        session.add(subject)
        session.flush()
        document = Document(
            identity_key="synthetic-edexcel", board_id=board.id, qualification_id=qualification.id,
            subject_id=subject.id, series_id=series.id, doc_type="question_paper", year=2024,
            paper_code="wec11-01",
        )
        session.add(document)
        session.flush()
        paper = Paper(document_id=document.id, paper_no="wec11-01")
        session.add(paper)
        session.flush()
        question = Question(paper_id=paper.id, number_label="1", number_path="1", display_order=1)
        session.add(question)
        session.commit()
        question_id = question.id
    fetcher = FakeFetcher()
    _patch_fetcher(api, monkeypatch, fetcher)
    with TestClient(api.app) as client:
        detail = client.get(f"/api/v1/question/{question_id}")
        assert detail.status_code == 200
        source = detail.json()["source"]
        assert source["board_canonical"] == "edexcel"
        endpoint = source["paper_endpoint"]
        params = parse_qs(urlsplit(endpoint).query)
        assert params["board"] == ["edexcel"]
        assert params["subject"] == ["1234"]
        assert params["mode"] == ["paper"]
        response = client.get(endpoint + "&download=false")
    assert response.status_code == 200
    assert response.json()["board"] == "edexcel"
    assert response.json()["board_source"] == "explicit"
    assert response.json()["request"]["board"] == "edexcel"
    assert not any(call[0] == "GET" for call in fetcher.calls)


def test_unified_download_and_json_preserve_binary_contract(api, monkeypatch):
    fetcher = FakeFetcher()
    _patch_fetcher(api, monkeypatch, fetcher)
    with TestClient(api.app) as client:
        binary = client.get("/api/v1/paper", params=CIE_ARGS)
        assert binary.status_code == 200
        assert binary.content == PDF
        assert binary.headers["content-disposition"] == 'attachment; filename="9709_m26_qp_12.pdf"'
        assert int(binary.headers["content-length"]) == len(PDF)
        response = client.get("/api/v1/paper", params={**CIE_ARGS, "format": "json"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["board_source"] == "explicit"
        assert base64.b64decode(payload["files"][0]["data_base64"]) == PDF
        archive = client.get("/api/v1/paper", params={**CIE_ARGS, "mode": "both"})
        assert archive.headers["content-type"] == "application/zip"
        with ZipFile(BytesIO(archive.content)) as zipped:
            assert sorted(zipped.namelist()) == ["9709_m26_ms_12.pdf", "9709_m26_qp_12.pdf"]
    assert not list(api.root.iterdir())


@pytest.mark.parametrize("path,extra", [("/paper-qa/resolve", {}), ("/paper-qa/query", {}), ("/api/v1/paper", {"download": "false"}), ("/api/v1/paper", {})])
@pytest.mark.parametrize("case,status", [("restricted", 403), ("ambiguous", 409), ("bad_metadata", 502)])
def test_existing_paperqa_errors_keep_status_and_detail_contract(api, monkeypatch, path, extra, case, status):
    if case == "restricted":
        records = [_record("/content/dam/secure/Economics/wec11-01-que-20240510.pdf")]
    elif case == "ambiguous":
        records = [_record(f"/content/dam/pdf/Economics/wec11-01-que-{date}.pdf") for date in ("20240510", "20240511")]
    else:
        records = [{"url": ["unexpected"], "category": []}]
    fetcher = FakeFetcher(records=records)
    _patch_fetcher(api, monkeypatch, fetcher)
    with TestClient(api.app) as client:
        response = client.get(path, params={**PEARSON_ARGS, **extra})
    assert response.status_code == status
    assert set(response.json()) == {"detail"}
    assert response.json()["detail"]
    assert not any(call[0] == "GET" for call in fetcher.calls)


@pytest.mark.parametrize("path,extra", [("/paper-qa/query", {}), ("/api/v1/paper", {}), ("/api/v1/paper", {"format": "json"})])
@pytest.mark.parametrize("status,data,expected", [(403, b"restricted", 403), (302, b"redirect", 403), (500, b"error", 502), (200, b"not-a-pdf", 502)])
def test_download_errors_are_http_errors(api, monkeypatch, path, extra, status, data, expected):
    _patch_fetcher(api, monkeypatch, FakeFetcher(status=status, data=data))
    with TestClient(api.app) as client:
        response = client.get(path, params={**CIE_ARGS, **extra})
    assert response.status_code == expected
    assert set(response.json()) == {"detail"}


@pytest.mark.parametrize("path,extra", [("/paper-qa/resolve", {}), ("/paper-qa/query", {}), ("/api/v1/paper", {"download": "false"}), ("/api/v1/paper", {"format": "json"})])
def test_malformed_numeric_upstream_is_502(api, monkeypatch, path, extra):
    _patch_fetcher(api, monkeypatch, FakeFetcher(catalogue={"rows": [], "total": float("inf")}))
    with TestClient(api.app) as client:
        response = client.get(path, params={**CIE_ARGS, **extra})
    assert response.status_code == 502
    assert response.json() == {"detail": "Invalid upstream response"}


@pytest.mark.parametrize("error_type", [AttributeError, IndexError, KeyError, TypeError, ValueError])
def test_raw_upstream_shape_exceptions_do_not_leak_details(api, monkeypatch, error_type):
    fetcher = FakeFetcher(error=error_type("private-upstream-shape-details"))
    _patch_fetcher(api, monkeypatch, fetcher)
    with TestClient(api.app) as client:
        for path, extra in [("/paper-qa/resolve", {}), ("/paper-qa/query", {}), ("/api/v1/paper", {"download": "false"}), ("/api/v1/paper", {"format": "json"})]:
            response = client.get(path, params={**CIE_ARGS, **extra})
            assert response.status_code == 502
            assert response.json() == {"detail": "Invalid upstream response"}
            assert "private-upstream" not in response.text


def test_invalid_parameters_fail_before_upstream_calls(api, monkeypatch):
    fetcher = FakeFetcher()
    _patch_fetcher(api, monkeypatch, fetcher)
    with TestClient(api.app) as client:
        for extra in ({"format": "xml"}, {"board": "ocr"}, {"year": 1999}):
            response = client.get("/api/v1/paper", params={**CIE_ARGS, **extra})
            assert response.status_code == 422
            assert set(response.json()) == {"detail"}
    assert not fetcher.calls
