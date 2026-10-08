"""W1 (C01 + C02) — coverage trust: ``verified``/``complete`` must be earned.

The integration review confirmed two trust defects in the published-data
coverage path (findings C01 and C02):

* C01 — an entry could count as ``verified`` (and its scope as ``complete`` /
  ``100%``) while its own quality summary claimed a verification its evidence
  does not support, or while its identity mapping was empty/unresolved. The
  identity and evidence rules must be the *same* rules the catalog path
  enforces (``contracts.trust``, schema ``trust/1``), and an entry that breaks
  them can only be ``partial``/``unknown`` and is recorded as a problem.
* C02 — the coverage derivation silently accepted manifest references that do
  not exist, duplicate public ids (double counting), wrong-scope references,
  and a manifest that contradicts itself (a repeated reference, an
  exclusion/partial overlap, an ``expected`` smaller than its exclusions), while
  still rendering ``complete`` coverage.

Every test here fails on the frozen parent tree (RED: the defects reproduce) and
passes on the repaired closure candidate (GREEN). The shared trust module is
imported behind a guard so the frozen parent produces a real assertion failure
instead of a collection error.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import b07r2_common as c  # import first: pins EXAMDATA_INTEGRATION_ROOT + asserts candidate origin
from examdata.integration.api.app import create_app
from examdata.integration.api.dataset import (
    Dataset,
    default_dataset,
    fixture_feature_source,
    fixture_providers,
    operations_view,
)
from examdata.integration.api.links import spec_for
from examdata.integration.catalog.builder import CatalogBuilder
from examdata.integration.catalog.model import (
    CatalogEntry,
    CatalogSnapshot,
    CatalogSource,
    compute_revision,
    counts_for,
)
from examdata.integration.catalog.store import CatalogStore
from examdata.integration.contracts.base import UNKNOWN
from examdata.integration.contracts.models import Coverage
from examdata.integration.operations import published as published_mod
from examdata.integration.operations.published import build_published
from fastapi.testclient import TestClient

import examdata.integration.api.app as app_module
import examdata.integration.api.dataset as dataset_module
import examdata.integration.catalog.builder as builder_module
import examdata.integration.catalog.model as model_module
import examdata.integration.catalog.store as store_module

c.assert_origin(app_module, "api.app")
c.assert_origin(dataset_module, "api.dataset")
c.assert_origin(builder_module, "catalog.builder")
c.assert_origin(model_module, "catalog.model")
c.assert_origin(store_module, "catalog.store")

try:
    from examdata.integration.contracts import trust as trust_mod
except ImportError:  # the frozen parent has no shared trust module yet (the C01 defect)
    trust_mod = None

EVIDENCE = ["copied_snapshot"]


def _resolved_identity(public_id: str, *, parent: Any = UNKNOWN) -> dict[str, Any]:
    """A fully resolved question identity (every frozen key carries a value)."""
    return {
        "system": "cie",
        "container_native_identity": "container-w1-tests",
        "native_id": public_id,
        "number_path": "1",
        "parent_native_id": parent,
    }


def _row_problem_codes(row: dict[str, Any]) -> list[str]:
    """The row's problem codes; a row without them fails loudly (the C02 defect)."""
    codes = row.get("problems")
    assert isinstance(codes, list), f"row carries no problem codes: {sorted(row)}"
    return codes


def _records(view: Any, code: str) -> list[dict[str, Any]]:
    return [record for record in view.problems if record.get("code") == code]


def _manifest_document(scope: dict[str, Any]) -> dict[str, Any]:
    return {"schema": "operations-expected/1", "scopes": [scope]}


def _synthetic_operations_root(tmp_path: Path) -> Path:
    root = tmp_path / "ops"
    c.write_json(root / "cie" / "checkpoint.json", c.cie_checkpoint_document())
    c.write_json(root / "expected-manifest.json", {
        "schema": "operations-expected/1",
        "scopes": [{"id": "cie-questions", "system": "cie", "kind": "question",
                    "expected": 1}]})
    return root


# --------------------------------------------------------------------------- #
# C01 — an unsupported verification claim is never verified / complete.
# --------------------------------------------------------------------------- #
def test_c01_1_unsupported_verified_claim_is_never_verified():
    """The review's exact C01 reproduction: ``content=complete`` +
    ``answer_verification=source_verified`` with no evidence labels must not
    count as verified, must be recorded, and must not render complete."""
    pid = "q_w1_c01_1"
    entry = c.make_entry(pid, identity=_resolved_identity(pid),
                         quality=c.QUALITY_VERIFIED, evidence=[])
    view = build_published([entry],
                           c.make_manifest(c.make_scope("cie-questions", expected=1)))
    row = c.row_for_scope(view, "cie-questions")
    assert row["verified"] == 0, row
    assert row["derived_status"] != "complete", row
    assert row["percentage"] is None, row
    codes = _row_problem_codes(row)
    assert "quality_claim_invalid" in codes, codes
    detail = _records(view, "quality_claim_invalid")[0]["detail"]
    assert "verification_without_authoritative_evidence" in detail, detail


