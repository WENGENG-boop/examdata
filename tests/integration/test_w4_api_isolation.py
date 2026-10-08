"""W4a: the read API performs no network, process or byte-serving side effects.

The product contract is that the staged v2 read surface only reads staged
in-process components (plan A10): a JSON request must never open a socket,
spawn a process, or touch the binary byte-serving paths, so a catalog search
or a detail read can never trigger a download, a crop copy or an external
call. This test instruments those exact seams with tripwires and walks every
JSON route; the binary routes are exercised by the transport tests instead
(they legitimately read staged sample bytes).
"""
from __future__ import annotations

import asyncio
import os
import socket
import subprocess

import b07r2_common as c  # noqa: F401  (first import pins the candidate root)
import pytest
from fastapi.testclient import TestClient

from examdata.integration.api import app as app_module
from examdata.integration.api import binary as binary_module
from examdata.integration.api import links
from examdata.integration.api.app import create_app, default_content_store
from examdata.integration.api.dataset import default_dataset

DATASET = default_dataset(operations_root=None)


def _json(response):
    assert response.status_code == 200, (
        response.request.url.path, response.status_code, response.text[:300])
    return response.json()


def _native_id(entry):
    return str(entry.identity_fields.get("native_id")
               or entry.native_locator.get("native_id"))


def _find_question(system, native_id):
    for entry in DATASET.entries("question"):
        if str(entry.system) == system and _native_id(entry) == native_id:
            return entry
    raise AssertionError(f"no {system} question with native id {native_id!r}")


def _cie_asset(sha_prefix):
    for entry in DATASET.entries("asset"):
        if str(entry.system) == "cie" and str(
                entry.identity_fields.get("sha256", "")).startswith(sha_prefix):
            return entry
    raise AssertionError(f"no cie asset with sha prefix {sha_prefix!r}")


def _json_route_paths(client):
    """One concrete path per non-binary route spec, resolved from the fixture."""
    courses = _json(client.get("/api/v2/courses"))["data"]["items"]
    containers = _json(client.get("/api/v2/containers"))["data"]["items"]
    container_id = containers[0]["public_id"]
    resources = _json(client.get(
        f"/api/v2/containers/{container_id}/resources"))["data"]["items"]
    syllabuses = _json(client.get("/api/v2/syllabuses"))["data"]["items"]
    materials = _json(client.get("/api/v2/materials"))["data"]["items"]
    cie_question = _find_question("cie", "1")
    asset = _cie_asset("4444")
    ids = {
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
    }
    paths = []
    for spec in links.IMPLEMENTED_SPECS:
        if spec.binary:
            continue
        if "{id}" in spec.path:
            paths.append(spec.full_path.format(id=ids[spec.capability]))
        else:
            paths.append(spec.full_path)
    return paths


def _install_tripwires(monkeypatch, hits):
    """Tripwire every forbidden side-effect seam; collect the hits per test."""

    def trip(name):
        def _fail(*args, **kwargs):
            hits.append(name)
            raise AssertionError(f"forbidden side effect attempted: {name}")
        return _fail

    monkeypatch.setattr(socket.socket, "connect", trip("socket.connect"))
    monkeypatch.setattr(socket.socket, "connect_ex", trip("socket.connect_ex"))
    monkeypatch.setattr(socket, "create_connection", trip("socket.create_connection"))
    monkeypatch.setattr(socket, "create_server", trip("socket.create_server"))
    for name in ("Popen", "run", "call", "check_call", "check_output"):
        monkeypatch.setattr(subprocess, name, trip(f"subprocess.{name}"))
    monkeypatch.setattr(os, "system", trip("os.system"))
    monkeypatch.setattr(os, "popen", trip("os.popen"))
    for name in [n for n in dir(os) if n.startswith("spawn")]:
        monkeypatch.setattr(os, name, trip(f"os.{name}"))
    monkeypatch.setattr(asyncio, "create_subprocess_shell",
                        trip("asyncio.create_subprocess_shell"))
    monkeypatch.setattr(asyncio, "create_subprocess_exec",
                        trip("asyncio.create_subprocess_exec"))
    for name in ("iter_sample", "iter_range", "iter_crop_copy"):
        monkeypatch.setattr(app_module, name, trip(f"app.{name}"))
    monkeypatch.setattr(binary_module.ContentStore, "sample_bytes",
                        trip("ContentStore.sample_bytes"))


@pytest.fixture()
def tripwires(monkeypatch):
    """Arm the tripwires directly (used only by the positive-control test)."""
    hits: list[str] = []
    _install_tripwires(monkeypatch, hits)
    return hits


@pytest.fixture()
def guarded_client(monkeypatch):
    """A live client whose event loop starts *before* the tripwires are armed.

    TestClient starts its blocking portal (and, on Windows, the asyncio event
    loop's own socketpair self-pipe) at ``__enter__``; arming the tripwires
    afterwards means only request-handling effects can trip them. The wires
    are lifted again before the client shuts down so teardown is never blamed
    on the test's own scaffolding.
    """
    hits: list[str] = []
    with TestClient(create_app(dataset=DATASET)) as client:
        _install_tripwires(monkeypatch, hits)
        try:
            yield client, hits
        finally:
            monkeypatch.undo()


def test_json_routes_never_touch_network_processes_or_byte_serving(guarded_client):
    client, hits = guarded_client
    for path in _json_route_paths(client):
        assert client.get(path).status_code == 200, path

    # Filtered searches, cursor paging and typed errors round out the request
    # shapes the surface accepts.
    for path, params in (
        ("/api/v2/questions", {"query": "paper"}),
        ("/api/v2/resources", {"query": "cie 2024"}),
        ("/api/v2/courses", {"system": "cie"}),
        ("/api/v2/materials", {"system": "cie"}),
    ):
        assert client.get(path, params=params).status_code == 200, (path, params)

    first = client.get("/api/v2/courses", params={"limit": 1})
    cursor = first.json()["meta"]["pagination"]["next_cursor"]
    assert cursor
    assert client.get("/api/v2/courses",
                      params={"limit": 1, "cursor": cursor}).status_code == 200
    client.get("/api/v2/courses/does-not-exist")
    client.get("/api/v2/courses?nope=1")

    assert hits == []


def test_tripwires_fire_when_a_frozen_path_is_invoked(tripwires):
    # Positive control: the instrumentation is live, so a silent walk above
    # cannot pass vacuously.
    store = default_content_store()
    sample = store.for_syllabus("syl_synthetic_cie_0580")
    assert sample is not None
    with pytest.raises(AssertionError):
        binary_module.ContentStore.sample_bytes(store, sample)
    with pytest.raises(AssertionError):
        app_module.iter_sample(sample)
    with pytest.raises(AssertionError):
        socket.create_connection(("127.0.0.1", 9))
    assert tripwires == ["ContentStore.sample_bytes", "app.iter_sample",
                         "socket.create_connection"]
