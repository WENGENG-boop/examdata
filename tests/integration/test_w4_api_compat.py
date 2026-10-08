"""W4a: API compatibility contract over the staged v2 surface (plan 5.1-5.4).

These tests run against the candidate's own synthetic fixtures through
``create_app``. They pin behaviour the product must keep while the explicit
production assembly seam lands: the response envelope across every route
family, typed errors, cursor/revision semantics, the binary transport
contract, filter allowlists (no URL proxy, no unknown-parameter silent
ignore), the partial-vs-total source-failure rule and the emitted status
vocabulary.
"""
from __future__ import annotations

import hashlib
import json

import b07r2_common as c  # noqa: F401  (first import pins the candidate root)
import pytest
from fastapi.testclient import TestClient

from examdata.integration.api import links, openapi
from examdata.integration.api.app import create_app, default_content_store
from examdata.integration.api.binary import ContentLimits, ContentStore
from examdata.integration.api.dataset import default_dataset
from examdata.integration.api.envelope import (
    BINARY_STATUSES,
    EMITTABLE_STATUSES,
    FRAMEWORK_STATUSES,
    SCHEMA_VERSION,
)
from examdata.integration.catalog.revision import make_cursor, parse_cursor
from examdata.integration.providers.capabilities import Capability
from examdata.integration.providers.fixtures import NullProvider
from w4a_common import (
    dataset_with_registry,
    empty_content_store,
    empty_registry,
    failing_provider,
    synthetic_registry,
)

DATASET = default_dataset(operations_root=None)
CLIENT = TestClient(create_app(dataset=DATASET))
STORE = default_content_store()

ENVELOPE_KEYS = {"schema_version", "request_id", "data", "meta", "error"}
META_KEYS = {"dataset_revision", "retrieved_at", "pagination", "completeness",
             "warnings", "providers"}


def _json(response):
    assert response.headers.get("content-type", "").startswith("application/json"), (
        response.status_code, response.headers)
    return response.json()


def _native_id(entry):
    return str(entry.identity_fields.get("native_id")
               or entry.native_locator.get("native_id"))


def _find_question(system, native_id):
    for entry in DATASET.entries("question"):
        if str(entry.system) == system and _native_id(entry) == native_id:
            return entry
    raise AssertionError(f"no {system} question with native id {native_id!r} in the fixture")


def _cie_asset(sha_prefix):
    for entry in DATASET.entries("asset"):
        if str(entry.system) == "cie" and str(
                entry.identity_fields.get("sha256", "")).startswith(sha_prefix):
            return entry
    raise AssertionError(f"no cie asset with sha prefix {sha_prefix!r}")


def _check_success(response):
    path = response.request.url.path
    assert response.status_code == 200, (path, response.status_code, response.text[:400])
    payload = _json(response)
    assert set(payload) == ENVELOPE_KEYS, path
    assert payload["schema_version"] == SCHEMA_VERSION
    assert isinstance(payload["request_id"], str) and payload["request_id"]
    assert payload["error"] is None, path
    assert set(payload["meta"]) == META_KEYS, path
    assert payload["meta"]["dataset_revision"] == DATASET.revision, path
    assert isinstance(payload["meta"]["completeness"], str) and payload["meta"]["completeness"]
    pagination = payload["meta"]["pagination"]
    assert set(pagination) == {"limit", "next_cursor"}, path
    assert pagination["limit"] is None or isinstance(pagination["limit"], int), path
    assert isinstance(payload["meta"]["providers"], list), path
    assert openapi.validate_response(payload) == [], path
    return payload


def _check_error(response, status, code):
    path = response.request.url.path
    assert response.status_code == status, (path, response.status_code, response.text[:400])
    payload = _json(response)
    assert set(payload) == ENVELOPE_KEYS, path
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["data"] is None, path
    assert payload["error"] is not None and payload["error"]["code"] == code, (
        path, payload["error"])
    assert payload["error"]["message"], path
    assert payload["meta"]["completeness"] == "unknown", path
    assert openapi.validate_response(payload) == [], path
    return payload


