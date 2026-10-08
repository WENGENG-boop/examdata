"""A13 operations coverage views (plan 3.5/11).

Coverage is derived, never stored: every observation is kept as a row ranked by
its native ``updated_at``, superseded snapshots stay visible, and a same-instant
disagreement becomes an explicit conflict instead of a silent pick. These tests
pin those honesty rules against the synthetic fixtures plus a few crafted
observations.

Nothing here touches the original tree, the network, a database or a service.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from examdata_integration.operations import checkpoints, coverage

STAGING = Path(__file__).resolve().parents[1]
FIXTURES = STAGING / "fixtures" / "synthetic" / "operations"
WHEN = datetime(2026, 10, 6, 2, 0, tzinfo=timezone.utc)
WHEN_ISO = "2026-10-06T02:00:00+00:00"

ALL_FIXTURES = (
    "cie-batch-checkpoint-running.json",
    "cie-batch-checkpoint-stopped.json",
    "ielts-run-checkpoint-ok.json",
    "ielts-run-checkpoint-ok-stale.json",
    "ielts-run-checkpoint-partial.json",
    "unsupported-checkpoint.json",
)


def _obs(name: str) -> checkpoints.CheckpointObservation:
    return checkpoints.read_checkpoint(FIXTURES / name, observed_at=WHEN)


def _view() -> coverage.CoverageView:
    return coverage.build_coverage([_obs(name) for name in ALL_FIXTURES])


def _crafter(payload: dict, source: str):
    data = json.dumps(payload).encode("utf-8")
    return checkpoints.read_checkpoint_bytes(data, source=source, observed_at=WHEN)


def test_healthy_run_is_current_and_ok():
    view = _view()
    rows = view.rows_for("ielts", "synthetic-run-ok", freshness="current")
    assert len(rows) == 1
    row = rows[0]
    assert row.state == "ok"
    assert row.counters == {"requests": 4, "bytes": 44, "errors": 0}
    assert row.sources == {"synthetic-source-a": {
        "requests": 4, "bytes": 44, "consecutive_5xx": 0, "blocked": None}}
    assert row.source == "ielts-run-checkpoint-ok.json"
    assert row.observed_at == WHEN_ISO
    assert row.native_updated_at == "2026-10-04T19:40:15.361Z"


def test_stale_summary_is_superseded_and_never_overrides():
    view = _view()
    rows = view.rows_for("ielts", "synthetic-run-ok")
    assert len(rows) == 2
    current, superseded = rows[0], rows[1]
    assert current.freshness == "current"
    assert current.counters["requests"] == 4
    assert superseded.freshness == "superseded"
    assert superseded.source == "ielts-run-checkpoint-ok-stale.json"
    assert superseded.counters == {"requests": 2, "bytes": 22, "errors": 0}
    assert superseded.native_updated_at == "2026-10-04T18:02:00.000Z"


def test_cie_batch_keeps_both_snapshots_with_stop_detail():
    view = _view()
    rows = view.rows_for("cie", "cie-batch:8888")
    assert len(rows) == 2
    current, superseded = rows[0], rows[1]
    assert current.freshness == "current"
    assert current.source == "cie-batch-checkpoint-running.json"
    assert current.state == "in_progress"
    assert current.stop is None
    assert superseded.freshness == "superseded"
    assert superseded.state == "stopped"
    assert superseded.stop == {
        "reason": "download_error",
        "detail": {"paper": "8888/2025/Jun/21", "role": "qp",
                   "error": "HTTP 502", "error_class": "http_502"},
        "stopped_at": "2026-10-04T16:30:15+0800",
    }
    assert superseded.resume["needs_user_resume"] is False
    assert superseded.counters["failed_cells"] == 0


def test_partial_failure_preserves_counters_and_blocked_source():
    view = _view()
    rows = view.rows_for("ielts", "synthetic-run-partial", freshness="current")
    assert len(rows) == 1
    row = rows[0]
    assert row.state == "partial_failure"
    assert row.counters == {"requests": 6, "bytes": 300, "errors": 1}
    assert row.sources["synthetic-source-b"]["consecutive_5xx"] == 2
    assert row.sources["synthetic-source-c"]["blocked"] == "http_403"


def test_unknown_checkpoint_is_carried_with_problems():
    view = _view()
    rows = view.rows_for("unknown")
    assert len(rows) == 1
    row = rows[0]
    assert row.state == "unknown"
    assert row.counters is None and row.sources is None
    assert "unrecognised_checkpoint_format" in row.problems
    assert {"source": "unsupported-checkpoint.json",
            "problems": ["unrecognised_checkpoint_format"]} in view.problems


def test_same_instant_disagreement_becomes_conflict():
    first = _crafter({"schema_version": "ielts-run-checkpoint/1", "run_id": "clash",
                      "updated_at": "2026-10-04T10:00:00Z",
                      "fetcher": {"counters": {"requests": 1, "bytes": 1, "errors": 0},
                                  "sources": {}}}, source="a.json")
    second = _crafter({"schema_version": "ielts-run-checkpoint/1", "run_id": "clash",
                       "updated_at": "2026-10-04T10:00:00Z",
                       "fetcher": {"counters": {"requests": 9, "bytes": 9, "errors": 0},
                                   "sources": {}}}, source="b.json")
    view = coverage.build_coverage([first, second])
    rows = view.rows_for("ielts", "clash")
    assert [row.freshness for row in rows] == ["conflict", "conflict"]
    assert [row.source for row in rows] == ["a.json", "b.json"]
    assert view.rows_for("ielts", "clash", freshness="current") == []
    assert len(view.conflicts) == 1
    conflict = view.conflicts[0]
    assert conflict["scope_id"] == "clash"
    assert conflict["sources"] == ["a.json", "b.json"]
    assert conflict["payload_sha256"][0] != conflict["payload_sha256"][1]


def test_missing_counters_stay_none_never_zero():
    bare = _crafter({"schema_version": "ielts-run-checkpoint/1", "run_id": "bare",
                     "updated_at": "2026-10-04T10:00:00Z"}, source="bare.json")
    view = coverage.build_coverage([bare])
    row = view.rows[0]
    assert row.state == "unknown"
    assert row.counters is None
    assert row.sources is None


def test_all_blocked_sources_is_blocked():
    blocked = _crafter(
        {"schema_version": "ielts-run-checkpoint/1", "run_id": "blocked-run",
         "updated_at": "2026-10-04T10:00:00Z",
         "fetcher": {"counters": {"requests": 2, "bytes": 2, "errors": 2},
                     "sources": {"one": {"requests": 1, "bytes": 1,
                                         "consecutive_5xx": 3, "blocked": "http_403"},
                                 "two": {"requests": 1, "bytes": 1,
                                         "consecutive_5xx": 3, "blocked": "http_429"}}}},
        source="blocked.json")
    view = coverage.build_coverage([blocked])
    assert view.rows[0].state == "blocked"
    assert view.rows[0].counters["errors"] == 2


def test_to_dict_is_deterministic_and_json_serializable():
    view = _view()
    document = view.to_dict()
    json.dumps(document)
    assert document["conflicts"] == []
    assert document["problems"] == [{"source": "unsupported-checkpoint.json",
                                     "problems": ["unrecognised_checkpoint_format"]}]
    reversed_view = coverage.build_coverage([_obs(name) for name in reversed(ALL_FIXTURES)])
    assert reversed_view.to_dict() == document
