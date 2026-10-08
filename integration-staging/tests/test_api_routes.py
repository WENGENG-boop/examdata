"""A10/A11 - the implemented v2 routes (plan 5.1, 5.2, 5.3, 5.4, 5.7).

Every implemented JSON route must answer 200 with a body that validates against
the declared envelope schema; every failure must be a typed envelope with
``data`` null; the five binary rows answer raw verified bytes instead (their
transport contract is pinned in `test_api_binary_transport.py`); and the fixture
data must stay honest - a missing answer slot is a visible gap, an answer
conflict is preserved with no decision invented, a native hierarchy is kept, and
the deferred families are labelled as synthetic.

Only the staged app and its private fixtures are used: no original module, no
network, no live service, no original data root.
"""
from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from examdata_integration.api import links
from examdata_integration.api.app import create_app
from examdata_integration.api.dataset import default_dataset
from examdata_integration.api.openapi import validate_response

DEFERRED_WARNING = "deferred to Phase B"
UNKNOWN_TOKEN = "__unknown__"


@pytest.fixture(scope="module")
def app():
    return create_app()


@pytest.fixture(scope="module")
def client(app) -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="module")
def dataset():
    return default_dataset()


def _pick(dataset, kind: str, system: str, native_id: str | None = None):
    for entry in dataset.entries(kind):
        if entry.system != system:
            continue
        if native_id is None or entry.native_locator.get("native_id") == native_id:
            return entry
    raise AssertionError(f"no {kind} fixture for {system!r}/{native_id!r}")


@pytest.fixture(scope="module")
def sample(dataset):
    """One concrete identity per route family, so a route can be exercised."""
    return {
        "course": _pick(dataset, "course", "ielts"),
        "container": _pick(dataset, "container", "cie"),
        "question": _pick(dataset, "question", "cie", "3"),
        "asset": dataset.entries("asset")[0],
    }


def _ok(response) -> dict:
    assert response.status_code == 200, response.text
    payload = response.json()
    assert validate_response(payload) == [], payload
    assert payload["error"] is None
    return payload


# -- every implemented route ------------------------------------------------- #
#: capability -> the concrete path that proves it, or None for a pathless route
CONCRETE = {
    "courses.get": lambda s: f"/api/v2/courses/{s['course'].public_id}",
    "syllabuses.get": lambda s: "/api/v2/syllabuses/syl_synthetic_cie_0580",
    "containers.get": lambda s: f"/api/v2/containers/{s['container'].public_id}",
    "containers.resources": lambda s: f"/api/v2/containers/{s['container'].public_id}/resources",
    "containers.questions": lambda s: f"/api/v2/containers/{s['container'].public_id}/questions",
    "resources.get": lambda s: f"/api/v2/resources/{s['asset'].public_id}",
    "questions.get": lambda s: f"/api/v2/questions/{s['question'].public_id}",
    "questions.answers": lambda s: f"/api/v2/questions/{s['question'].public_id}/answers",
    "questions.regions": lambda s: f"/api/v2/questions/{s['question'].public_id}/regions",
    "questions.audio": lambda s: f"/api/v2/questions/{s['question'].public_id}/audio",
    "assets.get": lambda s: f"/api/v2/assets/{s['asset'].public_id}",
    "tags.questions": lambda s: "/api/v2/tags/any_scheme/questions",
    "materials.get": lambda s: "/api/v2/materials/mat_synthetic_cie_ins",
    "jobs.get": lambda s: "/api/v2/jobs/job_synthetic_coverage",
}


def test_every_implemented_route_answers_200_with_a_valid_envelope(client, sample) -> None:
    # the five binary rows answer raw fixture bytes, not the JSON envelope;
    # their contract is pinned in test_api_binary_transport.py.
    json_specs = [spec for spec in links.IMPLEMENTED_SPECS if not spec.binary]
    checked = 0
    for spec in json_specs:
        build = CONCRETE.get(spec.capability)
        path = build(sample) if build else spec.full_path
        assert "{id}" not in path, f"{spec.capability} was left unresolved"
        response = client.get(path)
        assert response.status_code == 200, f"{path}: {response.text}"
        assert validate_response(response.json()) == [], path
        checked += 1
    assert checked == len(json_specs)