def _route_ids():
    """One concrete id per parameterised route, resolved from the fixture."""
    courses = _json(CLIENT.get("/api/v2/courses"))["data"]["items"]
    containers = _json(CLIENT.get("/api/v2/containers"))["data"]["items"]
    container_id = containers[0]["public_id"]
    resources = _json(CLIENT.get(
        f"/api/v2/containers/{container_id}/resources"))["data"]["items"]
    syllabuses = _json(CLIENT.get("/api/v2/syllabuses"))["data"]["items"]
    materials = _json(CLIENT.get("/api/v2/materials"))["data"]["items"]
    cie_question = _find_question("cie", "1")
    asset = _cie_asset("4444")
    return {
        "courses.get": courses[0]["public_id"],
        "syllabuses.get": syllabuses[0]["public_id"],
        "containers.get": container_id,
        "containers.resources": container_id,
        "containers.questions": container_id,
        "resources.get": resources[0]["public_id"],
        "questions.get": cie_question.public_id,
        "questions.answers": cie_question.public_id,
        "questions.regions": cie_question.public_id,
        "questions.audio": cie_question.public_id,
        "assets.get": asset.public_id,
        "tags.questions": "does-not-exist",
        "jobs.get": "job_synthetic_coverage",
        "materials.get": materials[0]["public_id"],
        "syllabuses.content": "syl_synthetic_cie_0580",
        "resources.content": resources[0]["public_id"],
        "questions.crop": cie_question.public_id,
        "assets.content": asset.public_id,
        "materials.content": "mat_synthetic_cie_ins",
    }


def _spec_path(spec, ids):
    """The concrete path for one spec: ids are needed only where `{id}` is."""
    if "{id}" in spec.path:
        return spec.full_path.format(id=ids[spec.capability])
    return spec.full_path


def test_every_json_route_family_serves_a_schema_valid_envelope():
    ids = _route_ids()
    json_specs = [spec for spec in links.IMPLEMENTED_SPECS if not spec.binary]
    assert len(json_specs) == len(links.ROUTE_SPECS) - 5
    for spec in json_specs:
        path = _spec_path(spec, ids)
        _check_success(CLIENT.get(path))


def test_info_advertises_exactly_the_linked_route_registry():
    payload = _check_success(CLIENT.get("/api/v2/info"))
    capabilities = payload["data"]["capabilities"]
    assert capabilities["available"] == links.advertised()
    assert capabilities["deferred"] == links.deferred() == []
    assert len(capabilities["available"]) == 34
    assert payload["data"]["evidence"] == "synthetic_fixture"


def test_exam_systems_mark_toefl_and_gaokao_unavailable():
    items = _check_success(CLIENT.get("/api/v2/exam-systems"))["data"]["items"]
    by_system = {row["system"]: row for row in items}
    for system in ("toefl", "gaokao"):
        row = by_system[system]
        assert row["availability"] == "unavailable"
        assert row["reason"]
        assert row["providers"] == []


@pytest.mark.parametrize("query,status,code", [
    ("/api/v2/courses/does-not-exist", 404, "not_found"),
    ("/api/v2/courses?nope=1", 422, "unsupported_filter"),
    ("/api/v2/courses?limit=abc", 400, "invalid_limit"),
    ("/api/v2/courses?limit=0", 422, "invalid_limit"),
    ("/api/v2/courses?limit=201", 422, "limit_exceeded"),
    ("/api/v2/does-not-exist", 404, "route_not_found"),
])
def test_typed_error_envelopes(query, status, code):
    _check_error(CLIENT.get(query), status, code)


def test_filters_and_methods_are_never_silently_ignored():
    payload = _check_error(CLIENT.get("/api/v2/courses?nope=1&other=2"),
                           422, "unsupported_filter")
    assert payload["error"]["details"]["unsupported"] == ["nope", "other"]
    assert payload["error"]["details"]["allowed"] == [
        "qualification", "query", "specification_version", "system"]

    # A wrong method is rejected by the router and still gets the envelope.
    _check_error(CLIENT.post("/api/v2/courses"), 405, "method_not_allowed")

    # A binary route accepts no query parameters at all - a URL-proxy style
    # parameter must never be consumed.
    _check_error(CLIENT.get("/api/v2/syllabuses/syl_synthetic_cie_0580/content?url=x"),
                 422, "unsupported_filter")
    _check_error(CLIENT.get("/api/v2/assets/asset_4fgmj24f44aqv3dnnwfrae3g4s5nmfdb"
                            "/content?target=x"), 422, "unsupported_filter")


def test_url_proxy_parameters_are_rejected_on_search_routes():
    for path in ("/api/v2/questions?url=http://example.com/x",
                 "/api/v2/resources?target=file:///etc/passwd",
                 "/api/v2/materials?download=http://example.com/x"):
        payload = _check_error(CLIENT.get(path), 422, "unsupported_filter")
        assert "unsupported" in payload["error"]["details"]


