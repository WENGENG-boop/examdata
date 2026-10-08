import copy
import hashlib
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from examdata.api import unified
from examdata.paperqa.api import index_paper
from examdata.paperqa.external_index import fetch_question, import_index, read_index
from examdata.paperqa import query
from examdata.paperqa.errors import AmbiguousDocument
from test_paperqa import FakeFetcher, pdf_bytes


@pytest.mark.parametrize("board,subject,paper", [("cie", "9709", "12"), ("edexcel", "Economics", "wec11-01")])
@pytest.mark.parametrize("mode,roles", [("qp", {"qp"}), ("ms", {"ms"}), ("both", {"qp", "ms"})])
def test_shared_modes(board, subject, paper, mode, roles):
    result = query(board, subject, 2026, "Mar" if board == "cie" else "Jun", paper, mode=mode, fetcher=FakeFetcher())
    assert {file.role for file in result.files} == roles
    assert all(file.media_type == "application/pdf" for file in result.files)


@pytest.mark.parametrize("mode,roles", [("qp", {"qp"}), ("ms", {"ms"}), ("both", {"qp", "ms"})])
def test_edexcel_shared_modes_crop(mode, roles):
    result = query("edexcel", "Economics", 2024, "Jun", "wec11-01", "2(a)", mode, fetcher=FakeFetcher())
    assert {file.role for file in result.files} == roles
    assert all(file.media_type == "image/png" and file.page == 2 and file.bbox for file in result.files)


def test_edexcel_whole_index():
    fetcher = FakeFetcher()
    result = index_paper("Economics", 2024, "Jun", "wec11-01", fetcher=fetcher)
    assert [q["question"] for q in result["questions"]] == ["1", "2", "2(a)", "2(a)(i)", "2(a)(ii)", "2(b)"]
    assert result["reviewed"] is False
    for q in result["questions"]:
        assert q["qp"] and q["ms"]
        assert q["qp"][0]["page"] == 2
        assert q["qp"][0]["sha256"] == hashlib.sha256(fetcher.data).hexdigest()


def test_index_does_not_merge_paper_variants(monkeypatch):
    import dataclasses
    from examdata.paperqa import api
    result = query("edexcel", "Economics", 2024, "Jun", "wec11-01", mode="both", fetcher=FakeFetcher())
    result.documents.append(dataclasses.replace(result.documents[0], paper="wec11-02"))
    monkeypatch.setattr(api, "query", lambda *a, **kw: result)
    with pytest.raises(AmbiguousDocument):
        api.index_paper("Economics", 2024, "Jun", "wec11")


@pytest.fixture
def external(tmp_path):
    data = pdf_bytes()
    qp = tmp_path / "qp.pdf"
    qp.write_bytes(data)
    sha = hashlib.sha256(data).hexdigest()
    payload = {"schema_version": "1", "board": "cie",
        "identity": {"subject": "9709", "year": 2026, "season": "Mar", "paper": "12"},
        "coordinate_system": "unrotated_pdf_points_top_left", "page_base": 1,
        "documents": [{"role": "qp", "sha256": sha}],
        "questions": [{"question": "1", "parent": None, "text": "First question", "marks": None,
                       "qp": [{"page": 2, "bbox": [40, 80, 500, 200]}],
                       "ms": [], "uncertain": True, "notes": ""}]}
    manifest = tmp_path / "index.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    return tmp_path, manifest, qp, sha, payload


def test_import_roundtrip_and_no_overwrite(external):
    root, manifest, qp, sha, payload = external
    result = import_index(manifest, qp, None, root)
    assert result["reviewed"] is False
    assert import_index(manifest, qp, None, root) == result
    assert read_index(root, sha, "1")["questions"][0]["text"] == "First question"
    payload["questions"][0]["text"] = "changed"
    manifest.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="already exists"):
        import_index(manifest, qp, None, root)
    assert read_index(root, sha)["questions"][0]["text"] == "First question"
    assert not list(Path(result["path"]).parent.glob("*.part"))


@pytest.mark.parametrize("problem", ["hash", "page", "bbox", "nan", "duplicate", "parent", "ms", "extra"])
def test_reject_bad_external_without_writes(external, problem):
    root, manifest, qp, sha, payload = external
    q = payload["questions"][0]
    if problem == "hash": payload["documents"][0]["sha256"] = "a" * 64
    elif problem == "page": q["qp"][0]["page"] = 100
    elif problem == "bbox": q["qp"][0]["bbox"][2] = 10000
    elif problem == "nan": q["qp"][0]["bbox"][0] = float("nan")
    elif problem == "duplicate": payload["questions"].append(copy.deepcopy(q))
    elif problem == "parent": q["question"] = "1(a)"
    elif problem == "ms": q["ms"] = copy.deepcopy(q["qp"])
    else: payload["reviewed"] = True
    manifest.write_text(json.dumps(payload))
    with pytest.raises(ValueError): import_index(manifest, qp, None, root)
    assert not (root / "question_indexes").exists()