def test_c01_2_missing_answer_with_verified_claim_is_a_contradiction():
    """A claim that the answer is missing *and* source-verified is a
    contradiction: not verified, recorded, and never complete."""
    pid = "q_w1_c01_2"
    entry = c.make_entry(pid, identity=_resolved_identity(pid),
                         quality={"content": "complete", "answer_presence": "missing",
                                  "answer_verification": "source_verified"},
                         evidence=list(EVIDENCE))
    view = build_published([entry],
                           c.make_manifest(c.make_scope("cie-questions", expected=1)))
    row = c.row_for_scope(view, "cie-questions")
    assert row["verified"] == 0, row
    assert row["derived_status"] == "conflict", row
    assert row["percentage"] is None, row
    codes = _row_problem_codes(row)
    assert "quality_claim_invalid" in codes, codes
    detail = _records(view, "quality_claim_invalid")[0]["detail"]
    assert "quality_claim_contradiction" in detail, detail


def test_c01_3_empty_identity_is_not_identity_complete():
    """An empty identity mapping must not count as identity complete: the entry
    is unknown, recorded, and the scope is never complete."""
    pid = "q_w1_c01_3"
    entry = c.make_entry(pid, identity={}, quality=c.QUALITY_VERIFIED,
                         evidence=list(EVIDENCE))
    view = build_published([entry],
                           c.make_manifest(c.make_scope("cie-questions", expected=1)))
    row = c.row_for_scope(view, "cie-questions")
    assert row["identity_complete"] == 0, row
    assert row["unknown"] == 1, row
    assert row["verified"] == 0, row
    codes = _row_problem_codes(row)
    assert codes == ["identity_unresolved"], codes
    assert row["derived_status"] == "partial", row


# --------------------------------------------------------------------------- #
# Positive controls: the good path still verifies.
# --------------------------------------------------------------------------- #
def test_verified_claim_with_authoritative_evidence_is_verified():
    pid = "q_w1_ok"
    entry = c.make_entry(pid, identity=_resolved_identity(pid),
                         quality=c.QUALITY_VERIFIED, evidence=list(EVIDENCE))
    view = build_published([entry],
                           c.make_manifest(c.make_scope("cie-questions", expected=1)))
    row = c.row_for_scope(view, "cie-questions")
    assert row["verified"] == 1, row
    assert row["derived_status"] == "complete", row
    assert row["percentage"] == 100.0, row
    assert row.get("problems", []) == [], row


def test_manual_adjudicated_with_decision_is_verified():
    pid = "q_w1_manual_ok"
    entry = c.make_entry(pid, identity=_resolved_identity(pid),
                         quality={"content": "complete", "answer_presence": "present",
                                  "answer_verification": "manual_adjudicated"},
                         evidence=["static_inspection"])
    entry.lineage = {"manual_decision": {"selected_value": "option-A"}}
    view = build_published([entry],
                           c.make_manifest(c.make_scope("cie-questions", expected=1)))
    row = c.row_for_scope(view, "cie-questions")
    assert row["verified"] == 1, row
    assert row["derived_status"] == "complete", row
    assert row["percentage"] == 100.0, row


def test_manual_adjudicated_without_decision_is_not_verified():
    pid = "q_w1_manual_bad"
    entry = c.make_entry(pid, identity=_resolved_identity(pid),
                         quality={"content": "complete", "answer_presence": "present",
                                  "answer_verification": "manual_adjudicated"},
                         evidence=["static_inspection"])
    view = build_published([entry],
                           c.make_manifest(c.make_scope("cie-questions", expected=1)))
    row = c.row_for_scope(view, "cie-questions")
    assert row["verified"] == 0, row
    codes = _row_problem_codes(row)
    assert "quality_claim_invalid" in codes, codes
    detail = _records(view, "quality_claim_invalid")[0]["detail"]
    assert "verification_without_manual_decision" in detail, detail