def test_cursor_pages_are_stable_and_revision_bound():
    first = CLIENT.get("/api/v2/courses", params={"limit": 1})
    page = _check_success(first)
    cursor = page["meta"]["pagination"]["next_cursor"]
    assert cursor

    def fetch(params):
        return CLIENT.get("/api/v2/courses", params=params)

    second = fetch({"limit": 1, "cursor": cursor})
    body = _check_success(second)
    assert len(body["data"]["items"]) == 1
    assert body["data"]["items"][0]["public_id"] != page["data"]["items"][0]["public_id"]

    replay = fetch({"limit": 1, "cursor": cursor})
    def _stable(payload):
        copy = json.loads(json.dumps(payload))
        copy.pop("request_id", None)
        copy["meta"].pop("retrieved_at", None)
        return copy
    assert _stable(replay.json()) == _stable(second.json())

    _check_error(fetch({"limit": 2, "cursor": cursor}), 400, "cursor_limit_mismatch")
    _check_error(fetch({"limit": 1, "cursor": cursor, "system": "cie"}),
                 400, "cursor_query_mismatch")
    _check_error(fetch({"limit": 1, "cursor": "not-a-cursor"}), 400, "invalid_cursor")

    parsed = parse_cursor(cursor)
    foreign = make_cursor(dataset_revision="rev-w4a-foreign-0000",
                          query=parsed["query"], sort=parsed["sort"],
                          last_key=parsed["last_key"], limit=parsed["limit"])
    _check_error(fetch({"limit": 1, "cursor": foreign}), 409, "stale_cursor")


def test_binary_transport_bytes_headers_ranges_and_304():
    cie1 = _find_question("cie", "1")
    asset = _cie_asset("4444")
    cases = [
        ("syllabus", f"/api/v2/syllabuses/syl_synthetic_cie_0580/content",
         STORE.for_syllabus("syl_synthetic_cie_0580")),
        ("material", "/api/v2/materials/mat_synthetic_cie_ins/content",
         STORE.for_material("mat_synthetic_cie_ins")),
        ("crop", f"/api/v2/questions/{cie1.public_id}/crop",
         STORE.crop_for("cie", "1")),
        ("asset", f"/api/v2/assets/{asset.public_id}/content",
         STORE.for_asset("cie", asset.identity_fields["sha256"])),
    ]
    for label, path, sample in cases:
        assert sample is not None, label
        response = CLIENT.get(path)
        assert response.status_code == 200, (label, response.status_code)
        body = response.content
        assert len(body) == sample.byte_size, label
        assert hashlib.sha256(body).hexdigest() == sample.sha256, label
        assert response.headers["content-type"] == sample.media_type, label
        assert response.headers["accept-ranges"] == "bytes", label
        assert response.headers["etag"] == f'"{sample.sha256}"', label
        assert response.headers["x-content-sha256"] == sample.sha256, label
        assert response.headers["x-evidence"] == "synthetic_fixture", label
        assert response.headers["x-dataset-revision"] == DATASET.revision, label

        head = CLIENT.head(path)
        assert head.status_code == 200 and head.content == b"", label
        assert int(head.headers["content-length"]) == sample.byte_size, label

        ranged = CLIENT.get(path, headers={"Range": "bytes=0-9"})
        assert ranged.status_code == 206, label
        assert ranged.headers["content-range"] == f"bytes 0-9/{sample.byte_size}", label
        assert ranged.content == body[:10], label

        cached = CLIENT.get(path, headers={"If-None-Match": f'"{sample.sha256}"'})
        assert cached.status_code == 304 and cached.content == b"", label

        exhausted = CLIENT.get(path, headers={"Range": f"bytes={sample.byte_size + 100}-"})
        assert exhausted.status_code == 416, label
        assert exhausted.headers["content-range"] == f"bytes */{sample.byte_size}", label
        _check_error(exhausted, 416, "range_not_satisfiable")


