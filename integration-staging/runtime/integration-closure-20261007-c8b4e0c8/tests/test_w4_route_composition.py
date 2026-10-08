"""W4a: v2 routes compose into a host app and the legacy baseline is intact.

Three seams are pinned here, all read-only:

* ``attach_v2`` registers the staged v2 routes inside a synthetic host without
  disturbing one byte of the host's own behaviour (its routes, its 404 body,
  its plain-text 500), while every ``/api/v2`` path answers with the staged
  envelope and the staged routing errors;
* the staged app's operation IDs are unique, deterministic across builds and
  across interpreter processes, and survive composition unchanged -- the A14
  document-regeneration contract depends on exactly that;
* static child routes and parameterised ``{id}`` routes resolve in the
  registered order, so ``/timetables/events`` is the events route while
  ``/containers/events`` is the containers detail route reporting ``not_found``;
* the A12 legacy decision registry still carries the 71 recorded baseline rows
  with the worksheet's status/mechanism counts, and ``legacy_error`` preserves
  the recorded status.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

import b07r2_common as c  # noqa: F401  (first import pins the candidate root)
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from examdata.integration.api import links
from examdata.integration.api.app import create_app
from examdata.integration.api.compose import attach_v2
from examdata.integration.api.dataset import default_dataset
from examdata.integration.api.envelope import SCHEMA_VERSION
from examdata.integration.legacy import decisions, translate

DATASET = default_dataset(operations_root=None)

#: The recorded A12 worksheet this run validates against (read-only).
WORKSHEET_PATH = Path(
    "C:/Users/weo/Desktop/api/docs/integration/execution/"
    "A12_ROUTE_COMPATIBILITY_WORKSHEET.json")

EXPECTED_MECHANISMS = {
    "add_v2_adapter_keep_legacy_defaults": 21,
    "keep_legacy_only": 16,
    "keep_legacy_namespace": 7,
    "bridge_node_cli_keep_legacy_payload": 20,
    "deferred_active_owner": 7,
}
EXPECTED_STATUSES = {"staged_pass": 64, "deferred_active_owner": 7}
EXPECTED_BASELINE_ROWS = 71


def _operations(app):
    """Every documented operation as ``(METHOD, path, operationId)``."""
    rows = []
    for path, operations in app.openapi()["paths"].items():
        for method, operation in operations.items():
            rows.append((method.upper(), path, operation.get("operationId")))
    return rows


def _json(response):
    assert response.status_code == 200, (
        response.request.url.path, response.status_code, response.text[:300])
    return response.json()


def _synthetic_host():
    host = FastAPI(title="w4a synthetic host")

    @host.get("/health")
    def health():
        return {"ok": True, "host": "legacy"}

    @host.get("/boom")
    def boom():
        raise RuntimeError("w4a synthetic host failure")

    return host


def test_attach_v2_keeps_host_behaviour_and_serves_v2_envelope():
    host = _synthetic_host()
    attach_v2(host)

    # The host's own route order is kept: its operations come first.
    assert list(host.openapi()["paths"])[:2] == ["/health", "/boom"]

    with TestClient(host, raise_server_exceptions=False) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json() == {"ok": True, "host": "legacy"}

        courses = _json(client.get("/api/v2/courses"))
        assert set(courses) == {"schema_version", "request_id", "data",
                                "meta", "error"}
        assert courses["schema_version"] == SCHEMA_VERSION
        assert courses["error"] is None
        assert set(courses["meta"]) == {
            "dataset_revision", "retrieved_at", "pagination", "completeness",
            "warnings", "providers"}

        unknown_v2 = client.get("/api/v2/does-not-exist")
        assert unknown_v2.status_code == 404
        assert unknown_v2.json()["error"]["code"] == "route_not_found"

        events = client.get("/api/v2/timetables/events")
        assert events.status_code == 200

        captured = client.get("/api/v2/containers/events")
        assert captured.status_code == 404
        assert captured.json()["error"]["code"] == "not_found"

        legacy_404 = client.get("/does-not-exist")
        assert legacy_404.status_code == 404
        assert legacy_404.json() == {"detail": "Not Found"}

        legacy_500 = client.get("/boom")
        assert legacy_500.status_code == 500
        assert legacy_500.text == "Internal Server Error"
        assert legacy_500.headers["content-type"].startswith("text/plain")


def test_attach_v2_refuses_invalid_second_and_late_attach():
    with pytest.raises(TypeError):
        attach_v2(object())

    host = _synthetic_host()
    attach_v2(host)
    with pytest.raises(RuntimeError):
        attach_v2(host)

    late = FastAPI()
    with TestClient(late) as client:
        client.get("/")
    with pytest.raises(RuntimeError):
        attach_v2(late)


def test_operation_ids_are_unique_deterministic_and_composed():
    rows = _operations(create_app(dataset=DATASET))
    again = _operations(create_app(dataset=DATASET))
    assert rows == again

    assert Counter(method for method, _, _ in rows) == {"GET": 34, "HEAD": 5}
    ids = [operation_id for _, _, operation_id in rows]
    assert all(ids)
    assert len(set(ids)) == len(ids) == 39

    implemented = [spec for spec in links.ROUTE_SPECS if spec.implemented]
    assert len(implemented) == 34
    binary = [spec for spec in implemented if spec.binary]
    assert len(binary) == 5
    pairs = {(method, path) for method, path, _ in rows}
    for spec in implemented:
        assert ("GET", spec.full_path) in pairs
    for spec in binary:
        assert ("HEAD", spec.full_path) in pairs

    host = _synthetic_host()
    attach_v2(host)
    host_v2 = sorted(row for row in _operations(host)
                     if row[1].startswith(links.PREFIX))
    assert host_v2 == sorted(rows)

    # Cross-process determinism: a fresh interpreter (arbitrary cwd, only the
    # candidate on PYTHONPATH) documents exactly the same operations.
    code = (
        "import json\n"
        "from examdata.integration.api.app import create_app\n"
        "doc = create_app().openapi()\n"
        "rows = [[m.upper(), p, op.get('operationId')]\n"
        "        for p, ops in doc['paths'].items() for m, op in ops.items()]\n"
        "print(json.dumps(sorted(rows)))\n")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(c.EXPECTED_ROOT / "src")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["EXAMDATA_INTEGRATION_ROOT"] = str(c.EXPECTED_ROOT)
    proc = subprocess.run([sys.executable, "-B", "-c", code],
                          capture_output=True, text=True, encoding="utf-8",
                          cwd=str(c.EXPECTED_ROOT), env=env, timeout=240)
    assert proc.returncode == 0, proc.stderr[-500:]
    assert [tuple(row) for row in json.loads(proc.stdout)] == sorted(rows)


def test_static_and_parameterised_routes_resolve_in_order():
    client = TestClient(create_app(dataset=DATASET))

    for path in ("/api/v2/timetables/events", "/api/v2/timetables/windows"):
        payload = _json(client.get(path))
        assert payload["error"] is None, path

    captured = client.get("/api/v2/containers/events")
    assert captured.status_code == 404
    assert captured.json()["error"]["code"] == "not_found"

    captured_sub = client.get("/api/v2/questions/does-not-exist/answers")
    assert captured_sub.status_code == 404
    assert captured_sub.json()["error"]["code"] == "not_found"

    unknown = client.get("/api/v2/does-not-exist")
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "route_not_found"


def test_legacy_registry_matches_recorded_worksheet():
    assert decisions.baseline_count() == EXPECTED_BASELINE_ROWS
    assert dict(decisions.mechanism_counts()) == EXPECTED_MECHANISMS
    assert dict(decisions.status_counts()) == EXPECTED_STATUSES

    registry_file = c.EXPECTED_ROOT / "src/examdata/integration/legacy/registry.json"
    expected_sha = hashlib.sha256(registry_file.read_bytes()).hexdigest()
    assert decisions.registry_sha256() == expected_sha
    assert len(expected_sha) == 64

    worksheet = json.loads(WORKSHEET_PATH.read_text(encoding="utf-8"))
    assert worksheet["schema"] == (
        "examdata.integration.route_compatibility_worksheet/2")
    summary = worksheet["summary"]
    assert summary["row_count"] == EXPECTED_BASELINE_ROWS
    assert summary["baseline_coverage"] == "71/71"
    assert summary["status_counts"] == dict(decisions.status_counts())
    assert summary["mechanism_counts"] == dict(decisions.mechanism_counts())
    assert summary["coverage_kind_counts"] == (
        decisions.coverage_summary()["by_coverage_kind"])

    worksheet_rows = {row["row_id"]: row for row in worksheet["rows"]}
    registry_rows = {row["row_id"]: row for row in decisions.rows()}
    assert len(worksheet_rows) == EXPECTED_BASELINE_ROWS
    assert set(worksheet_rows) == set(registry_rows)
    # Detail text was decoded from the legacy sources and may be mangled by
    # encoding; only the decision tokens must agree row for row.
    disagreements = [
        rid for rid, row in registry_rows.items()
        if (worksheet_rows[rid]["status"], worksheet_rows[rid]["mechanism"])
        != (row["status"], row["mechanism"])
    ]
    assert disagreements == []


def test_legacy_error_preserves_the_recorded_status():
    for status in (200, 400, 404, 409, 422, 500, 502, 503, 504):
        assert translate.legacy_error(status, "recorded detail") == {
            "status_code": status, "detail": "recorded detail"}
    with pytest.raises(TypeError):
        translate.legacy_error("503", "recorded detail")