# --------------------------------------------------------------------------- #
# Identity rules (the C01 identity axis).
# --------------------------------------------------------------------------- #
def test_identity_unknown_sentinel_is_unresolved_and_flagged():
    pid = "q_w1_unk"
    entry = c.make_entry(pid, identity={**_resolved_identity(pid), "native_id": UNKNOWN},
                         quality=c.QUALITY_VERIFIED, evidence=list(EVIDENCE))
    view = build_published([entry],
                           c.make_manifest(c.make_scope("cie-questions", expected=1)))
    row = c.row_for_scope(view, "cie-questions")
    assert row["identity_complete"] == 0, row
    assert row["unknown"] == 1, row
    assert row["verified"] == 0, row
    codes = _row_problem_codes(row)
    assert codes == ["identity_unresolved"], codes


def test_identity_persisted_unknown_token_round_trip_stays_unresolved():
    pid = "q_w1_token"
    entry = c.make_entry(pid, identity={**_resolved_identity(pid), "native_id": UNKNOWN})
    raw = entry.to_dict()
    assert raw["identity_fields"]["native_id"] == "__unknown__", raw
    restored = CatalogEntry.from_dict(raw)
    assert trust_mod is not None, "contracts.trust is missing: identity rules are not shared"
    assert trust_mod.identity_resolved(restored) is False
    problems = trust_mod.identity_problems("question", restored.identity_fields)
    assert any(problem.startswith("identity_unknown") for problem in problems), problems


def test_identity_none_value_is_unresolved():
    pid = "q_w1_none"
    entry = c.make_entry(pid, identity={**_resolved_identity(pid), "native_id": None},
                         quality=c.QUALITY_VERIFIED, evidence=list(EVIDENCE))
    view = build_published([entry],
                           c.make_manifest(c.make_scope("cie-questions", expected=1)))
    row = c.row_for_scope(view, "cie-questions")
    assert row["identity_complete"] == 0, row
    assert row["unknown"] == 1, row
    codes = _row_problem_codes(row)
    assert codes == ["identity_unresolved"], codes
    detail = _records(view, "identity_unresolved")[0]["detail"]
    assert detail == "identity_none_value:native_id", detail


def test_identity_empty_value_is_unresolved():
    pid = "q_w1_empty"
    entry = c.make_entry(pid, identity={**_resolved_identity(pid), "number_path": []},
                         quality=c.QUALITY_VERIFIED, evidence=list(EVIDENCE))
    view = build_published([entry],
                           c.make_manifest(c.make_scope("cie-questions", expected=1)))
    row = c.row_for_scope(view, "cie-questions")
    assert row["identity_complete"] == 0, row
    codes = _row_problem_codes(row)
    assert codes == ["identity_unresolved"], codes
    detail = _records(view, "identity_unresolved")[0]["detail"]
    assert detail == "identity_empty_value:number_path", detail


def test_identity_rules_are_per_kind():
    """The frozen per-kind identity keys decide resolution: an asset with a
    ``None`` media type is unresolved, a complete asset is not."""
    bad = c.make_entry("asset_w1_bad", system="cie", kind="asset",
                       identity={"system": "cie", "media_type": None,
                                 "sha256": "a" * 64, "storage_mode": "link"})
    good = c.make_entry("asset_w1_good", system="cie", kind="asset",
                        identity={"system": "cie", "media_type": "image/png",
                                  "sha256": "b" * 64, "storage_mode": "link"})
    view = build_published([bad, good], c.make_manifest(
        c.make_scope("cie-assets", system="cie", kind="asset", expected=2)))
    row = c.row_for_scope(view, "cie-assets")
    assert row["identity_complete"] == 1, row
    codes = _row_problem_codes(row)
    assert codes == ["identity_unresolved"], codes
    detail = _records(view, "identity_unresolved")[0]["detail"]
    assert detail == "identity_none_value:media_type", detail


def test_identity_parent_native_id_unknown_stays_exempt():
    """``parent_native_id=UNKNOWN`` records a known absence (a top-level
    question has no parent): it must not make the entry unknown."""
    pid = "q_w1_parent_na"
    entry = c.make_entry(pid, identity=_resolved_identity(pid, parent=UNKNOWN),
                         quality=c.QUALITY_VERIFIED, evidence=list(EVIDENCE))
    view = build_published([entry],
                           c.make_manifest(c.make_scope("cie-questions", expected=1)))
    row = c.row_for_scope(view, "cie-questions")
    assert row["identity_complete"] == 1, row
    assert row["verified"] == 1, row
    assert row["derived_status"] == "complete", row
    assert row.get("problems", []) == [], row