def test_binary_budgets_and_missing_samples_fail_closed(tmp_path):
    base = default_content_store()
    limited = ContentStore(base.root, base.manifest_path,
                           limits=ContentLimits(max_total_bytes=1, max_crop_bytes=1))
    client = TestClient(create_app(dataset=DATASET, content_store=limited))
    payload = _check_error(
        client.get("/api/v2/syllabuses/syl_synthetic_cie_0580/content"),
        413, "response_budget_exceeded")
    assert payload["error"]["details"]["limit"] == 1
    assert payload["error"]["details"]["byte_size"] > 1

    cie1 = _find_question("cie", "1")
    payload = _check_error(client.get(f"/api/v2/questions/{cie1.public_id}/crop"),
                           413, "crop_budget_exceeded")
    assert payload["error"]["details"]["limit"] == 1

    empty = empty_content_store(tmp_path / "w4a-empty-binary")
    starved = TestClient(create_app(dataset=DATASET, content_store=empty))
    for path, code in [
        ("/api/v2/syllabuses/syl_synthetic_cie_0580/content", "content_not_available"),
        ("/api/v2/materials/mat_synthetic_cie_ins/content", "content_not_available"),
        (f"/api/v2/questions/{cie1.public_id}/crop", "crop_not_available"),
    ]:
        _check_error(starved.get(path), 404, code)

    asset = _cie_asset("4444")
    _check_error(starved.get(f"/api/v2/assets/{asset.public_id}/content"),
                 404, "content_not_available")
    item = _json(starved.get(f"/api/v2/assets/{asset.public_id}"))["data"]["item"]
    assert item["content_available"] is False
    assert item["content_link"] is None
    assert "content" not in item["links"]
    links_out = _json(starved.get(f"/api/v2/questions/{cie1.public_id}"))["data"]["item"]["links"]
    assert "crop" not in links_out


def test_capability_links_only_claim_samples_that_exist():
    cie1 = _find_question("cie", "1")
    with_crop = _json(CLIENT.get(f"/api/v2/questions/{cie1.public_id}"))["data"]["item"]
    assert STORE.crop_for("cie", "1") is not None
    assert with_crop["links"]["crop"] == f"/api/v2/questions/{cie1.public_id}/crop"

    without = next(entry for entry in DATASET.entries("question")
                   if str(entry.system) == "cie"
                   and STORE.crop_for("cie", _native_id(entry)) is None)
    item = _json(CLIENT.get(f"/api/v2/questions/{without.public_id}"))["data"]["item"]
    assert "crop" not in item["links"]
    _check_error(CLIENT.get(f"/api/v2/questions/{without.public_id}/crop"),
                 404, "crop_not_available")

    asset = _cie_asset("4444")
    detail = _json(CLIENT.get(f"/api/v2/assets/{asset.public_id}"))["data"]["item"]
    assert detail["content_available"] is True
    assert detail["content_link"] == f"/api/v2/assets/{asset.public_id}/content"
    assert detail["links"]["content"] == detail["content_link"]
    assert detail["availability"] == "fixture"


def test_api_key_environment_marker_never_reaches_a_response(monkeypatch):
    marker = "sk-w4a-b07r2-marker-9f7e2a"
    monkeypatch.setenv("EXAMDATA_API_KEY", marker)
    for path in ("/api/v2/info", "/api/v2/courses", "/api/v2/exam-systems",
                 "/api/v2/coverage", "/api/v2/gaps"):
        response = CLIENT.get(path)
        assert response.status_code not in (401, 403, 503), path
        assert response.status_code == 200, path
        assert marker not in response.text, path


def test_partial_and_total_source_failure_are_distinct():
    partial = dataset_with_registry(synthetic_registry(
        failing_provider("w4a_fail", Capability.COVERAGE),
        NullProvider("w4a_empty_ok", capabilities=frozenset({Capability.COVERAGE})),
    ))
    payload = _check_success(TestClient(create_app(dataset=partial)).get("/api/v2/coverage"))
    assert payload["meta"]["completeness"] == "partial"
    assert "w4a_fail: failed" in payload["meta"]["warnings"]
    statuses = {row["provider_id"]: row["status"] for row in payload["meta"]["providers"]}
    assert statuses == {"w4a_fail": "failed", "w4a_empty_ok": "ok"}

    total = dataset_with_registry(synthetic_registry(
        failing_provider("w4a_fail_a", Capability.COVERAGE),
        failing_provider("w4a_fail_b", Capability.COVERAGE),
    ))
    payload = _check_error(TestClient(create_app(dataset=total)).get("/api/v2/coverage"),
                           502, "provider_failed")
    assert [row["provider_id"] for row in payload["error"]["details"]["providers"]] == [
        "w4a_fail_a", "w4a_fail_b"]
    assert "<path>" in payload["error"]["message"]
    assert "secret.db" not in json.dumps(payload)

    # A single-provider route dispatches the first provider for the system and
    # must fail closed too - never an empty 200 from a failed source.
    cie1 = _find_question("cie", "1")
    single = dataset_with_registry(synthetic_registry(
        failing_provider("w4a_answers_fail", Capability.ANSWERS),
        NullProvider("w4a_answers_ok", capabilities=frozenset({Capability.ANSWERS})),
    ))
    _check_error(TestClient(create_app(dataset=single)).get(
        f"/api/v2/questions/{cie1.public_id}/answers"), 502, "provider_failed")

    # No provider at all for a system: a typed 503, not an empty success.
    silent = dataset_with_registry(empty_registry())
    _check_error(TestClient(create_app(dataset=silent)).get(
        f"/api/v2/questions/{cie1.public_id}/answers"), 503, "provider_unavailable")


