from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from examdata.workspace import child_environment, main, repository_root


ROOT = Path(__file__).resolve().parents[1]


def test_workspace_resolves_actual_monorepo_paths():
    assert repository_root(ROOT) == ROOT
    env = child_environment(ROOT, 18801, 18800, 18802, "127.0.0.1")
    from examdata.api import ielts, toefl
    assert (Path(env["EXAMDATA_IELTS_DIR"]) / ielts._SCRIPT_NAME).is_file()
    assert (Path(env["EXAMDATA_TOEFL_DIR"]) / toefl._SCRIPT_NAME).is_file()
    assert Path(env["EXAMDATA_TIMETABLE_DIR"]).is_dir()
    assert env["EXAMDATA_URL"] == "http://127.0.0.1:18801"


def test_launcher_refuses_conflicting_ports_without_starting_processes():
    assert main(["--root", str(ROOT), "--port", "18800", "--api-port", "18800", "--check"]) == 1


def test_v2_default_does_not_serve_rehearsal_data(monkeypatch):
    from fastapi import FastAPI
    from examdata.integration.deployment import install
    monkeypatch.delenv("EXAMDATA_V2_FACTORY", raising=False)
    app = FastAPI()
    install(app)
    response = TestClient(app).get("/api/v2/courses")
    assert response.status_code == 503
    assert response.json()["fixture_fallback"] is False
    assert response.json()["error"]["code"] == "production_sources_not_configured"


def test_existing_typer_cli_survives_merge():
    from typer.testing import CliRunner
    from examdata.cli import app
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("workspace", "serve", "initdb", "question-crop", "import-cie-index"):
        assert command in result.output