# --------------------------------------------------------------------------- #
# Quality buckets.
# --------------------------------------------------------------------------- #
def test_quality_without_information_is_unknown_not_verified():
    pid = "q_w1_noinfo"
    entry = c.make_entry(pid, identity=_resolved_identity(pid))
    view = build_published([entry],
                           c.make_manifest(c.make_scope("cie-questions", expected=1)))
    row = c.row_for_scope(view, "cie-questions")
    assert row["verified"] == 0, row
    assert row["unknown"] == 1, row
    assert row["partial"] == 0, row
    assert row["derived_status"] == "partial", row
    assert row["percentage"] == 0.0, row


def test_quality_partial_content_stays_partial():
    pid = "q_w1_partial"
    entry = c.make_entry(pid, identity=_resolved_identity(pid),
                         quality=c.QUALITY_PARTIAL_UNVERIFIED)
    view = build_published([entry],
                           c.make_manifest(c.make_scope("cie-questions", expected=1)))
    row = c.row_for_scope(view, "cie-questions")
    assert row["verified"] == 0, row
    assert row["partial"] == 1, row
    assert row["derived_status"] == "partial", row
    assert row["percentage"] == 0.0, row
    assert row.get("problems", []) == [], row


def test_answer_axis_on_non_answer_kind_is_a_quality_problem():
    """A kind that carries no answers (an asset) must not claim the answer
    axis: the claim is recorded and can never verify."""
    pid = "asset_w1_answer_axis"
    entry = c.make_entry(pid, system="cie", kind="asset",
                         identity={"system": "cie", "media_type": "image/png",
                                   "sha256": "d" * 64, "storage_mode": "link"},
                         quality=c.QUALITY_VERIFIED, evidence=list(EVIDENCE))
    view = build_published([entry], c.make_manifest(
        c.make_scope("cie-assets", system="cie", kind="asset", expected=1)))
    row = c.row_for_scope(view, "cie-assets")
    assert row["verified"] == 0, row
    codes = _row_problem_codes(row)
    assert "quality_claim_invalid" in codes, codes
    detail = _records(view, "quality_claim_invalid")[0]["detail"]
    assert detail == "answer_axis_not_applicable", detail


def test_unknown_evidence_label_is_a_quality_problem():
    pid = "q_w1_bad_label"
    entry = c.make_entry(pid, identity=_resolved_identity(pid),
                         quality=c.QUALITY_VERIFIED,
                         evidence=["copied_snapshot", "w1-not-a-label"])
    view = build_published([entry],
                           c.make_manifest(c.make_scope("cie-questions", expected=1)))
    row = c.row_for_scope(view, "cie-questions")
    assert row["verified"] == 0, row
    codes = _row_problem_codes(row)
    assert "quality_claim_invalid" in codes, codes
    detail = _records(view, "quality_claim_invalid")[0]["detail"]
    assert "unknown_evidence_label:w1-not-a-label" in detail, detail


# --------------------------------------------------------------------------- #
# C02 — the manifest and the observed side must not silently disagree.
# --------------------------------------------------------------------------- #
def test_c02_1_manifest_reference_to_unpublished_id_is_a_conflict():
    """The review's exact C02 reproduction: a manifest partial expectation for
    an id that is not published must be recorded and never render complete."""
    pid = "q_w1_c02_1"
    entry = c.make_entry(pid, identity=_resolved_identity(pid),
                         quality=c.QUALITY_VERIFIED, evidence=list(EVIDENCE))
    view = build_published([entry], c.make_manifest(c.make_scope(
        "cie-questions", expected=1,
        partial=(("q_w1_c02_ghost", "declared but never published"),))))
    row = c.row_for_scope(view, "cie-questions")
    assert row["derived_status"] == "conflict", row
    assert row["percentage"] is None, row
    codes = _row_problem_codes(row)
    assert codes == ["manifest_id_not_published"], codes
    assert _records(view, "manifest_id_not_published")[0]["public_id"] == "q_w1_c02_ghost"


def test_c02_2_conflicting_duplicate_public_id_is_deduplicated_and_flagged():
    """The review's exact C02 reproduction: the same public id published twice
    with different content is one logical entry plus a recorded collision."""
    pid = "q_w1_c02_dup"
    first = c.make_entry(pid, identity=_resolved_identity(pid),
                         quality=c.QUALITY_VERIFIED, evidence=list(EVIDENCE))
    second = c.make_entry(pid, identity=_resolved_identity(pid),
                          quality=c.QUALITY_VERIFIED, evidence=list(EVIDENCE))
    second.searchable["stem"] = "a conflicting second copy"
    view = build_published([first, second],
                           c.make_manifest(c.make_scope("cie-questions", expected=2)))
    row = c.row_for_scope(view, "cie-questions")
    assert row["observed"] == 1, row
    assert row["verified"] == 1, row
    assert row["derived_status"] == "conflict", row
    assert row["percentage"] is None, row
    codes = _row_problem_codes(row)
    assert codes == ["duplicate_public_id"], codes
    record = _records(view, "duplicate_public_id")[0]
    assert record["public_id"] == pid and record["copies"] == 2, record


