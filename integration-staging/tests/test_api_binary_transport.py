"""A11 - the five binary routes over the default staged app (plan 5.3).

The store/serving primitives are unit-tested in `test_api_binary_store.py`;
this module pins the wire contract of the GET/HEAD routes against the default
app: verified bytes only, strong etags and If-None-Match, single byte ranges
(206) and unsatisfiable ranges (416), HEAD, the failure envelope
(404/405/409/413/422), provenance headers, budgets and the guarantee that a
streamed crop leaves no temp directory behind.

Private synthetic fixtures and the in-process test client only: no network,
no original module, no live service.
"""
from __future__ import annotations

import json
import shutil

import pytest
from fastapi.testclient import TestClient

from examdata_integration.api import dataset as dataset_module
from examdata_integration.api.app import create_app
from examdata_integration.api.binary import ContentLimits, ContentStore
from examdata_integration.api.dataset import default_dataset

BINARY_FIXTURES = dataset_module.FIXTURE_ROOT / "binary"
MANIFEST_PATH = BINARY_FIXTURES / "manifest.json"


@pytest.fixture(scope="module")
def app():
    return create_app()


@pytest.fixture(scope="module")
def client(app) -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="module")
def store(app):
    return app.state.content_store


@pytest.fixture(scope="module")
def dataset():
    return default_dataset()


@pytest.fixture(scope="module")
def revision(client) -> str:
    return client.get("/api/v2/info").json()["data"]["dataset_revision"]


@pytest.fixture(scope="module")
def asset(dataset, store):
    entry = dataset.entries("asset")[0]
    sample = store.for_asset(entry.system, entry.identity_fields.get("sha256"))
    assert sample is not None, "fixture drifted: first asset has no content sample"
    return entry, sample


def _question(client, dataset, system: str, native_id: str) -> str:
    for entry in dataset.entries("question"):
        if entry.system == system and entry.native_locator.get("native_id") == native_id:
            public_id = entry.public_id
            break
    else:
        raise AssertionError(f"no {system!r} question fixture with native id {native_id!r}")
    detail = client.get(f"/api/v2/questions/{public_id}")
    assert detail.status_code == 200, public_id
    return public_id


# -- 200/HEAD ---------------------------------------------------------------- #
def test_asset_content_serves_the_verified_bytes(client, asset, revision) -> None:
    entry, sample = asset
    response = client.get(f"/api/v2/assets/{entry.public_id}/content",
                          headers={"x-request-id": "req-a11-echo"})
    assert response.status_code == 200
    assert response.content == sample.path.read_bytes()
    assert len(response.content) == sample.byte_size
    assert response.headers["content-type"] == "image/png"
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["etag"] == f'"{sample.sha256}"'
    assert response.headers["x-content-sha256"] == sample.sha256
    assert response.headers["x-evidence"] == "synthetic_fixture"
    assert response.headers["x-dataset-revision"] == revision
    assert response.headers["content-disposition"] == \
        f'inline; filename="{entry.public_id}.png"'
    assert response.headers["content-length"] == str(sample.byte_size)
    assert response.headers["x-request-id"] == "req-a11-echo"


def test_head_matches_get_without_a_body(client, asset) -> None:
    entry, sample = asset
    url = f"/api/v2/assets/{entry.public_id}/content"
    head = client.head(url)
    assert head.status_code == 200
    assert head.content == b""
    assert head.headers["content-length"] == str(sample.byte_size)
    assert head.headers["etag"] == f'"{sample.sha256}"'
    # HEAD ignores Range in the staged transport: 200 with the full length
    ranged = client.head(url, headers={"range": "bytes=0-9"})
    assert ranged.status_code == 200
    assert ranged.headers["content-length"] == str(sample.byte_size)


def test_resource_content_aliases_asset_content(client, asset) -> None:
    entry, sample = asset
    response = client.get(f"/api/v2/resources/{entry.public_id}/content")
    assert response.status_code == 200
    assert response.content == sample.path.read_bytes()