def test_partial_completeness_marks_list_families_without_losing_items():
    # The deferred fixture families answer 200 with completeness "unknown"
    # rather than pretending to be complete, and every season row states its
    # own unavailability with a reason instead of a guessed boundary.
    payload = _check_success(CLIENT.get("/api/v2/timetables"))
    assert payload["meta"]["completeness"] == "unknown"
    seasons = payload["data"]["seasons"]
    assert seasons
    for season in seasons:
        assert season["availability"] == "unavailable"
        assert season["reason"]

    payload = _check_success(CLIENT.get("/api/v2/jobs/job_synthetic_coverage"))
    assert payload["meta"]["completeness"] in ("unknown", "partial", "complete")


def test_job_record_is_a_labelled_static_fixture():
    payload = _check_success(CLIENT.get("/api/v2/jobs/job_synthetic_coverage"))
    item = payload["data"]["item"]
    assert item["public_id"] == "job_synthetic_coverage"
    assert item["evidence"] == "synthetic_fixture"
    assert item["integration_status"] == "deferred_active_owner"


def test_emitted_statuses_stay_in_the_documented_vocabulary():
    seen = set()
    ids = _route_ids()

    def record(response):
        seen.add(response.status_code)
        return response

    for spec in links.IMPLEMENTED_SPECS:
        path = _spec_path(spec, ids)
        if spec.binary:
            record(CLIENT.get(path))
        else:
            record(CLIENT.get(path))
    record(CLIENT.get("/api/v2/courses/does-not-exist"))
    record(CLIENT.get("/api/v2/courses?limit=abc"))
    record(CLIENT.get("/api/v2/courses?limit=0"))
    record(CLIENT.get("/api/v2/courses?limit=201"))
    record(CLIENT.get("/api/v2/does-not-exist"))
    record(CLIENT.post("/api/v2/courses"))
    record(CLIENT.get("/api/v2/courses", params={"limit": 1,
                                                 "cursor": "not-a-cursor"}))
    first = CLIENT.get("/api/v2/courses", params={"limit": 1})
    cursor = first.json()["meta"]["pagination"]["next_cursor"]
    parsed = parse_cursor(cursor)
    foreign = make_cursor(dataset_revision="rev-w4a-foreign-0000",
                          query=parsed["query"], sort=parsed["sort"],
                          last_key=parsed["last_key"], limit=parsed["limit"])
    record(CLIENT.get("/api/v2/courses", params={"limit": 1, "cursor": foreign}))
    sample = STORE.for_syllabus("syl_synthetic_cie_0580")
    record(CLIENT.get("/api/v2/syllabuses/syl_synthetic_cie_0580/content",
                      headers={"Range": "bytes=0-9"}))
    record(CLIENT.get("/api/v2/syllabuses/syl_synthetic_cie_0580/content",
                      headers={"If-None-Match": f'"{sample.sha256}"'}))
    record(CLIENT.get("/api/v2/syllabuses/syl_synthetic_cie_0580/content",
                      headers={"Range": f"bytes={sample.byte_size + 100}-"}))

    total = dataset_with_registry(synthetic_registry(
        failing_provider("w4a_vocab_fail", Capability.COVERAGE)))
    record(TestClient(create_app(dataset=total)).get("/api/v2/coverage"))
    silent = dataset_with_registry(empty_registry())
    record(TestClient(create_app(dataset=silent)).get("/api/v2/coverage"))

    allowed = EMITTABLE_STATUSES | FRAMEWORK_STATUSES | BINARY_STATUSES
    assert seen <= allowed, sorted(seen - allowed)
    assert 200 in seen
    missing = {401, 403, 410, 429, 504}
    assert not (seen & missing), sorted(seen & missing)