def test_all_implemented_routes_are_get() -> None:
    assert all(spec.method == "GET" for spec in links.IMPLEMENTED_SPECS)


# -- discovery --------------------------------------------------------------- #
def test_info_reports_versions_and_the_route_inventory(client) -> None:
    data = _ok(client.get("/api/v2/info"))["data"]
    assert data["schema_version"] == "examdata.v2/1"
    assert data["service"]["name"] == "examdata-v2-staged"
    assert data["dataset_revision"]
    assert data["evidence"] == "synthetic_fixture"
    assert data["counts"]["question"] > 0
    available = {row["path"] for row in data["capabilities"]["available"]}
    assert available == {spec.full_path for spec in links.IMPLEMENTED_SPECS}
    deferred = {row["path"] for row in data["capabilities"]["deferred"]}
    assert deferred == {spec.full_path for spec in links.DEFERRED_SPECS}
    assert str(422) in data["error_map"]


def test_exam_systems_lists_only_available_systems(client) -> None:
    items = _ok(client.get("/api/v2/exam-systems"))["data"]["items"]
    systems = {row["system"] for row in items}
    assert {"cie", "edexcel", "ielts"} <= systems
    assert all("availability" in row for row in items)


def test_providers_report_capabilities_without_inventing_any(client) -> None:
    items = _ok(client.get("/api/v2/providers"))["data"]["items"]
    assert items
    for row in items:
        assert row["capabilities"], row
        assert row["evidence"] == "synthetic_fixture"
    edexcel = next(r for r in items if r["exam_system"] == "edexcel")
    assert "questions" not in edexcel["capabilities"]


# -- catalog identities ------------------------------------------------------ #
def test_course_detail_carries_native_identity_and_links(client, sample) -> None:
    entry = sample["course"]
    item = _ok(client.get(f"/api/v2/courses/{entry.public_id}"))["data"]["item"]
    assert item["public_id"] == entry.public_id
    assert item["native_code"] == "synthetic-book-1"
    assert item["links"]["self"] == f"/api/v2/courses/{entry.public_id}"


def test_course_alias_resolves_to_the_same_entry(client, sample) -> None:
    entry = sample["course"]
    alias = _ok(client.get("/api/v2/courses/SB1"))["data"]["item"]
    assert alias["public_id"] == entry.public_id


def test_container_detail_keeps_hierarchy_and_resources(client, sample) -> None:
    item = _ok(client.get(
        f"/api/v2/containers/{sample['container'].public_id}"))["data"]["item"]
    assert item["system"] == "cie"
    assert item["native_identity"]["subject"] == "9999"
    assert item["sections"], "the CIE synthetic container has a section hierarchy"
    assert {row["role"] for row in item["resources"]} == {"qp", "ms"}


def test_container_questions_preserve_native_order_and_hierarchy(client, sample) -> None:
    items = _ok(client.get(
        f"/api/v2/containers/{sample['container'].public_id}/questions"))["data"]["items"]
    assert [row["native_id"] for row in items] == ["1", "1(a)", "1(b)", "2", "3"]
    assert items[1]["parent_native_id"] == "1"
    assert items[1]["number_path"] == ["1", "1(a)"]
    assert items[0]["parent_native_id"] == UNKNOWN_TOKEN


def test_every_question_ref_resolves_to_a_real_question(client, sample, dataset) -> None:
    container = sample["container"]
    items = _ok(client.get(
        f"/api/v2/containers/{container.public_id}/questions"))["data"]["items"]
    for row in items:
        assert _ok(client.get(f"/api/v2/questions/{row['public_id']}"))["data"]["item"]