def test_identical_duplicate_is_deduplicated_without_a_conflict():
    pid = "q_w1_c02_same"
    first = c.make_entry(pid, identity=_resolved_identity(pid),
                         quality=c.QUALITY_VERIFIED, evidence=list(EVIDENCE))
    second = c.make_entry(pid, identity=_resolved_identity(pid),
                          quality=c.QUALITY_VERIFIED, evidence=list(EVIDENCE))
    view = build_published([first, second],
                           c.make_manifest(c.make_scope("cie-questions", expected=1)))
    row = c.row_for_scope(view, "cie-questions")
    assert row["observed"] == 1, row
    assert row["derived_status"] == "complete", row
    assert row["percentage"] == 100.0, row
    codes = _row_problem_codes(row)
    assert codes == ["duplicate_public_id_identical"], codes


def test_wrong_scope_reference_is_reported_not_missing():
    container = c.make_entry("cnt_w1_elsewhere", system="cie", kind="container",
                             identity={"system": "cie", "kind": "container",
                                       "native_identity": {"ref": "x"}})
    view = build_published([container], c.make_manifest(c.make_scope(
        "cie-questions", expected=0,
        partial=(("cnt_w1_elsewhere", "published under another kind"),))))
    row = c.row_for_scope(view, "cie-questions")
    codes = _row_problem_codes(row)
    assert codes == ["manifest_id_wrong_scope"], codes
    record = _records(view, "manifest_id_wrong_scope")[0]
    assert record["public_id"] == "cnt_w1_elsewhere", record
    assert record["published_scopes"] == ["cie:container"], record
    assert row["derived_status"] == "conflict", row


def test_duplicate_reference_inside_a_constructed_scope_is_a_contradiction():
    """``parse_manifest`` rejects this, but a directly constructed scope must
    still be caught by the derivation (one classification, one record)."""
    pid = "q_w1_dup_ref"
    entry = c.make_entry(pid, identity=_resolved_identity(pid),
                         quality=c.QUALITY_VERIFIED, evidence=list(EVIDENCE))
    view = build_published([entry], c.make_manifest(c.make_scope(
        "cie-questions", expected=1,
        partial=((pid, "first reason"), (pid, "second reason")))))
    row = c.row_for_scope(view, "cie-questions")
    codes = _row_problem_codes(row)
    assert codes == ["manifest_duplicate_reference"], codes
    record = _records(view, "manifest_duplicate_reference")[0]
    assert record["list"] == "partial" and record["count"] == 2, record
    assert row["partial"] == 1, row
    assert row["derived_status"] == "conflict", row


def test_exclusion_and_partial_overlap_is_a_contradiction():
    pid = "q_w1_overlap"
    entry = c.make_entry(pid, identity=_resolved_identity(pid),
                         quality=c.QUALITY_VERIFIED, evidence=list(EVIDENCE))
    view = build_published([entry], c.make_manifest(c.make_scope(
        "cie-questions", expected=1,
        exclusions=((pid, "excluded once"),), partial=((pid, "and partial too"),))))
    row = c.row_for_scope(view, "cie-questions")
    codes = _row_problem_codes(row)
    assert codes == ["manifest_exclusion_partial_overlap"], codes
    assert row["excluded"] == 1, row
    assert row["partial"] == 0, row
    assert row["derived_status"] == "conflict", row


def test_parse_manifest_rejects_a_repeated_reference():
    document = _manifest_document({
        "id": "s", "system": "cie", "kind": "question", "expected": 2,
        "partial": [{"public_id": "p1", "reason": "a"},
                    {"public_id": "p1", "reason": "b"}]})
    with pytest.raises(ValueError, match="repeats public_id"):
        published_mod.parse_manifest(document)


def test_parse_manifest_rejects_exclusion_partial_overlap():
    document = _manifest_document({
        "id": "s", "system": "cie", "kind": "question", "expected": 2,
        "exclusions": [{"public_id": "p1", "reason": "a"}],
        "partial": [{"public_id": "p1", "reason": "b"}]})
    with pytest.raises(ValueError, match="both"):
        published_mod.parse_manifest(document)