def test_syllabus_and_material_content_serve_pdf(client) -> None:
    syllabus = client.get("/api/v2/syllabuses/syl_synthetic_cie_0580/content")
    assert syllabus.status_code == 200
    assert syllabus.content.startswith(b"%PDF-")
    assert syllabus.headers["content-type"] == "application/pdf"
    assert syllabus.headers["content-disposition"] == \
        'inline; filename="syl_synthetic_cie_0580.pdf"'
    material = client.get("/api/v2/materials/mat_synthetic_cie_ins/content")
    assert material.status_code == 200
    assert material.content.startswith(b"%PDF-")


# -- ranges and etags -------------------------------------------------------- #
def test_single_ranges_return_206_with_exact_content_ranges(client, asset) -> None:
    entry, sample = asset
    blob = sample.path.read_bytes()
    url = f"/api/v2/assets/{entry.public_id}/content"

    first = client.get(url, headers={"range": "bytes=0-9"})
    assert first.status_code == 206
    assert first.content == blob[:10]
    assert first.headers["content-range"] == f"bytes 0-9/{sample.byte_size}"
    assert first.headers["content-length"] == "10"

    tail = client.get(url, headers={"range": "bytes=-10"})
    assert tail.status_code == 206
    assert tail.content == blob[-10:]
    assert tail.headers["content-range"] == \
        f"bytes {sample.byte_size - 10}-{sample.byte_size - 1}/{sample.byte_size}"

    open_end = client.get(url, headers={"range": "bytes=10-"})
    assert open_end.status_code == 206
    assert open_end.content == blob[10:]
    assert open_end.headers["content-range"] == f"bytes 10-{sample.byte_size - 1}/{sample.byte_size}"

    rest = client.get(url, headers={"range": f"bytes=10-{sample.byte_size - 1}"})
    assert first.content + rest.content == blob


def test_unsatisfiable_ranges_are_416_and_malformed_ranges_stay_200(client, asset) -> None:
    entry, sample = asset
    url = f"/api/v2/assets/{entry.public_id}/content"
    response = client.get(url, headers={"range": f"bytes={sample.byte_size + 1}-"})
    assert response.status_code == 416
    payload = response.json()
    assert payload["data"] is None
    assert payload["error"]["code"] == "range_not_satisfiable"
    assert response.headers["content-range"] == f"bytes */{sample.byte_size}"
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["etag"] == f'"{sample.sha256}"'

    zero = client.get(url, headers={"range": "bytes=-0"})
    assert zero.status_code == 416

    ignored = client.get(url, headers={"range": "bytes=5-3"})
    assert ignored.status_code == 200
    assert ignored.content == sample.path.read_bytes()


def test_if_none_match_returns_304_without_a_body(client, asset) -> None:
    entry, sample = asset
    url = f"/api/v2/assets/{entry.public_id}/content"
    etag = f'"{sample.sha256}"'
    for value in (etag, f"W/{etag}", f'"other", {etag}'):
        response = client.get(url, headers={"if-none-match": value})
        assert response.status_code == 304
        assert response.content == b""
        assert "content-length" not in response.headers
        assert response.headers["etag"] == etag
    fresh = client.get(url, headers={"if-none-match": '"other"'})
    assert fresh.status_code == 200


# -- failure modes ----------------------------------------------------------- #
def test_method_and_query_guards(client, asset) -> None:
    entry, _ = asset
    url = f"/api/v2/assets/{entry.public_id}/content"
    post = client.post(url)
    assert post.status_code == 405
    assert post.json()["error"]["code"] == "method_not_allowed"
    filtered = client.get(url, params={"limit": 1})
    assert filtered.status_code == 422
    assert filtered.json()["error"]["code"] == "unsupported_filter"


def test_unknown_identities_and_missing_samples_are_404(client) -> None:
    cases = [
        ("/api/v2/assets/asset_does_not_exist/content", "not_found"),
        ("/api/v2/syllabuses/syl_does_not_exist/content", "not_found"),
        ("/api/v2/syllabuses/syl_synthetic_ielts_book/content", "content_not_available"),
        ("/api/v2/materials/mat_does_not_exist/content", "not_found"),
        ("/api/v2/materials/mat_synthetic_edexcel_gt/content", "content_not_available"),
    ]
    for path, code in cases:
        response = client.get(path)
        assert response.status_code == 404, path
        payload = response.json()
        assert payload["data"] is None, path
        assert payload["error"]["code"] == code, path