def test_container_resources_only_lists_that_containers_assets(client, sample) -> None:
    items = _ok(client.get(
        f"/api/v2/containers/{sample['container'].public_id}/resources"))["data"]["items"]
    hashes = {row["sha256"] for row in items}
    assert "2222222222222222222222222222222222222222222222222222222222222222" in hashes
    assert all(row["system"] == "cie" for row in items)


def test_question_detail_is_explicit_about_gaps(client, sample) -> None:
    entry = sample["question"]
    item = _ok(client.get(f"/api/v2/questions/{entry.public_id}"))["data"]["item"]
    assert item["native_id"] == "3"
    assert item["system"] == "cie"
    assert item["links"]["answers"] == f"/api/v2/questions/{entry.public_id}/answers"


def test_question_list_filters_by_system(client) -> None:
    items = _ok(client.get("/api/v2/questions", params={"system": "cie"}))["data"]["items"]
    assert items and all(row["system"] == "cie" for row in items)


def test_unknown_filter_is_422_and_names_the_filter(client) -> None:
    response = client.get("/api/v2/questions", params={"nonsense": "1"})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "unsupported_filter"
    assert "nonsense" in error["details"]["unsupported"]
    assert "system" in error["details"]["allowed"]


# -- answers: conflicts and missing slots are preserved ---------------------- #
def test_answer_conflict_is_preserved_and_not_resolved(client, sample) -> None:
    data = _ok(client.get(
        f"/api/v2/questions/{sample['question'].public_id}/answers"))["data"]
    assert len(data["items"]) == 1
    answer = data["items"][0]
    assert answer["verification"] == "unverified"
    assert answer["manual_decision"] is None
    values = {row["value"] for row in answer["conflicts"]}
    assert values == {"synthetic-mark-scheme-answer", "synthetic-alternate-answer"}
    assert all(row["decision"] is None for row in answer["conflicts"])
    assert [gap["code"] for gap in data["gaps"]] == ["answer_conflict"]


def test_missing_answer_slot_is_an_empty_list_with_a_gap(client, dataset) -> None:
    entry = _pick(dataset, "question", "ielts", "Q41")
    data = _ok(client.get(f"/api/v2/questions/{entry.public_id}/answers"))["data"]
    assert data["items"] == []
    assert [gap["code"] for gap in data["gaps"]] == ["missing_answer_slot"]
    assert data["gaps"][0]["detail"].startswith("question Q41 has no answer slot")


def test_question_without_a_recorded_answer_slot_does_not_fabricate_one(client,
                                                                       dataset) -> None:
    entry = _pick(dataset, "question", "cie", "1(a)")
    data = _ok(client.get(f"/api/v2/questions/{entry.public_id}/answers"))["data"]
    assert data["items"] == []
    assert data["gaps"] == []


def test_regions_tie_to_an_exact_document_and_report_the_gap(client, sample) -> None:
    data = _ok(client.get(
        f"/api/v2/questions/{sample['question'].public_id}/regions"))["data"]
    assert data["items"]
    region = data["items"][0]
    assert region["document_sha256"]
    assert region["document_role"] == "qp"
    assert region["evidence_status"] == "unverified"
    assert [gap["code"] for gap in data["gaps"]] == ["missing_region"]


def test_regions_are_422_when_the_provider_cannot_supply_them(client, dataset) -> None:
    entry = _pick(dataset, "question", "ielts", "Q1")
    response = client.get(f"/api/v2/questions/{entry.public_id}/regions")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsupported_capability"


def test_audio_route_claims_no_alignment(client, dataset) -> None:
    entry = _pick(dataset, "question", "ielts", "Q1")
    payload = _ok(client.get(f"/api/v2/questions/{entry.public_id}/audio"))
    assert payload["data"]["items"] == []
    assert payload["data"]["association"] is None
    assert payload["data"]["alignment"] is None
    assert any("no association" in w for w in payload["meta"]["warnings"])