def test_parse_manifest_rejects_expected_smaller_than_exclusions():
    document = _manifest_document({
        "id": "s", "system": "cie", "kind": "question", "expected": 1,
        "exclusions": [{"public_id": "p1", "reason": "a"},
                       {"public_id": "p2", "reason": "b"}]})
    with pytest.raises(ValueError, match="smaller than"):
        published_mod.parse_manifest(document)


# --------------------------------------------------------------------------- #
# Status / percentage matrix (the four-state contract).
# --------------------------------------------------------------------------- #
def test_zero_expected_empty_scope_is_partial_without_percentage():
    view = build_published([], c.make_manifest(c.make_scope("cie-questions", expected=0)))
    row = c.row_for_scope(view, "cie-questions")
    assert row["derived_status"] == "partial", row
    assert row["percentage"] is None, row
    assert row["overfilled"] == 0, row
    assert _row_problem_codes(row) == [], row


def test_zero_expected_with_published_entries_is_a_conflict():
    pid = "q_w1_zero"
    entry = c.make_entry(pid, identity=_resolved_identity(pid),
                         quality=c.QUALITY_VERIFIED, evidence=list(EVIDENCE))
    view = build_published([entry],
                           c.make_manifest(c.make_scope("cie-questions", expected=0)))
    row = c.row_for_scope(view, "cie-questions")
    codes = _row_problem_codes(row)
    assert codes == ["expected_below_published"], codes
    assert row["overfilled"] == 1, row
    assert row["derived_status"] == "conflict", row
    assert row["percentage"] is None, row


def test_all_excluded_scope_is_partial_without_percentage():
    first = c.make_entry("q_w1_ex_1", identity=_resolved_identity("q_w1_ex_1"),
                         quality=c.QUALITY_VERIFIED, evidence=list(EVIDENCE))
    second = c.make_entry("q_w1_ex_2", identity=_resolved_identity("q_w1_ex_2"),
                          quality=c.QUALITY_VERIFIED, evidence=list(EVIDENCE))
    view = build_published([first, second], c.make_manifest(c.make_scope(
        "cie-questions", expected=2,
        exclusions=(("q_w1_ex_1", "reason one"), ("q_w1_ex_2", "reason two")))))
    row = c.row_for_scope(view, "cie-questions")
    assert row["excluded"] == 2, row
    assert row["observed"] == 2, row
    assert row["unmet"] == 0, row
    assert row["derived_status"] == "partial", row
    assert row["percentage"] is None, row
    assert row.get("problems", []) == [], row


def test_underfilled_scope_stays_partial_with_verified_share():
    pid = "q_w1_under"
    entry = c.make_entry(pid, identity=_resolved_identity(pid),
                         quality=c.QUALITY_VERIFIED, evidence=list(EVIDENCE))
    view = build_published([entry],
                           c.make_manifest(c.make_scope("cie-questions", expected=3)))
    row = c.row_for_scope(view, "cie-questions")
    assert row["unmet"] == 2, row
    assert row["observed"] == 1, row
    assert row["derived_status"] == "partial", row
    assert row["percentage"] == 33.33, row


def test_unknown_denominator_never_renders_a_percentage():
    pid = "q_w1_unknown_denom"
    entry = c.make_entry(pid, identity=_resolved_identity(pid),
                         quality=c.QUALITY_VERIFIED, evidence=list(EVIDENCE))
    view = build_published([entry],
                           c.make_manifest(c.make_scope("cie-questions", expected=None)))
    row = c.row_for_scope(view, "cie-questions")
    assert row["derived_status"] == "unknown", row
    assert row["denominator_known"] is False, row
    assert row["percentage"] is None, row
    assert row["unmet"] is None, row
    assert row.get("problems", []) == [], row


def test_missing_stays_zero_and_unmet_carries_the_gap():
    pid = "q_w1_gap"
    entry = c.make_entry(pid, identity=_resolved_identity(pid),
                         quality=c.QUALITY_VERIFIED, evidence=list(EVIDENCE))
    view = build_published([entry],
                           c.make_manifest(c.make_scope("cie-questions", expected=2)))
    row = c.row_for_scope(view, "cie-questions")
    assert row["missing"] == 0, row
    assert row["unmet"] == 1, row
    assert row["observed"] == 1, row
    assert row["verified"] == 1, row


def test_build_published_consumes_any_iterable_exactly_once():
    pid = "q_w1_iter"
    entry = c.make_entry(pid, identity=_resolved_identity(pid),
                         quality=c.QUALITY_VERIFIED, evidence=list(EVIDENCE))
    manifest = c.make_manifest(c.make_scope("cie-questions", expected=1))
    rendered = []
    for entries in ([entry], (entry,), (item for item in [entry])):
        view = build_published(entries, manifest,
                               computed_at="2026-10-07T00:00:00+00:00")
        rendered.append(json.dumps(view.rows, sort_keys=True))
    assert rendered[0] == rendered[1] == rendered[2], rendered