def test_cie_index_read_api_and_algorithm_refusal(external, monkeypatch):
    root, manifest, qp, sha, payload = external
    import_index(manifest, qp, None, root)
    monkeypatch.setattr(unified, "get_settings", lambda: type("Config", (), {"data_dir": root})())
    from examdata.paperqa import external_index
    original_fetch = external_index.fetch_question
    monkeypatch.setattr(external_index, "fetch_question", lambda *a: original_fetch(*a, fetcher=FakeFetcher(data=qp.read_bytes())))
    app = FastAPI()
    app.include_router(unified.router)
    with TestClient(app) as client:
        r = client.get(f"/api/v1/indexes/cie/{sha}", params={"question": "1"})
        assert r.status_code == 200 and r.json()["reviewed"] is False
        assert client.get(f"/api/v1/indexes/cie/{sha}?question=99").status_code == 404
        assert client.get("/api/v1/indexes/cie/invalid").status_code == 422
        crop = client.get(f"/api/v1/indexes/cie/{sha}/question", params={"question": "1", "format": "json"})
        assert crop.status_code == 200, crop.text
        assert crop.json()["source_documents"][0]["sha256"] == sha
        assert crop.json()["files"][0]["page"] == 2
        assert client.get(f"/api/v1/indexes/cie/{sha}/question?question=1").content.startswith(b"\x89PNG")
        assert client.get(f"/api/v1/indexes/cie/{sha}/question?question=1&mode=ms").status_code == 404
        assert client.get("/api/v1/paper/index", params={"board": "cie", "subject": "9709", "year": 2026, "season": "Mar", "paper": "12"}).status_code == 422


def test_import_cli(external, monkeypatch):
    from typer.testing import CliRunner
    from examdata import cli
    root, manifest, qp, sha, payload = external
    monkeypatch.setattr(cli, "get_settings", lambda: type("Config", (), {"data_dir": root})())
    result = CliRunner().invoke(cli.app, ["import-cie-index", str(manifest), "--qp", str(qp)])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["sha256"] == sha
    assert read_index(root, sha)["reviewed"] is False


def test_fetch_cie_regions_in_memory_only(external):
    root, manifest, qp, sha, payload = external
    import_index(manifest, qp, None, root)
    before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    result, provenance = fetch_question(root, sha, "1", fetcher=FakeFetcher(data=qp.read_bytes()))
    assert provenance["source_documents"][0]["sha256"] == sha
    assert result.files[0].data.startswith(b"\x89PNG")
    assert result.files[0].page == 2 and result.files[0].bbox == (40, 80, 500, 200)
    assert before == {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_changed_source_refuses_old_coordinates(external):
    root, manifest, qp, sha, payload = external
    import_index(manifest, qp, None, root)
    with pytest.raises(AmbiguousDocument, match="changed"):
        fetch_question(root, sha, "1", fetcher=FakeFetcher(data=qp.read_bytes() + b"\n"))


def test_missing_ms_never_generates_answer(external):
    from examdata.paperqa.errors import NotFound
    root, manifest, qp, sha, payload = external
    import_index(manifest, qp, None, root)
    with pytest.raises(NotFound, match="not indexed"):
        fetch_question(root, sha, "1", mode="ms", fetcher=FakeFetcher())


def test_unified_download_and_index_http(monkeypatch):
    app = FastAPI()
    app.include_router(unified.router)
    from examdata.paperqa.api import index_paper as run_index
    monkeypatch.setattr(unified, "paperqa_query", lambda *args: query(*args, fetcher=FakeFetcher()))
    monkeypatch.setattr(unified, "index_paper", lambda *args: run_index(*args, fetcher=FakeFetcher()))
    with TestClient(app) as client:
        params = {"board": "edexcel", "subject": "Economics", "year": 2024, "season": "Jun", "paper": "wec11-01", "mode": "both"}
        r = client.get("/api/v1/paper", params={**params, "question": "2(a)", "format": "json"})
        assert r.status_code == 200, r.text
        assert {f["role"] for f in r.json()["files"]} == {"qp", "ms"}
        assert client.get("/api/v1/paper/index", params=params).json()["questions"][0]["question"] == "1"
        assert client.get("/api/v1/cie-index-schema").json()["properties"]["board"]["const"] == "cie"