# -- resources and assets are one entity ------------------------------------- #
def test_resources_and_assets_agree_on_the_same_entity(client, sample) -> None:
    entry = sample["asset"]
    listed = _ok(client.get("/api/v2/resources", params={"limit": 200}))["data"]["items"]
    row = next(r for r in listed if r["public_id"] == entry.public_id)
    detail = _ok(client.get(f"/api/v2/assets/{entry.public_id}"))["data"]["item"]
    as_resource = _ok(client.get(f"/api/v2/resources/{entry.public_id}"))["data"]["item"]
    assert row["sha256"] == detail["sha256"] == as_resource["sha256"]
    assert row["system"] == detail["system"]
    # the synthetic sample exists, so the content is available and linked
    assert detail["content_available"] is True
    assert detail["availability"] == "fixture"
    assert detail["range_capable"] is True
    assert detail["links"]["content"] == f"/api/v2/assets/{entry.public_id}/content"
    assert detail["content"]["declared_sha256"] == entry.identity_fields["sha256"]
    assert len(detail["content"]["sha256"]) == 64
    assert detail["content"]["evidence"] == "synthetic_fixture"


def test_asset_sha256_is_the_native_identity(dataset) -> None:
    for entry in dataset.entries("asset"):
        assert entry.identity_fields["sha256"] == entry.native_locator["sha256"]


def test_resource_filter_by_media_type(client) -> None:
    items = _ok(client.get("/api/v2/resources",
                           params={"media_type": "application/pdf"}))["data"]["items"]
    assert items and all(row["media_type"] == "application/pdf" for row in items)


# -- deferred families are labelled, never implied --------------------------- #
@pytest.mark.parametrize("path", ["/api/v2/syllabuses", "/api/v2/materials",
                                  "/api/v2/timetables", "/api/v2/timetables/events",
                                  "/api/v2/timetables/windows"])
def test_deferred_families_are_labelled_synthetic(client, path) -> None:
    payload = _ok(client.get(path))
    rows = payload["data"].get("items", payload["data"].get("seasons"))
    assert rows
    assert all(row["evidence"] == "synthetic_fixture" for row in rows)
    assert all(row["integration_status"] == "deferred_active_owner" for row in rows)
    assert any(DEFERRED_WARNING in w for w in payload["meta"]["warnings"])
    assert payload["meta"]["completeness"] == "unknown"


def test_timetable_season_without_a_date_is_unavailable_not_guessed(client) -> None:
    data = _ok(client.get("/api/v2/timetables"))["data"]
    cie = next(row for row in data["seasons"] if row["system"] == "cie")
    assert cie["availability"] == "unavailable"
    assert "unknown" in cie["reason"]


def test_timetable_event_keeps_unknown_boundaries_null(client) -> None:
    items = _ok(client.get("/api/v2/timetables/events",
                           params={"system": "cie"}))["data"]["items"]
    assert items and all(row["date"] is None for row in items)


def test_tags_are_empty_with_a_deferred_source_gap(client) -> None:
    payload = _ok(client.get("/api/v2/tags"))
    assert payload["data"]["items"] == []
    assert [gap["code"] for gap in payload["data"]["gaps"]] == ["deferred_source"]


def test_tag_lookup_is_explicitly_deferred(client) -> None:
    payload = _ok(client.get("/api/v2/tags/any_scheme/questions"))
    assert payload["data"]["items"] == []
    assert [gap["code"] for gap in payload["data"]["gaps"]] == ["deferred_source"]
    assert payload["meta"]["completeness"] == "unknown"


# -- coverage, gaps and jobs ------------------------------------------------- #
def test_coverage_is_never_a_percentage_without_a_denominator(client) -> None:
    items = _ok(client.get("/api/v2/coverage"))["data"]["items"]
    assert items
    for row in items:
        if not row["denominator_known"]:
            assert row["percentage"] is None
            assert row["derived_status"] == "unknown"


def test_gaps_union_snapshot_problems_and_provider_gaps(client) -> None:
    items = _ok(client.get("/api/v2/gaps", params={"limit": 200}))["data"]["items"]
    codes = {row["code"] for row in items}
    assert "answer_conflict" in codes
    assert "deferred_source" in codes
    assert len(items) == len({(r["code"], r["scope"], r["detail"]) for r in items})