def test_published_rows_validate_against_the_coverage_contract():
    verified = c.make_entry("q_w1_contract_ok", identity=_resolved_identity("q_w1_contract_ok"),
                            quality=c.QUALITY_VERIFIED, evidence=list(EVIDENCE))
    unsupported = c.make_entry("q_w1_contract_bad", identity=_resolved_identity("q_w1_contract_bad"),
                               quality=c.QUALITY_VERIFIED, evidence=[])
    scenarios = [
        ([verified], c.make_scope("s1", expected=1)),
        ([unsupported], c.make_scope("s2", expected=1)),
        ([verified], c.make_scope("s3", expected=None)),
        ([verified], c.make_scope("s4", expected=0)),
        ([verified, verified], c.make_scope("s5", expected=2)),
        ([], c.make_scope("s6", expected=0)),
    ]
    for entries, scope in scenarios:
        view = build_published(entries, c.make_manifest(scope))
        for row in view.rows:
            assert Coverage.from_dict(row).validate() == [], row


def test_row_problem_codes_are_sorted_and_unique():
    pid = "q_w1_codes"
    entry = c.make_entry(pid, identity={}, quality=c.QUALITY_VERIFIED, evidence=[])
    view = build_published([entry],
                           c.make_manifest(c.make_scope("cie-questions", expected=1)))
    row = c.row_for_scope(view, "cie-questions")
    codes = _row_problem_codes(row)
    assert codes == sorted(set(codes)), codes
    assert codes == ["identity_unresolved", "quality_claim_invalid"], codes


# --------------------------------------------------------------------------- #
# One invalid entry, every catalog path: the same rules everywhere.
# --------------------------------------------------------------------------- #
def _unsupported_source(pid: str) -> CatalogSource:
    return CatalogSource(
        kind="question",
        system="cie",
        identity_fields=_resolved_identity(pid),
        native_locator={"native_kind": "synthetic-w1", "ref": pid},
        searchable={"stem": pid},
        source_revision="rev-w1",
        quality_summary=dict(c.QUALITY_VERIFIED),
        content_class="synthetic",
        evidence_labels=[],
    )


def test_one_invalid_quality_entry_is_flagged_on_every_catalog_path():
    pid = "q_w1_paths"
    entry = c.make_entry(pid, identity=_resolved_identity(pid),
                         quality=c.QUALITY_VERIFIED, evidence=[])
    source = _unsupported_source(pid)

    entry_problems = entry.validate()
    assert "entry: verification_without_authoritative_evidence" in entry_problems, entry_problems

    source_problems = source.validate()
    assert "source: verification_without_authoritative_evidence" in source_problems, source_problems

    store = CatalogStore()
    stored = store.add(source)
    assert stored is not None
    assert [p["code"] for p in store.problems] == ["quality_claim_invalid"], store.problems
    assert getattr(store, "identity_problems", None) == [], store.identity_problems

    result = CatalogBuilder().build([source])
    assert result.ok is False, result.problems
    assert result.snapshot is None
    assert "quality_claim_invalid" in [p["code"] for p in result.problems], result.problems

    snapshot = CatalogSnapshot.from_dict({
        "schema": "catalog-snapshot/1", "dataset_revision": "rev-w1",
        "entries": [entry.to_dict()], "problems": []})
    assert "quality_claim_invalid" in [p["code"] for p in snapshot.problems], snapshot.problems


def test_one_unresolved_identity_entry_is_visible_but_not_fatal():
    source = CatalogSource(
        kind="asset",
        system="cie",
        identity_fields={"system": "cie", "media_type": None,
                         "sha256": "c" * 64, "storage_mode": "link"},
        native_locator={"kind": "asset", "sha256": "c" * 64, "storage_mode": "link"},
        searchable={"media_type": None},
        source_revision="rev-w1",
        content_class="unknown",
    )
    store = CatalogStore()
    stored = store.add(source)
    assert stored is not None
    assert store.problems == [], store.problems
    identity_problems = getattr(store, "identity_problems", None)
    assert identity_problems, "the store must keep the unresolved identity visible"
    assert [p["code"] for p in identity_problems] == ["identity_unresolved"], identity_problems
    assert "identity_none_value:media_type" in identity_problems[0]["detail"]

    result = CatalogBuilder().build([source])
    assert result.ok is True, result.problems
    assert result.snapshot is not None
    assert [p["code"] for p in result.snapshot.problems] == ["identity_unresolved"], \
        result.snapshot.problems


