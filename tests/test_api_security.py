from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient
from starlette.requests import Request

from examdata.api.security import _application_path, install_security


@pytest.fixture(autouse=True)
def security_environment(monkeypatch):
    monkeypatch.delenv("EXAMDATA_API_KEY", raising=False)
    monkeypatch.delenv("EXAMDATA_CORS_ORIGINS", raising=False)


def _secured_app() -> FastAPI:
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/private")
    def private():
        return {"status": "private"}

    @app.get("/docs-note")
    def docs_note():
        return PlainTextResponse("docs-note")

    install_security(app)
    return app


@pytest.mark.parametrize("value", [None, ""])
def test_security_is_opt_in(monkeypatch, value):
    if value is not None:
        monkeypatch.setenv("EXAMDATA_API_KEY", value)
    monkeypatch.setenv("EXAMDATA_CORS_ORIGINS", " , \t, ")
    app = _secured_app()
    assert not app.user_middleware
    with TestClient(app) as client:
        response = client.get("/private", headers={"Origin": "https://client.example"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize("prefix", ["", "/proxy"])
def test_api_key_exempts_exact_route_paths_with_root_path(monkeypatch, prefix):
    monkeypatch.setenv("EXAMDATA_API_KEY", "test-key")
    app = _secured_app()

    with TestClient(app, root_path=prefix) as client:
        for path in ("/health", "/docs", "/redoc", "/openapi.json"):
            assert client.get(prefix + path).status_code == 200
        assert client.get("/health").status_code == 200
        for path in ("/private", "/docs-note", "/health-extra", "/health/private"):
            denied = client.get(prefix + path)
            assert denied.status_code == 401
            assert set(denied.json()) == {"detail"}
            assert denied.headers["www-authenticate"] == "X-API-Key"
        assert client.get(prefix + "/private", headers={"X-API-Key": "wrong"}).status_code == 401
        assert client.get(prefix + "/private", headers={"X-API-Key": "test-key"}).status_code == 200
        assert client.get(prefix + "/private", headers={"X-API-Key": b"\xff"}).status_code == 401


@pytest.mark.parametrize(
    "path,root_path,expected",
    [
        ("/proxy/health", "/proxy", "/health"),
        ("/health", "/proxy", "/health"),
        ("/proxy-other/health", "/proxy", "/proxy-other/health"),
    ],
)
def test_root_path_is_removed_only_at_a_path_boundary(path, root_path, expected):
    request = Request({"type": "http", "path": path, "root_path": root_path})
    assert _application_path(request) == expected


def test_mounted_application_keeps_exemptions(monkeypatch):
    monkeypatch.setenv("EXAMDATA_API_KEY", "test-key")
    parent = FastAPI()
    parent.mount("/mounted", _secured_app())
    with TestClient(parent) as client:
        assert client.get("/mounted/health").status_code == 200
        assert client.get("/mounted/openapi.json").status_code == 200
        assert client.get("/mounted/private").status_code == 401


def test_api_key_is_captured_when_security_is_installed(monkeypatch):
    monkeypatch.setenv("EXAMDATA_API_KEY", "test-key")
    app = _secured_app()
    monkeypatch.setenv("EXAMDATA_API_KEY", "replacement-key")
    with TestClient(app) as client:
        assert client.get("/private", headers={"X-API-Key": "test-key"}).status_code == 200
        assert client.get("/private", headers={"X-API-Key": "replacement-key"}).status_code == 401


def test_cors_is_outermost_and_preflight_bypasses_api_key(monkeypatch):
    monkeypatch.setenv("EXAMDATA_API_KEY", "test-key")
    monkeypatch.setenv("EXAMDATA_CORS_ORIGINS", " https://client.example , https://second.example ")
    app = _secured_app()

    with TestClient(app) as client:
        preflight = client.options(
            "/private",
            headers={
                "Origin": "https://client.example",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-API-Key",
            },
        )
        assert preflight.status_code == 200
        assert preflight.headers["access-control-allow-origin"] == "https://client.example"
        assert "x-api-key" in preflight.headers["access-control-allow-headers"].lower()

        denied = client.get("/private", headers={"Origin": "https://client.example"})
        assert denied.status_code == 401
        assert denied.headers["access-control-allow-origin"] == "https://client.example"
        unlisted = client.get("/private", headers={"Origin": "https://other.example"})
        assert unlisted.status_code == 401
        assert "access-control-allow-origin" not in unlisted.headers
        non_preflight = client.options("/private")
        assert non_preflight.status_code == 401


def test_wildcard_cors_without_authentication(monkeypatch):
    monkeypatch.setenv("EXAMDATA_CORS_ORIGINS", "*")
    with TestClient(_secured_app()) as client:
        response = client.get("/private", headers={"Origin": "https://any.example"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