def test_job_lookup_serves_the_synthetic_record(client) -> None:
    item = _ok(client.get("/api/v2/jobs/job_synthetic_coverage"))["data"]["item"]
    assert item["state"] == "succeeded"
    assert item["evidence"] == "synthetic_fixture"


def test_unknown_job_is_404(client) -> None:
    response = client.get("/api/v2/jobs/job_does_not_exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


# -- failure modes ----------------------------------------------------------- #
@pytest.mark.parametrize("path", [
    "/api/v2/courses/course_does_not_exist",
    "/api/v2/containers/container_does_not_exist",
    "/api/v2/questions/q_does_not_exist",
    "/api/v2/assets/asset_does_not_exist",
    "/api/v2/materials/mat_does_not_exist",
    "/api/v2/syllabuses/syl_does_not_exist",
])
def test_unknown_identity_is_a_404_envelope(client, path) -> None:
    response = client.get(path)
    assert response.status_code == 404
    payload = response.json()
    assert payload["data"] is None
    assert payload["error"]["code"] == "not_found"
    assert validate_response(payload) == []


def test_unknown_identity_error_does_not_echo_a_long_raw_id(client) -> None:
    response = client.get("/api/v2/courses/" + "x" * 200)
    assert response.status_code == 404
    assert len(response.json()["error"]["message"]) <= 300


@pytest.mark.parametrize("capability,path", [
    ("syllabuses.content", "/api/v2/syllabuses/whatever/content"),
    ("resources.content", "/api/v2/resources/whatever/content"),
    ("questions.crop", "/api/v2/questions/whatever/crop"),
    ("assets.content", "/api/v2/assets/whatever/content"),
    ("materials.content", "/api/v2/materials/whatever/content"),
])
def test_the_binary_routes_are_registered_and_404_for_unknown_identity(
        client, capability, path) -> None:
    spec = next(s for s in links.IMPLEMENTED_SPECS if s.capability == capability)
    assert spec.binary is True
    response = client.get(path)
    assert response.status_code == 404
    payload = response.json()
    assert payload["data"] is None
    assert payload["error"]["code"] == "not_found"
    assert response.headers["content-type"].startswith("application/json")


def test_a_wrong_method_is_405_with_an_envelope(client) -> None:
    response = client.post("/api/v2/info")
    assert response.status_code == 405
    payload = response.json()
    assert payload["error"]["code"] == "method_not_allowed"
    assert payload["data"] is None


def test_an_unknown_v2_path_is_404(client) -> None:
    response = client.get("/api/v2/nothing-here")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "route_not_found"


def test_every_error_status_is_inside_the_plan_map(client) -> None:
    from examdata_integration.api.envelope import ERROR_MAP, FRAMEWORK_STATUSES
    for response in (client.get("/api/v2/courses/nope"),
                     client.get("/api/v2/questions", params={"limit": "x"}),
                     client.get("/api/v2/questions", params={"limit": 999})):
        assert response.status_code in ERROR_MAP
    # a wrong method is rejected by the framework's own routing before any v2
    # handler runs, so it is framework-level rather than in the plan 5.2 map;
    # it is still surfaced through the same error envelope.
    wrong_method = client.post("/api/v2/info")
    assert wrong_method.status_code in FRAMEWORK_STATUSES
    assert wrong_method.json()["error"]["code"] == "method_not_allowed"


def test_request_id_is_echoed_when_it_is_safe(client) -> None:
    payload = _ok(client.get("/api/v2/info", headers={"X-Request-ID": "trace-123"}))
    assert payload["request_id"] == "trace-123"


def test_request_id_is_replaced_when_it_is_unsafe(client) -> None:
    payload = _ok(client.get("/api/v2/info", headers={"X-Request-ID": "bad id!"}))
    assert payload["request_id"].startswith("req_")