def test_snapshot_round_trip_keeps_trust_problems():
    pid = "q_w1_roundtrip"
    entry = c.make_entry(pid, identity=_resolved_identity(pid),
                         quality=c.QUALITY_VERIFIED, evidence=[])
    snapshot = CatalogSnapshot.from_dict({
        "schema": "catalog-snapshot/1", "dataset_revision": "rev-w1",
        "entries": [entry.to_dict()], "problems": []})
    codes = [p["code"] for p in snapshot.problems]
    assert "quality_claim_invalid" in codes, codes
    again = CatalogSnapshot.from_dict(snapshot.to_dict())
    assert [p["code"] for p in again.problems] == codes, again.problems
    assert snapshot.validate(), "the flat validate view must surface the rejected entry"


# --------------------------------------------------------------------------- #
# The shared rule source itself.
# --------------------------------------------------------------------------- #
def test_trust_module_is_the_shared_rule_source():
    assert trust_mod is not None, "contracts.trust is missing: the rules are not shared"
    assert trust_mod.TRUST_SCHEMA == "trust/1"
    assert published_mod.ANSWER_BEARING_KINDS == trust_mod.ANSWER_BEARING_KINDS
    assert published_mod.NOT_APPLICABLE_IDENTITY_FIELDS == trust_mod.NOT_APPLICABLE_IDENTITY_FIELDS
    codes = getattr(published_mod, "CONTRADICTION_CODES", None)
    assert codes is not None, "the contradiction code set is not published"
    expected = {"expected_below_published", "expected_below_exclusions",
                "manifest_id_not_published", "manifest_id_wrong_scope",
                "manifest_duplicate_reference", "manifest_exclusion_partial_overlap",
                "duplicate_public_id", "quality_claim_invalid"}
    assert set(codes) == expected, sorted(codes)
    assert "duplicate_public_id_identical" not in codes
    assert "identity_unresolved" not in codes


def test_quality_state_matches_the_published_bucket():
    assert trust_mod is not None, "contracts.trust is missing: the rules are not shared"
    verified = c.make_entry("q_w1_state_ok", identity=_resolved_identity("q_w1_state_ok"),
                            quality=c.QUALITY_VERIFIED, evidence=list(EVIDENCE))
    partial = c.make_entry("q_w1_state_partial", identity=_resolved_identity("q_w1_state_partial"),
                           quality=c.QUALITY_COMPLETE_UNVERIFIED, evidence=list(EVIDENCE))
    unknown = c.make_entry("q_w1_state_unknown", identity=_resolved_identity("q_w1_state_unknown"))
    assert trust_mod.quality_state(verified) == "verified"
    assert trust_mod.quality_state(partial) == "partial"
    assert trust_mod.quality_state(unknown) == "unknown"


# --------------------------------------------------------------------------- #
# HTTP projections.
# --------------------------------------------------------------------------- #
def test_http_coverage_never_renders_an_unsupported_claim_as_verified(tmp_path):
    root = _synthetic_operations_root(tmp_path)
    pid = "q_w1_http"
    entry = c.make_entry(pid, identity=_resolved_identity(pid),
                         quality=c.QUALITY_VERIFIED, evidence=[])
    revision = compute_revision([entry])
    dataset = Dataset(
        snapshot=CatalogSnapshot(dataset_revision=revision, entries=[entry],
                                 counts=counts_for([entry])),
        registry=fixture_providers(),
        features=fixture_feature_source(),
        available_revisions=(revision,),
        operations=operations_view(entries=[entry], root=root,
                                   dataset_revision=revision),
    )
    client = TestClient(create_app(dataset=dataset))
    response = client.get(spec_for("coverage.get").full_path)
    assert response.status_code == 200, response.text
    published = response.json()["data"]["operations"]["published"]
    rows = published["rows"]
    assert len(rows) == 1, rows
    row = rows[0]
    assert row["verified"] == 0, row
    assert row["derived_status"] == "conflict", row
    assert row["percentage"] is None, row
    codes = row.get("problems")
    assert isinstance(codes, list) and "quality_claim_invalid" in codes, row


def test_http_gaps_route_surfaces_identity_problems():
    dataset = default_dataset(operations_root=None)
    client = TestClient(create_app(dataset=dataset))
    response = client.get(spec_for("gaps.list").full_path)
    assert response.status_code == 200, response.text
    items = response.json()["data"]["items"]
    codes = [row.get("code") for row in items]
    assert codes.count("identity_unresolved") >= 4, codes
