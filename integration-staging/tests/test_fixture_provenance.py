"""A03 fixture provenance tests (plan section 11/A03).

The manifest is the authority for fixture integrity: every fixture must be inside
the staging fixture root, must match its recorded sha256, must carry provenance,
and copied snapshots must be provably stable (source hash before == after == copy).
Synthetic fixtures must declare themselves synthetic. Examination material must be
absent.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from examdata_integration.testing.guards import STAGING_ROOT, is_within

FIXTURES = STAGING_ROOT / "fixtures"
MANIFEST = FIXTURES / "PROVENANCE.json"
TOOL = STAGING_ROOT / "tools" / "a03_capture_fixtures.py"

# A verbatim fragment of real CIE question text from the stopped batch output.
# If this ever appears inside a fixture, examination material has leaked into staging.
EXAM_MATERIAL_CANARY = "Express 3y"

DENY_SUFFIXES = (".db", ".sqlite", ".sqlite3", ".duckdb", ".parquet", ".pdf", ".mp3", ".wav",
                 ".pem", ".key", ".zip", ".tar", ".gz")


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def test_manifest_exists_and_is_wellformed(manifest):
    assert manifest["schema"] == "examdata.integration.fixture-provenance/1"
    assert manifest["entries"], "manifest must record fixtures"
    assert manifest["policy"]["max_bytes"] > 0
    assert manifest["generator"].endswith("a03_capture_fixtures.py")


def test_generator_hash_matches_on_disk(manifest):
    assert TOOL.is_file()
    assert manifest["generator_sha256"] == sha256_file(TOOL), \
        "manifest was written by a different revision of the capture tool; re-run it"


def test_every_fixture_is_inside_the_staging_fixture_root(manifest):
    for entry in manifest["entries"]:
        dst = STAGING_ROOT.parent / entry["destination_path"]
        assert is_within(dst, FIXTURES), f"{entry['fixture_id']} escapes the fixture root"


def test_every_destination_matches_its_recorded_hash(manifest):
    mismatches = []
    for entry in manifest["entries"]:
        dst = STAGING_ROOT.parent / entry["destination_path"]
        if not dst.is_file():
            if str(entry.get("status", "")).startswith("deferred"):
                continue
            mismatches.append(f"{entry['fixture_id']}: missing")
            continue
        if sha256_file(dst) != entry["destination_sha256"]:
            mismatches.append(f"{entry['fixture_id']}: hash mismatch")
    assert not mismatches, mismatches


def test_copied_snapshots_are_stable_and_complete(manifest):
    copied = [e for e in manifest["entries"] if e["kind"] == "copied_snapshot"]
    assert copied, "expected at least one copied_snapshot fixture"
    for entry in copied:
        assert entry["status"] == "copied", entry
        assert entry["stable"] is True, entry
        assert entry["content_matches"] is True, entry
        assert entry["source_sha256_before"] == entry["source_sha256_after"], entry
        assert entry["destination_sha256"] == entry["source_sha256_before"], entry
        assert entry["source_bytes"] == entry["destination_bytes"], entry
        for field in ("source_path", "source_mtime_local", "scope", "copied_at_local",
                      "access_notes_from_source"):
            assert field in entry, f"{entry['fixture_id']} lacks {field}"


def test_synthetic_fixtures_are_labelled_synthetic(manifest):
    synthetic = [e for e in manifest["entries"] if e["kind"] == "synthetic"]
    assert len(synthetic) >= 3
    for entry in synthetic:
        assert entry["label"] == "synthetic_fixture"
        assert entry["source_path"] is None, "a synthetic fixture must not claim an upstream source"
        assert entry["synthetic_marker_present"] is True, entry
        dst = STAGING_ROOT.parent / entry["destination_path"]
        payload = json.loads(dst.read_text(encoding="utf-8"))
        assert payload["fixture_kind"] == "synthetic"
        assert payload["_provenance"]["created_by"], "synthetic fixtures must state their origin"


def test_no_database_or_credential_fixture(manifest):
    offenders = []
    for entry in manifest["entries"]:
        dest = entry["destination_path"].lower()
        src = (entry.get("source_path") or "").lower()
        if dest.endswith(DENY_SUFFIXES) or src.endswith(DENY_SUFFIXES):
            offenders.append(entry["fixture_id"])
        for part in ("/.venv/", "node_modules", "__pycache__", "site-packages", "/.git/"):
            if part in src:
                offenders.append(f"{entry['fixture_id']} ({part})")
    assert not offenders, offenders


def test_examination_material_is_deferred_not_copied(manifest):
    deferred = {d["source"]: d for d in manifest["deferred_sources"]}
    cie = "cie-index-batch-2026-10-01/9709/2024-Jun-11/cie-index.json"
    assert cie in deferred, "the CIE index (verbatim question text) must be recorded as deferred"
    assert deferred[cie]["status"] == "deferred_examination_material"
    copied_sources = {e.get("source_path") for e in manifest["entries"] if e["kind"] == "copied_snapshot"}
    assert cie not in copied_sources


def test_no_examination_material_canary_in_any_fixture():
    hits = []
    for path in sorted(FIXTURES.rglob("*")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if EXAM_MATERIAL_CANARY in text:
            hits.append(path.name)
    assert not hits, f"examination material leaked into fixtures: {hits}"


def test_copied_fixtures_are_valid_json_and_small(manifest):
    for entry in manifest["entries"]:
        if entry["kind"] != "copied_snapshot":
            continue
        dst = STAGING_ROOT.parent / entry["destination_path"]
        payload = json.loads(dst.read_text(encoding="utf-8"))
        assert payload is not None
        assert dst.stat().st_size <= manifest["policy"]["max_bytes"]
        assert dst.stat().st_size == entry["destination_bytes"]


def test_manifest_summary_matches_entries(manifest):
    summary = manifest["summary"]
    entries = manifest["entries"]
    assert summary["entries"] == len(entries)
    assert summary["by_kind"] == {
        "copied_snapshot": len([e for e in entries if e["kind"] == "copied_snapshot"]),
        "synthetic": len([e for e in entries if e["kind"] == "synthetic"]),
    }
    assert summary["copied"] == len([e for e in entries if e["status"] == "copied"])