def test_question_crop_serves_the_png_with_provenance_headers(
        client, dataset, store) -> None:
    question_id = _question(client, dataset, "cie", "1")
    sample = store.crop_for("cie", "1")
    assert sample is not None
    response = client.get(f"/api/v2/questions/{question_id}/crop")
    assert response.status_code == 200
    assert response.content == sample.path.read_bytes()
    assert response.headers["content-type"] == "image/png"
    assert response.headers["content-disposition"] == \
        f'inline; filename="{question_id}.png"'
    assert response.headers["x-document-sha256"] == "2" * 64
    assert response.headers["x-page"] == "2"

    ranged = client.get(f"/api/v2/questions/{question_id}/crop",
                        headers={"range": "bytes=0-99"})
    assert ranged.status_code == 206
    assert ranged.content == sample.path.read_bytes()[:100]
    assert ranged.headers["content-range"] == f"bytes 0-99/{sample.byte_size}"
    assert ranged.headers["x-page"] == "2"


def test_crop_gaps_and_regionless_questions_are_typed_errors(client, dataset) -> None:
    no_crop = _question(client, dataset, "cie", "1(a)")
    missing = client.get(f"/api/v2/questions/{no_crop}/crop")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "crop_not_available"

    regionless = _question(client, dataset, "ielts", "Q1")
    response = client.get(f"/api/v2/questions/{regionless}/crop")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsupported_capability"

    unknown = client.get("/api/v2/questions/q_does_not_exist/crop")
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "not_found"


def test_a_streamed_crop_leaves_no_temp_directory_behind(
        client, dataset, store) -> None:
    question_id = _question(client, dataset, "cie", "1")
    tmp_root = store.temp_root
    before = {p.name for p in tmp_root.iterdir() if p.name.startswith("crop-")}
    assert client.get(f"/api/v2/questions/{question_id}/crop").status_code == 200
    assert client.get(f"/api/v2/questions/{question_id}/crop",
                      headers={"range": "bytes=0-99"}).status_code == 206
    after = {p.name for p in tmp_root.iterdir() if p.name.startswith("crop-")}
    assert after == before


# -- budgets and evidence conflicts ------------------------------------------ #
@pytest.fixture(scope="module")
def tiny_app():
    store = ContentStore(BINARY_FIXTURES, MANIFEST_PATH,
                         limits=ContentLimits(max_total_bytes=100,
                                              max_crop_bytes=50))
    assert store.ok, store.problems
    return create_app(content_store=store)


def test_budgets_surface_as_413(tiny_app, asset, dataset) -> None:
    entry, sample = asset
    small = TestClient(tiny_app)
    too_large = small.get(f"/api/v2/assets/{entry.public_id}/content")
    assert too_large.status_code == 413
    payload = too_large.json()
    assert payload["data"] is None
    assert payload["error"]["code"] == "response_budget_exceeded"
    assert payload["error"]["details"]["limit"] == 100
    assert payload["error"]["details"]["byte_size"] == sample.byte_size

    question_id = _question(small, dataset, "cie", "1")
    crop = small.get(f"/api/v2/questions/{question_id}/crop")
    assert crop.status_code == 413
    assert crop.json()["error"]["code"] == "crop_budget_exceeded"


@pytest.mark.parametrize("change,code", [
    ({"declared_document_sha256": "9" * 64}, "hash_conflict"),
    ({"page": 7}, "region_conflict"),
])
def test_crop_evidence_conflicts_surface_as_409(tmp_path, change, code) -> None:
    root = tmp_path / "binary"
    shutil.copytree(BINARY_FIXTURES, root)
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    target = next(entry for entry in manifest["crops"]
                  if entry["system"] == "cie" and entry["native_id"] == "1")
    target.update(change)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    store = ContentStore(root, manifest_path)
    assert store.ok, store.problems
    launched = create_app(content_store=store)
    question_id = _question(TestClient(launched), default_dataset(), "cie", "1")
    response = TestClient(launched).get(f"/api/v2/questions/{question_id}/crop")
    assert response.status_code == 409
    payload = response.json()
    assert payload["data"] is None
    assert payload["error"]["code"] == code
