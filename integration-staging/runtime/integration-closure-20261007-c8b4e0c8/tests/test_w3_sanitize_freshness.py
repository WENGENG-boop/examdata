"""W3 (C05 + C06) — one-shot secret iterables and the bounded observation service.

Two integration-review defects:

* C05 — a public projection consulted the caller's secret iterable once per
  string leaf (and per nested call), so a one-shot iterable - the obvious
  ``(x for x in (secret,))`` - was exhausted by the first leaf and every later
  leaf silently escaped redaction. The repair fixes the iterable as one tuple
  (``materialize_secrets``) at each projection boundary, so a tuple and a
  generator over the same values produce byte-identical, marker-free output.
* C06 — the operations view was captured once at dataset construction and
  never observed again: a long-lived app kept serving one frozen scan, a
  damaged root was indistinguishable from a fresh one, and any later read had
  no TTL, no revision and no staleness. The repair observes the root through
  ``OperationsObservationService``: a cached view within the declared TTL, a
  re-scan past it with a new ``obs-...`` revision, a failing refresh served as
  the last good view marked ``stale`` (never raised), and an ``unknown``
  placeholder (``observation_unavailable``) before any good view exists.

Every test here fails on the frozen parent tree (RED: the defects reproduce)
and passes on the repaired closure candidate (GREEN). Candidate-only API
(``materialize_secrets``, ``OperationsObservationService``,
``DEFAULT_OPERATIONS_TTL_SECONDS`` and the new ``default_dataset`` keywords) is
reached through helpers that fail loudly when it is missing, so the frozen
parent yields per-test failures instead of a collection error.
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

import b07r2_common as c  # import first: pins EXAMDATA_INTEGRATION_ROOT + asserts candidate origin
from examdata.integration.api.app import create_app
from examdata.integration.api.links import spec_for
from examdata.integration.operations.jobs import sanitize_tree
from fastapi.testclient import TestClient

import examdata.integration.api.app as app_module
import examdata.integration.api.dataset as dataset_mod

c.assert_origin(app_module, "api.app")
c.assert_origin(dataset_mod, "api.dataset")

MARKER = "SYNTHSECRET-ALPHA-W3"
ABS_WIN = "C:/Users/weo/Desktop/api/secret-area"


# --------------------------------------------------------------------------- #
# Lazy access to the candidate-only API: missing API fails the test, never
# the collection.
# --------------------------------------------------------------------------- #
def _require_param(func: Any, name: str, label: str) -> None:
    import inspect

    try:
        parameters = inspect.signature(func).parameters
    except (TypeError, ValueError):  # pragma: no cover - defensive only
        pytest.fail(f"{label} has no introspectable signature")
    if name not in parameters:
        pytest.fail(f"{label} does not accept a {name!r} keyword")


def _materialize_secrets(secrets: Any) -> tuple[str, ...]:
    func = getattr(c.jobs_mod, "materialize_secrets", None)
    if func is None:
        pytest.fail("operations.jobs.materialize_secrets is not implemented")
    return func(secrets)


def _observation_service() -> Any:
    cls = getattr(dataset_mod, "OperationsObservationService", None)
    if cls is None:
        pytest.fail("api.dataset.OperationsObservationService is not implemented")
    return cls


def _default_ttl() -> Any:
    value = getattr(dataset_mod, "DEFAULT_OPERATIONS_TTL_SECONDS", None)
    if value is None:
        pytest.fail("api.dataset.DEFAULT_OPERATIONS_TTL_SECONDS is not implemented")
    return value


def build_default_dataset(**kwargs: Any) -> Any:
    for name in ("operations_ttl", "operations_clock"):
        if name in kwargs:
            _require_param(dataset_mod.default_dataset, name,
                           "api.dataset.default_dataset")
    return dataset_mod.default_dataset(**kwargs)


# --------------------------------------------------------------------------- #
# Synthetic fixtures and helpers.
# --------------------------------------------------------------------------- #
class FakeClock:
    """A deterministic, manually advanced clock: tests never sleep."""

    def __init__(self, start: datetime) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now = self.now + timedelta(seconds=seconds)


def _utc(day: int = 7, hour: int = 0) -> datetime:
    return datetime(2026, 10, day, hour, 0, 0, tzinfo=timezone.utc)


def _blob(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _marker_document() -> dict[str, Any]:
    """One older CIE checkpoint carrying the marker in keys and values alike."""
    return {
        "stage": "stopped",
        "loop_stage": "idle",
        "current_subject": "synth-w3",
        "totals": {f"count-{MARKER}": 1, "done": 1},
        "stop_reason": f"halted at {MARKER}",
        "stop_detail": {f"log {MARKER}": f"see {MARKER}",
                        "nested": {"deep": f"value {MARKER}"}},
        "needs_user_resume": True,
        "resume_policy": MARKER,
        "updated_at": "2026-10-06T01:00:00+0800",
    }


def _running_document() -> dict[str, Any]:
    return {
        "stage": "running",
        "loop_stage": "idle",
        "current_subject": "synth-w3",
        "totals": {"done": 1},
        "updated_at": "2026-10-06T08:18:31+0800",
    }


def _stopped_document() -> dict[str, Any]:
    """A newer, marker-free stop whose native file requires a user resume."""
    return {
        "stage": "stopped",
        "loop_stage": "idle",
        "current_subject": "synth-w3",
        "totals": {"done": 2},
        "stop_reason": "halted by the operator",
        "needs_user_resume": True,
        "resume_policy": "manual",
        "updated_at": "2026-10-07T02:10:00+0000",
    }


def _write_checkpoint(root: Path, name: str, document: dict[str, Any]) -> Path:
    return c.write_json(root / name / "checkpoint.json", document)


def _marker_view(tmp_path: Path) -> Any:
    root = tmp_path / "ops"
    _write_checkpoint(root, "cie", _marker_document())
    view = dataset_mod.operations_view(entries=[], root=root,
                                       dataset_revision="rev-w3-c05")
    assert view is not None
    return view


def _only_stage(view: Any) -> Any:
    briefs = view.jobs.briefs()
    assert len(briefs) == 1, briefs
    return briefs[0]["stage"]


def _brief_stage(jobs: list[dict[str, Any]]) -> Any:
    assert len(jobs) == 1, jobs
    return jobs[0]["stage"]


# --------------------------------------------------------------------------- #
# C05 — one-shot secret iterables are materialised once per public boundary.
# --------------------------------------------------------------------------- #
def test_c05_operations_projection_generator_matches_tuple(tmp_path):
    """The review's exact C05 reproduction: the same secrets as a tuple and as
    a one-shot generator must produce byte-identical, marker-free output."""
    view = _marker_view(tmp_path)

    tuple_blob = _blob(view.to_public(secrets=(MARKER,)))
    generator_blob = _blob(view.to_public(secrets=(x for x in (MARKER,))))

    assert generator_blob == tuple_blob, (
        "a one-shot secrets iterable changed the public projection")
    assert MARKER not in tuple_blob
    assert MARKER not in generator_blob
    assert "<secret>" in generator_blob


def test_c05_job_projection_and_brief_generator_match_tuple(tmp_path):
    view = _marker_view(tmp_path)
    assert len(view.jobs.rows) == 1
    row = view.jobs.rows[0]

    assert _blob(row.to_public(secrets=(x for x in (MARKER,)))) == _blob(
        row.to_public(secrets=(MARKER,)))
    brief_tuple = _blob(row.brief(secrets=(MARKER,)))
    brief_generator = _blob(row.brief(secrets=(x for x in (MARKER,))))
    assert brief_generator == brief_tuple
    assert MARKER not in brief_generator
    assert "<secret>" in brief_generator


def test_c05_jobs_view_briefs_generator_redacts_every_row(tmp_path):
    root = tmp_path / "ops"
    _write_checkpoint(root, "a", _marker_document())
    _write_checkpoint(root, "b", _stopped_document())
    view = dataset_mod.operations_view(entries=[], root=root,
                                       dataset_revision="rev-w3-c05")
    assert view is not None
    assert len(view.jobs.rows) == 2

    tuple_blob = _blob(view.jobs.briefs(secrets=(MARKER,)))
    generator_blob = _blob(view.jobs.briefs(secrets=(x for x in (MARKER,))))

    assert generator_blob == tuple_blob, (
        "a later row escaped redaction after the generator was exhausted")
    assert MARKER not in generator_blob
    assert len(view.jobs.briefs(secrets=(MARKER,))) == 2


def test_c05_sanitize_tree_generator_redacts_whole_tree():
    value = {"counters": {f"count-{MARKER}": 1, "done": 1},
             "notes": [f"see {MARKER}", {"deep": f"value {MARKER}"}],
             "keep": "untouched"}

    tuple_out = sanitize_tree(value, secrets=(MARKER,))
    generator_out = sanitize_tree(value, secrets=(x for x in (MARKER,)))

    assert generator_out == tuple_out
    assert MARKER not in _blob(generator_out)
    assert generator_out["keep"] == "untouched"
    assert len(generator_out["notes"]) == 2
    assert len(generator_out["counters"]) == 2
    assert tuple_out["counters"]["done"] == 1


def test_c05_unicode_and_path_shaped_secrets_from_generator():
    secret = "秘密-TÖKEN-W3"
    value = {"a": f"{secret} at {ABS_WIN}", "b": [f"{ABS_WIN}/run.log", secret]}

    tuple_out = sanitize_tree(value, secrets=(secret, ABS_WIN))
    generator_out = sanitize_tree(value, secrets=(s for s in (secret, ABS_WIN)))

    assert generator_out == tuple_out
    blob = _blob(generator_out)
    assert secret not in blob
    assert ABS_WIN not in blob and "C:/" not in blob
    assert "<secret>" in blob and "<path>" in blob


def test_c05_text_limit_and_collision_suffixes_survive_a_generator():
    long_tail = "x" * 600
    value = {f"{ABS_WIN}/a": 1, f"{ABS_WIN}/a ": 2, f"{ABS_WIN}/a  ": 3,
             "note": f"see {MARKER} at {ABS_WIN} {long_tail}"}

    tuple_out = sanitize_tree(value, secrets=(MARKER,))
    generator_out = sanitize_tree(value, secrets=(x for x in (MARKER,)))

    assert generator_out == tuple_out
    assert len(generator_out) == 4, f"records were dropped: {generator_out!r}"
    assert {"<path>", "<path>#2", "<path>#3"} <= set(generator_out)
    note = generator_out["note"]
    assert MARKER not in note and ABS_WIN not in note
    limit = getattr(c.jobs_mod, "PUBLIC_TEXT_LIMIT", 500)
    assert len(note) <= limit


def test_c05_materialize_secrets_contract():
    assert _materialize_secrets(None) == ()
    fixed = ("a", "b")
    assert _materialize_secrets(fixed) is fixed, "a tuple must not be copied"
    materialized = _materialize_secrets(x for x in ("a", "b"))
    assert materialized == ("a", "b")
    assert isinstance(materialized, tuple)
    assert "materialize_secrets" in c.jobs_mod.__all__


def test_c05_http_coverage_route_materializes_generator_secrets(tmp_path, monkeypatch):
    root = tmp_path / "ops"
    _write_checkpoint(root, "cie", _marker_document())
    dataset = dataset_mod.default_dataset(operations_root=root)
    client = TestClient(create_app(dataset=dataset))

    monkeypatch.setattr(app_module, "_public_secrets",
                        lambda: (x for x in (MARKER,)))

    response = client.get(spec_for("coverage.get").full_path)
    assert response.status_code == 200, response.text
    operations = response.json()["data"]["operations"]
    assert set(operations) == {"read_only", "root", "checkpoints", "jobs", "published"}
    assert operations["root"]["scanned_files"] == 1
    assert MARKER not in response.text, (
        "a one-shot secrets iterable leaked into the /coverage response")


def test_c05_http_job_detail_materializes_generator_secrets(tmp_path, monkeypatch):
    root = tmp_path / "ops"
    _write_checkpoint(root, "cie", _marker_document())
    dataset = dataset_mod.default_dataset(operations_root=root)
    client = TestClient(create_app(dataset=dataset))

    listing = client.get(spec_for("coverage.get").full_path).json()
    job_id = listing["data"]["operations"]["jobs"][0]["public_id"]

    monkeypatch.setattr(app_module, "_public_secrets",
                        lambda: (x for x in (MARKER,)))

    response = client.get(spec_for("jobs.get").full_path.replace("{id}", job_id))
    assert response.status_code == 200, response.text
    assert MARKER not in response.text, (
        "a one-shot secrets iterable leaked into the /jobs/{id} response")
    item = response.json()["data"]["item"]
    assert item["public_id"] == job_id
    assert "<secret>" in _blob(item)


# --------------------------------------------------------------------------- #
# C06 — the bounded TTL observation service.
# --------------------------------------------------------------------------- #
def test_c06_http_observation_block_is_nested_and_current(tmp_path):
    root = tmp_path / "ops"
    _write_checkpoint(root, "cie", _running_document())
    dataset = dataset_mod.default_dataset(operations_root=root)
    client = TestClient(create_app(dataset=dataset))

    response = client.get(spec_for("coverage.get").full_path)
    assert response.status_code == 200, response.text
    body = response.json()
    operations = body["data"]["operations"]

    assert set(operations) == {"read_only", "root", "checkpoints", "jobs", "published"}
    assert "observation" not in operations and "observation" not in operations["root"]
    observation = operations["checkpoints"]["observation"]
    assert set(observation) == {
        "observation_revision", "observed_at", "age_seconds", "staleness",
        "ttl_seconds", "problems"}
    assert observation["staleness"] == "current"
    assert observation["problems"] == []
    assert observation["ttl_seconds"] == _default_ttl() == 30.0
    revision = observation["observation_revision"]
    assert isinstance(revision, str) and revision.startswith("obs-")
    assert revision != body["meta"]["dataset_revision"]
    assert isinstance(observation["observed_at"], str) and observation["observed_at"]
    assert observation["age_seconds"] >= 0.0


def test_c06_default_dataset_ttl_cache_then_refresh(tmp_path):
    root = tmp_path / "ops"
    path = _write_checkpoint(root, "cie", _running_document())
    clock = FakeClock(_utc())
    dataset = build_default_dataset(operations_root=root, operations_ttl=30.0,
                                    operations_clock=clock)
    client = TestClient(create_app(dataset=dataset))

    def observe() -> dict[str, Any]:
        response = client.get(spec_for("coverage.get").full_path)
        assert response.status_code == 200, response.text
        return response.json()["data"]["operations"]

    first = observe()
    first_observation = first["checkpoints"]["observation"]
    assert first_observation["observation_revision"] == "obs-000001"
    assert first_observation["staleness"] == "current"
    assert first_observation["age_seconds"] == 0.0
    assert _brief_stage(first["jobs"]) == "running"

    c.write_json(path, _stopped_document())
    clock.advance(10.0)
    cached = observe()
    assert cached["checkpoints"]["observation"]["observation_revision"] == "obs-000001"
    assert cached["checkpoints"]["observation"]["age_seconds"] == 10.0
    assert _brief_stage(cached["jobs"]) == "running", (
        "a rewrite within the TTL must not be observed yet")

    clock.advance(25.0)
    refreshed = observe()
    refreshed_observation = refreshed["checkpoints"]["observation"]
    assert refreshed_observation["observation_revision"] == "obs-000002"
    assert refreshed_observation["age_seconds"] == 0.0
    assert refreshed_observation["staleness"] == "current"
    assert _brief_stage(refreshed["jobs"]) == "stopped_requires_resume"


def test_c06_service_observes_within_ttl_and_refreshes_past_it(tmp_path):
    service_cls = _observation_service()
    root = tmp_path / "ops"
    _write_checkpoint(root, "cie", _running_document())
    clock = FakeClock(_utc())
    service = service_cls(root, ttl_seconds=30.0, clock=clock,
                          dataset_revision="rev-w3-direct")

    first = service.observe()
    assert first.staleness == "current"
    assert first.observation_revision == "obs-000001"
    assert first.age_seconds == 0.0
    assert isinstance(first.observed_at, str) and first.observed_at
    assert first.ttl_seconds == 30.0
    assert first.observation_revision != "rev-w3-direct"

    c.write_json(root / "cie" / "checkpoint.json", _stopped_document())
    clock.advance(10.0)
    second = service.observe()
    assert second.observation_revision == first.observation_revision
    assert second.age_seconds == 10.0
    assert _only_stage(second) == "running"

    clock.advance(25.0)
    third = service.observe()
    assert third.observation_revision == "obs-000002"
    assert third.age_seconds == 0.0
    assert third.staleness == "current"
    assert _only_stage(third) == "stopped_requires_resume"

    observation = third.to_public()["checkpoints"]["observation"]
    assert observation["observation_revision"] == "obs-000002"
    assert observation["staleness"] == "current"
    assert observation["ttl_seconds"] == 30.0
    assert observation["problems"] == []


def test_c06_failed_refresh_serves_last_good_stale(tmp_path, monkeypatch):
    service_cls = _observation_service()
    root = tmp_path / "ops"
    _write_checkpoint(root, "cie", _running_document())
    clock = FakeClock(_utc())
    service = service_cls(root, ttl_seconds=30.0, clock=clock)

    good = service.observe()
    clock.advance(31.0)

    def boom(**kwargs: Any) -> Any:
        raise RuntimeError(f"synthetic refresh failure {ABS_WIN}/w3.log")

    with monkeypatch.context() as patched:
        patched.setattr(dataset_mod, "operations_view", boom)
        stale = service.observe()

    assert stale.staleness == "stale"
    assert list(stale.observation_problems) == ["observation_refresh_failed"]
    assert stale.observation_revision == good.observation_revision
    assert stale.age_seconds == 31.0
    blob = _blob(stale.to_public())
    assert "synthetic refresh failure" not in blob
    assert ABS_WIN not in blob and "C:/" not in blob

    clock.advance(1.0)
    recovered = service.observe()
    assert recovered.staleness == "current"
    assert recovered.observation_revision == "obs-000002"


def test_c06_initial_failure_is_an_unknown_placeholder(tmp_path, monkeypatch):
    service_cls = _observation_service()
    root = tmp_path / "ops"
    _write_checkpoint(root, "cie", _running_document())

    def boom(**kwargs: Any) -> Any:
        raise RuntimeError(f"synthetic refresh failure {ABS_WIN}/w3.log")

    with monkeypatch.context() as patched:
        patched.setattr(dataset_mod, "operations_view", boom)

        service = service_cls(root, ttl_seconds=30.0)
        placeholder = service.observe()
        assert placeholder.staleness == "unknown"
        assert list(placeholder.observation_problems) == ["observation_unavailable"]
        assert placeholder.observation_revision is None
        assert placeholder.age_seconds is None
        assert placeholder.observed_at is None
        assert placeholder.root_kind == "configured"
        assert [p["code"] for p in placeholder.problems] == ["observation_unavailable"]
        blob = _blob(placeholder.to_public())
        assert "synthetic refresh failure" not in blob
        assert ABS_WIN not in blob

        dataset = build_default_dataset(operations_root=root)
        assert dataset.operations_service is not None
        assert dataset.operations is not None
        assert dataset.operations.staleness == "unknown"

        client = TestClient(create_app(dataset=dataset))
        response = client.get(spec_for("coverage.get").full_path)
        assert response.status_code == 200, response.text
        observation = response.json()["data"]["operations"]["checkpoints"]["observation"]
        assert observation["staleness"] == "unknown"
        assert observation["problems"] == ["observation_unavailable"]
        assert observation["observation_revision"] is None


def test_c06_missing_or_invalid_native_timestamp_is_unknown(tmp_path):
    missing_root = tmp_path / "missing"
    c.write_json(missing_root / "cie" / "checkpoint.json",
                 c.cie_checkpoint_document(updated_at=None))
    invalid_root = tmp_path / "invalid"
    c.write_json(invalid_root / "cie" / "checkpoint.json",
                 c.cie_checkpoint_document(updated_at="not-a-date"))

    for root, label in ((missing_root, "missing"), (invalid_root, "invalid")):
        view = dataset_mod.operations_view(entries=[], root=root,
                                           dataset_revision="rev-w3-c06")
        assert view is not None
        assert view.staleness == "unknown", label
        assert view.staleness != "current", label
        observation = view.to_public()["checkpoints"]["observation"]
        assert observation["staleness"] == "unknown", label

        service = _observation_service()(root, ttl_seconds=30.0)
        observed = service.observe()
        assert observed.staleness == "unknown", label
        assert list(observed.observation_problems) == [], label


def test_c06_invalid_ttl_is_rejected(tmp_path):
    service_cls = _observation_service()
    root = tmp_path / "ops"
    root.mkdir(parents=True)

    for bad in (-1, 0, True, "30", None):
        with pytest.raises(ValueError):
            service_cls(root, ttl_seconds=bad)

    for bad in (-1, 0.0, True):
        with pytest.raises(ValueError):
            build_default_dataset(operations_root=root, operations_ttl=bad)


def test_c06_freshness_vocabulary_survives_refresh(tmp_path):
    service_cls = _observation_service()
    root = tmp_path / "ops"
    _write_checkpoint(root, "a", _marker_document())
    _write_checkpoint(root, "b", _stopped_document())
    clock = FakeClock(_utc())
    service = service_cls(root, ttl_seconds=30.0, clock=clock)

    first = service.observe()
    vocabulary = {row.freshness for row in first.jobs.rows}
    assert vocabulary == {"current", "superseded"}
    assert len(first.jobs.rows) == 2
    assert len(first.jobs.by_id()) == 1

    clock.advance(31.0)
    second = service.observe()
    assert second.observation_revision == "obs-000002"
    assert {row.freshness for row in second.jobs.rows} == vocabulary
    assert len(second.jobs.rows) == 2
    assert len(second.jobs.by_id()) == 1


def test_c06_concurrent_readers_share_one_refresh(tmp_path):
    service_cls = _observation_service()
    root = tmp_path / "ops"
    _write_checkpoint(root, "cie", _running_document())
    clock = FakeClock(_utc())
    service = service_cls(root, ttl_seconds=30.0, clock=clock)

    with ThreadPoolExecutor(max_workers=8) as pool:
        observed = list(pool.map(lambda _index: service.observe(), range(8)))

    assert {(o.observation_revision, o.staleness, o.age_seconds)
            for o in observed} == {("obs-000001", "current", 0.0)}
    assert all(o.root_kind == "configured" for o in observed)


def test_c06_multi_root_refresh_keeps_the_tree_summary(tmp_path):
    service_cls = _observation_service()
    root = tmp_path / "ops"
    _write_checkpoint(root, "a", _marker_document())
    _write_checkpoint(root, "b", _stopped_document())
    clock = FakeClock(_utc())
    service = service_cls(root, ttl_seconds=30.0, clock=clock)

    first = service.observe()
    assert first.root_kind == "configured"
    assert first.scanned_files == 2
    assert len(first.jobs.briefs()) == 2

    clock.advance(31.0)
    second = service.observe()
    assert second.observation_revision == "obs-000002"
    assert second.scanned_files == 2
    assert len(second.jobs.briefs()) == 2

    public = second.to_public()
    assert public["root"]["scanned_files"] == 2
    assert len(public["jobs"]) == 2
    assert public["checkpoints"]["observation"]["staleness"] == "current"


def test_c06_public_projection_key_sets_are_frozen(tmp_path):
    service_cls = _observation_service()
    root = tmp_path / "ops"
    _write_checkpoint(root, "cie", _running_document())
    service = service_cls(root, ttl_seconds=30.0)
    public = service.observe().to_public()

    assert set(public) == {"read_only", "root", "checkpoints", "jobs", "published"}
    assert set(public["root"]) == {"kind", "configured", "scanned_files",
                                   "truncated", "skipped", "problems"}
    assert set(public["checkpoints"]) == {"rows", "conflicts", "problems", "scan",
                                          "observation"}
    assert set(public["checkpoints"]["observation"]) == {
        "observation_revision", "observed_at", "age_seconds", "staleness",
        "ttl_seconds", "problems"}
    assert len(public["jobs"]) == 1
    assert set(public["jobs"][0]) == {
        "public_id", "system", "scope_id", "scope_kind", "stage", "freshness",
        "resume_required", "stop_reason", "native_updated_at", "source"}
