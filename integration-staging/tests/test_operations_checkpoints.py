"""A13 operations checkpoint adapters (plan 3.5/11).

The adapters are read-only: they hash and parse a checkpoint file and return a
typed observation, never writing anything and never inventing a value the
native file does not provide. These tests drive them against the synthetic
fixtures (invented values, shaped like both native formats) and pin the typed
handling of corrupted, missing and unknown files.

Nothing here touches the original tree, the network, a database or a service.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from examdata_integration.operations import checkpoints

STAGING = Path(__file__).resolve().parents[1]
FIXTURES = STAGING / "fixtures" / "synthetic" / "operations"
TOOL = STAGING / "tools" / "a13_capture_fixtures.py"
WHEN = datetime(2026, 10, 6, 2, 0, tzinfo=timezone.utc)
WHEN_ISO = "2026-10-06T02:00:00+00:00"


def _read(name: str, **kwargs) -> checkpoints.CheckpointObservation:
    return checkpoints.read_checkpoint(FIXTURES / name, observed_at=WHEN, **kwargs)


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_capture_tool_check_mode_is_clean():
    result = subprocess.run(
        [sys.executable, str(TOOL), "--check"],
        cwd=STAGING, capture_output=True, text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    assert result.returncode == 0, result.stdout + result.stderr
    assert "A13_PROVENANCE: PASS (6 entries)" in result.stdout


def test_manifest_lists_every_fixture_with_matching_hash():
    manifest = json.loads((FIXTURES / "PROVENANCE.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == "fixture-provenance/1"
    assert manifest["summary"]["entries"] == len(manifest["entries"]) == 6
    listed = {Path(entry["path"]).name for entry in manifest["entries"]}
    present = {p.name for p in FIXTURES.glob("*.json") if p.name != "PROVENANCE.json"}
    assert listed == present
    for entry in manifest["entries"]:
        path = FIXTURES / Path(entry["path"]).name
        assert path.stat().st_size == entry["bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]
    assert (FIXTURES / "README.md").is_file()


def test_read_is_read_only():
    path = FIXTURES / "cie-batch-checkpoint-stopped.json"
    before_bytes = path.read_bytes()
    before_mtime = path.stat().st_mtime_ns
    observation = checkpoints.read_checkpoint(path, observed_at=WHEN)
    assert observation.payload_sha256 == hashlib.sha256(before_bytes).hexdigest()
    assert path.read_bytes() == before_bytes
    assert path.stat().st_mtime_ns == before_mtime


def test_cie_stopped_view_preserves_native_fields():
    document = _load("cie-batch-checkpoint-stopped.json")
    observation = _read("cie-batch-checkpoint-stopped.json")
    assert observation.format is checkpoints.CheckpointFormat.CIE_BATCH
    assert observation.native_schema is None
    assert observation.problems == []
    state = checkpoints.cie_batch_state(observation)
    assert state is not None
    assert state.stage == "stopped"
    assert state.loop_stage == "stopped"
    assert state.current_subject == "8888"
    assert state.stop_reason == "download_error"
    assert state.stop_detail == document["stop_detail"]
    assert state.stopped_at == document["stopped_at"]
    assert state.needs_user_resume is False
    assert state.resume_policy == document["resume_policy"]
    assert state.totals == document["totals"]
    assert state.loop_stages == document["loop_stages"]


def test_cie_running_view_keeps_missing_stop_fields_none():
    document = _load("cie-batch-checkpoint-running.json")
    assert "stop_reason" not in document and "stop_detail" not in document
    state = checkpoints.cie_batch_state(_read("cie-batch-checkpoint-running.json"))
    assert state is not None
    assert state.stage == "running"
    assert state.current_paper == document["current_paper"]
    assert state.stop_reason is None
    assert state.stop_detail is None
    assert state.stopped_at is None
    assert state.totals == document["totals"]


def test_ielts_view_preserves_counters_sources_and_blocked_reason():
    ok_doc = _load("ielts-run-checkpoint-ok.json")
    ok = checkpoints.ielts_run_state(_read("ielts-run-checkpoint-ok.json"))
    assert ok is not None
    assert ok.run_id == "synthetic-run-ok"
    assert ok.updated_at == ok_doc["updated_at"]
    assert ok.counters == ok_doc["fetcher"]["counters"]
    assert ok.sources == ok_doc["fetcher"]["sources"]
    assert ok.sources["synthetic-source-a"]["blocked"] is None
    partial = checkpoints.ielts_run_state(_read("ielts-run-checkpoint-partial.json"))
    assert partial is not None
    assert partial.sources["synthetic-source-c"]["blocked"] == "http_403"
    assert partial.sources["synthetic-source-b"]["consecutive_5xx"] == 2


def test_markers_and_unknown_keys_are_preserved_verbatim():
    observation = _read("ielts-run-checkpoint-ok.json")
    assert observation.payload == _load("ielts-run-checkpoint-ok.json")
    assert observation.document["fixture_kind"] == "synthetic"
    assert observation.native_schema == "ielts-run-checkpoint/1"


def test_unknown_format_is_typed_not_an_exception():
    observation = _read("unsupported-checkpoint.json")
    assert observation.format is checkpoints.CheckpointFormat.UNKNOWN
    assert "unrecognised_checkpoint_format" in observation.problems
    assert observation.payload == _load("unsupported-checkpoint.json")
    assert checkpoints.state_of(observation) is None


def test_invalid_json_is_a_typed_problem():
    observation = checkpoints.read_checkpoint_bytes(b"{not json", source="broken.json",
                                                   observed_at=WHEN)
    assert observation.problems == ["json_unreadable"]
    assert observation.payload is None
    assert observation.format is checkpoints.CheckpointFormat.UNKNOWN
    assert observation.source == "broken.json"
    assert observation.observed_at == WHEN_ISO


def test_non_object_payload_is_a_typed_problem():
    observation = checkpoints.read_checkpoint_bytes(b"[1, 2]", source="list.json",
                                                   observed_at=WHEN)
    assert "payload_not_an_object" in observation.problems
    assert observation.payload == [1, 2]


def test_missing_file_raises_typed_read_error():
    with pytest.raises(checkpoints.CheckpointReadError):
        checkpoints.read_checkpoint(FIXTURES / "does-not-exist.json")


def test_native_timestamp_parsing_accepts_both_dialects():
    parse = checkpoints.parse_native_timestamp
    assert parse("2026-10-04T16:30:15+0800") == datetime(2026, 10, 4, 8, 30, 15,
                                                         tzinfo=timezone.utc)
    assert parse("2026-10-04T19:40:15.361Z") == datetime(2026, 10, 4, 19, 40, 15,
                                                         361000, tzinfo=timezone.utc)
    assert parse(None) is None
    assert parse("garbage") is None
    assert parse("") is None


def test_observed_at_defaults_to_now_utc():
    before = datetime.now(timezone.utc).timestamp()
    observation = checkpoints.read_checkpoint(FIXTURES / "ielts-run-checkpoint-ok.json")
    after = datetime.now(timezone.utc).timestamp()
    parsed = checkpoints.parse_native_timestamp(observation.observed_at)
    assert parsed is not None
    assert before - 1 <= parsed.timestamp() <= after + 1


def test_iter_checkpoint_paths_selects_names_and_sorts(tmp_path):
    (tmp_path / "b").mkdir()
    (tmp_path / "a").mkdir()
    wanted = tmp_path / "b" / "checkpoint.json"
    wanted.write_text("{}", encoding="utf-8")
    resume = tmp_path / "a" / "resume-checkpoint.json"
    resume.write_text("{}", encoding="utf-8")
    (tmp_path / "a" / "other.json").write_text("{}", encoding="utf-8")
    found = checkpoints.iter_checkpoint_paths(
        tmp_path, names=("checkpoint.json", "resume-checkpoint.json"))
    assert found == [resume, wanted]
    assert checkpoints.iter_checkpoint_paths(tmp_path / "missing") == []


def test_payload_sha256_and_size_match_file_bytes():
    observation = _read("ielts-run-checkpoint-partial.json")
    raw = (FIXTURES / "ielts-run-checkpoint-partial.json").read_bytes()
    assert observation.payload_sha256 == hashlib.sha256(raw).hexdigest()
    assert observation.size_bytes == len(raw)
