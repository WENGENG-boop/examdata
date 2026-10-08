"""A10/A11 - the route registry, the OpenAPI document and the runtime agree.

`links.py` is the single source of truth for the v2 route table; `app.py`
registers exactly the implemented rows; and `openapi.py` proves the three views
match. Since A11 every plan 5.4 row is implemented, the five binary
content/crop rows included, and every link a payload publishes must resolve to
a route that actually answers 200 (422 only where a provider lacks the
capability) - a client must never be handed a link into an unavailable feature.
"""
from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from examdata_integration.api import links
from examdata_integration.api.app import create_app
from examdata_integration.api.dataset import default_dataset
from examdata_integration.api.envelope import BINARY_STATUSES, ERROR_MAP
from examdata_integration.api.openapi import (
    ENVELOPE_SCHEMA,
    agreement_problems,
    iter_routes,
    runtime_head_pairs,
    runtime_pairs,
    spec_envelope_schemas,
    spec_pairs,
    validate_response,
)


@pytest.fixture(scope="module")
def app():
    return create_app()


@pytest.fixture(scope="module")
def client(app) -> TestClient:
    return TestClient(app)


# -- the registry ------------------------------------------------------------ #
def test_registry_covers_the_plan_route_table() -> None:
    # 34 plan 5.4 rows, all implemented since packet A11 staged the binary rows
    assert len(links.ROUTE_SPECS) == 34
    assert len(links.IMPLEMENTED_SPECS) == 34
    assert len(links.DEFERRED_SPECS) == 0
    assert set(links.IMPLEMENTED_SPECS) | set(links.DEFERRED_SPECS) == set(links.ROUTE_SPECS)


def test_registry_paths_are_unique_and_prefixed() -> None:
    paths = [spec.full_path for spec in links.ROUTE_SPECS]
    assert len(paths) == len(set(paths))
    assert all(path.startswith("/api/v2/") for path in paths)
    assert all(spec.path == spec.full_path[len(links.PREFIX):] for spec in links.ROUTE_SPECS)


def test_every_binary_row_is_implemented_and_registered(app) -> None:
    binary = [spec for spec in links.ROUTE_SPECS if spec.binary]
    assert len(binary) == 5
    assert all(spec.implemented for spec in binary)
    assert links.DEFERRED_SPECS == ()
    served = runtime_pairs(app)
    for spec in binary:
        assert (spec.method, spec.full_path) in served
        assert spec.media_types, spec.capability
    assert runtime_head_pairs(app) == {("HEAD", spec.full_path) for spec in binary}


def test_capability_lookup_is_exact() -> None:
    assert links.spec_for("info").full_path == "/api/v2/info"
    with pytest.raises(KeyError):
        links.spec_for("not_a_capability")


def test_advertised_links_exclude_every_deferred_route() -> None:
    advertised = {row["path"] for row in links.advertised()}
    deferred = {row["path"] for row in links.deferred()}
    assert advertised == {spec.full_path for spec in links.IMPLEMENTED_SPECS}
    assert not advertised & deferred


# -- the runtime and the document -------------------------------------------- #
def test_runtime_matches_the_registry_exactly(app) -> None:
    assert runtime_pairs(app) == links.advertised_pairs()


def test_openapi_matches_the_registry_exactly(app) -> None:
    assert spec_pairs(app) == links.advertised_pairs()


def test_no_deferred_route_is_registered_at_runtime(app) -> None:
    served = runtime_pairs(app)
    for spec in links.DEFERRED_SPECS:
        assert (spec.method, spec.full_path) not in served


def test_no_deferred_route_appears_in_the_document(app) -> None:
    documented = spec_pairs(app)
    for spec in links.DEFERRED_SPECS:
        assert (spec.method, spec.full_path) not in documented


def test_agreement_checker_reports_nothing(app) -> None:
    assert agreement_problems(app) == []


def test_framework_meta_routes_are_disabled(app) -> None:
    served = runtime_pairs(app)
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert not any(p == path for _, p in served)


