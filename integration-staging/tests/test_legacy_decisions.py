"""A12 legacy compatibility registry invariants (plan 5.5).

The registry is the single per-route record for the 71-route baseline. These
tests pin its vocabulary, counts, id scheme and cross-references: adapter rows
must point at real staged v2 capabilities, deferred rows must name a protected
owner, every row must carry at least one test id whose file exists, and the
recorded input hashes must still match the files on disk.

Read-only: nothing here touches the original tree beyond existence checks.
"""
from __future__ import annotations

import hashlib
import importlib
import re
from pathlib import Path

import pytest

from examdata_integration.api import links
from examdata_integration.legacy import decisions

STAGING = Path(__file__).resolve().parents[1]
WORKSPACE = STAGING.parent

FROZEN_MECHANISMS = {
    "add_v2_adapter_keep_legacy_defaults": 21,
    "keep_legacy_only": 16,
    "keep_legacy_namespace": 7,
    "bridge_node_cli_keep_legacy_payload": 20,
    "deferred_active_owner": 7,
}
FROZEN_COVERAGE = {"fixture_translation": 14, "envelope_contract": 33, "static_contract": 24}
CAPABILITY_TOKENS = {spec.capability for spec in links.ROUTE_SPECS}
TOKEN_RE = re.compile(r"\b[a-z][a-z-]*\.[a-z][a-z-]*\b")


def test_registry_shape_and_validation():
    document = decisions.registry()
    assert document["schema"] == decisions.SCHEMA
    assert document["row_count"] == 71 == len(decisions.rows())
    assert document["mechanisms"] == FROZEN_MECHANISMS
    assert tuple(document["allowed_statuses"]) == decisions.ALLOWED_STATUSES
    assert re.fullmatch(r"[0-9a-f]{64}", decisions.registry_sha256())


def test_row_ids_are_unique_and_match_the_slug_scheme():
    seen = set()
    for row in decisions.rows():
        assert row["row_id"] == decisions.row_id(row["method"], row["legacy_path"])
        assert row["row_id"] not in seen
        seen.add(row["row_id"])
    assert len(seen) == 71


def test_status_and_coverage_counts_are_frozen():
    assert decisions.status_counts() == {"staged_pass": 64, "deferred_active_owner": 7}
    summary = decisions.coverage_summary()
    assert summary["by_coverage_kind"] == FROZEN_COVERAGE
    assert len(summary["deferred_rows"]) == 7


def test_every_row_has_a_test_id_whose_file_exists():
    referenced_files = set()
    for row in decisions.rows():
        assert row["test_ids"], f"{row['row_id']} carries no test id"
        for test_id in row["test_ids"]:
            assert test_id.startswith("tests/")
            referenced_files.add(test_id.split("::", 1)[0])
    for rel in referenced_files:
        assert (STAGING / rel).is_file(), f"missing test file {rel}"


def test_adapter_rows_name_real_staged_capabilities():
    adapters = [r for r in decisions.rows()
                if r["mechanism"] == "add_v2_adapter_keep_legacy_defaults"]
    assert len(adapters) == 21
    for row in adapters:
        assert row["v2_target"], f"{row['row_id']} has no v2 target"
        tokens = TOKEN_RE.findall(row["v2_target"])
        for token in tokens:
            assert token in CAPABILITY_TOKENS, \
                f"{row['row_id']} names unknown staged capability {token!r}"
    for row in decisions.rows():
        if row["mechanism"] != "add_v2_adapter_keep_legacy_defaults":
            assert row["v2_target"] == "", f"{row['row_id']} must not claim a v2 target"


def test_fixture_ids_are_resolvable():
    for row in decisions.rows():
        for fixture_id in row["fixture_ids"]:
            if fixture_id.startswith("inline:"):
                continue
            module_name, _, attr = fixture_id.partition(":")
            assert module_name.startswith("examdata_integration."), fixture_id
            module = importlib.import_module(module_name)
            assert callable(getattr(module, attr)), fixture_id


def test_deferred_rows_name_the_protected_owner_and_exist():
    deferred = decisions.deferred_rows()
    assert {r["row_id"] for r in deferred} == {
        "GET__api_v1_materials", "GET__api_v1_materials_cie_in_paper",
        "GET__api_v1_materials_material_id", "GET__api_v1_materials_material_id_content",
        "GET__api_v1_timetable", "GET__api_v1_timetable_seasons",
        "GET__api_v1_timetable_windows",
    }
    for row in deferred:
        assert row["status"] == "deferred_active_owner"
        assert row["owner"] == "kimi_active"
        assert row["deferred_reason"]
        assert row["native_parameters"] == "", "protected source must not be parsed"
        # existence only - the router source is never opened in Phase A
        assert (WORKSPACE / row["source_file"]).is_file(), row["source_file"]
        assert "/materials/" in row["source_file"] or "/timetable/" in row["source_file"]


def test_evidence_paths_stay_inside_the_phase_a_roots():
    for row in decisions.rows():
        assert row["evidence_path"].startswith("docs/integration/execution/")
        assert ".." not in row["evidence_path"]


def test_recorded_input_hashes_still_match_disk():
    document = decisions.registry()
    for key in ("worksheet", "shape_extract", "build_tool"):
        entry = document["sources"][key]
        path = WORKSPACE / entry["path"]
        assert path.is_file(), entry["path"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == entry["sha256"], f"{key} changed since the registry was built"
    assert set(document["source_hashes"]) == {
        "examdata/src/examdata/api/app.py",
        "examdata/src/examdata/api/unified.py",
        "examdata/src/examdata/api/ielts.py",
        "examdata/src/examdata/api/toefl.py",
    }
    for rel, digest in document["source_hashes"].items():
        assert re.fullmatch(r"[0-9a-f]{64}", digest), rel


def test_notes_never_claim_merged_or_deployed():
    for row in decisions.rows():
        for text in (row["notes"], row["deferred_reason"]):
            lowered = text.lower()
            assert "merged_pass" not in lowered
            assert "deployed" not in lowered


def test_unknown_lookups_raise():
    with pytest.raises(KeyError):
        decisions.row_by_id("GET__not_a_route")