def test_iter_routes_descends_into_included_routers(app) -> None:
    # Starlette wraps an included router, so a flat walk of app.routes would see
    # nothing: the helper must find the real endpoints.
    assert len(list(iter_routes(app.routes))) >= len(links.IMPLEMENTED_SPECS)


# -- the declared response schema -------------------------------------------- #
def test_every_documented_json_200_uses_the_envelope_schema(app) -> None:
    schemas = spec_envelope_schemas(app)
    json_rows = [spec for spec in links.IMPLEMENTED_SPECS if not spec.binary]
    assert len(schemas) == len(json_rows)
    for operation, schema in schemas.items():
        assert schema == ENVELOPE_SCHEMA, operation


def test_documented_binary_200_documents_the_fixture_media_only(app) -> None:
    document = app.openapi()
    for spec in (s for s in links.ROUTE_SPECS if s.binary):
        operation = document["paths"][spec.full_path]["get"]
        content = operation["responses"]["200"]["content"]
        assert set(content) == set(spec.media_types), spec.capability
        assert "application/json" not in content
        assert "application/json" not in operation["responses"]["206"]["content"]
        documented = set(operation["responses"])
        assert {"200", "206", "304", "413", "416"} <= documented, spec.capability


def test_documented_error_statuses_are_from_the_plan(app) -> None:
    document = app.openapi()
    for path, operations in document["paths"].items():
        for method, operation in operations.items():
            for status in operation["responses"]:
                assert int(status) in ERROR_MAP or int(status) in BINARY_STATUSES, (
                    f"{method.upper()} {path} -> {status}")


def test_envelope_schema_rejects_a_wrong_shape() -> None:
    assert validate_response({"schema_version": "examdata.v2/1"}) != []
    assert validate_response([]) != []
    assert validate_response({
        "schema_version": "examdata.v2/1", "request_id": "r", "data": None,
        "meta": {"dataset_revision": None, "retrieved_at": None,
                 "pagination": {"limit": None, "next_cursor": None},
                 "completeness": "unknown", "warnings": [], "providers": []},
        "error": None}) == []


def test_envelope_schema_forbids_unknown_keys() -> None:
    payload = {"schema_version": "examdata.v2/1", "request_id": "r", "data": None,
               "meta": {"dataset_revision": None, "retrieved_at": None,
                        "pagination": {"limit": None, "next_cursor": None},
                        "completeness": "unknown", "warnings": [], "providers": []},
               "error": None, "extra": 1}
    assert validate_response(payload) != []


# -- links a payload publishes must resolve ---------------------------------- #
def test_every_published_link_resolves_to_a_200(client) -> None:
    dataset = default_dataset()
    targets: set[str] = set()
    for kind in ("course", "container", "question", "asset"):
        for entry in dataset.entries(kind):
            targets.update(links.entry_links(kind, entry.public_id).values())
    assert targets
    for target in sorted(targets):
        response = client.get(target)
        # entry_links is route-level (it names implemented routes only). A
        # provider may still lack the capability a sub-route needs, so a
        # capability-gated sub-route answers 422 unsupported_capability rather
        # than 200. Anything else is a defect.
        assert response.status_code in (200, 422), f"{target}: {response.text}"
        if response.status_code == 422:
            body = response.json()
            assert body["error"]["code"] == "unsupported_capability", target


def test_entry_links_only_name_implemented_routes(app) -> None:
    templates = {spec.full_path for spec in links.IMPLEMENTED_SPECS}
    for kind in ("course", "container", "question", "asset"):
        for href in links.entry_links(kind, "PLACEHOLDER").values():
            assert href.replace("PLACEHOLDER", "{id}") in templates, href


def test_info_links_resolve_and_never_name_a_deferred_route(client) -> None:
    data = client.get("/api/v2/info").json()["data"]
    deferred = {row["path"] for row in data["capabilities"]["deferred"]}
    for row in data["capabilities"]["available"]:
        assert row["path"] not in deferred
        concrete = row["path"].replace("{id}", "job_synthetic_coverage")
        assert client.get(concrete).status_code in (200, 404, 422)
