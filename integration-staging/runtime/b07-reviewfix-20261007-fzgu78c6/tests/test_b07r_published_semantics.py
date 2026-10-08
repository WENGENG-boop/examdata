"""B07R STEP 2 (F1/F2) — published coverage semantics, reproduced on the frozen tree.

These tests encode the REQUIRED post-repair semantics, so on the frozen v1
candidate they fail (RED) and on the repaired v2 candidate they pass.

F1: an identity-known entry must not become ``verified`` without quality
evidence (content complete AND answer verification source-verified or
manually adjudicated). Entries with explicitly partial/missing/unverified
quality land in ``partial``; entries with no quality information land in
``unknown``.

F2: expected and observed counts stay distinct (``observed`` is the published
count; ``expected`` is the manifest denominator; ``unmet`` is the
expected-side gap), and an expected/observed conflict can never render
``complete`` coverage or a 100% percentage.
"""
from __future__ import annotations

import pytest

import b07r_common as c
from examdata.integration.contracts.models import Coverage
from examdata.integration.operations.published import build_published

ROW_CONTRACT_KEYS = {
    "public_id", "scope", "denominator", "denominator_known", "observed",
    "excluded", "unknown", "missing", "partial", "verified", "exclusions",
    "computed_at", "evidence", "derived_status", "percentage",
}


# --------------------------------------------------------------------------- #
# F1 — verified requires quality evidence.
# --------------------------------------------------------------------------- #
def test_f1_identity_known_unverified_entry_is_not_verified():
    manifest = c.make_manifest(c.make_scope("cie-questions", expected=1))
    entries = [c.make_entry("q:cie:synthetic-1",
                            quality=c.QUALITY_PARTIAL_UNVERIFIED)]
    row = c.row_for_scope(build_published(entries, manifest), "cie-questions")
    assert row["verified"] == 0, (
        "an identity-known entry with content=partial and answer_verification="
        f"unverified was counted verified: {row!r}")
    assert row["partial"] == 1
    assert row["observed"] == 1
    assert row["derived_status"] == "partial"
    assert row["percentage"] == 0.0
    assert row.get("expected") == 1
    assert row.get("unmet") == 0
    assert row.get("identity_complete") == 1
    assert row.get("content_complete") == 0
    assert row.get("answers_verified") == 0


def test_f1_verified_requires_content_and_answer_verification():
    entries = [
        c.make_entry("q:cie:a", quality=c.QUALITY_VERIFIED),
        c.make_entry("q:cie:b", quality=c.QUALITY_COMPLETE_UNVERIFIED),
        c.make_entry("q:cie:c", quality=c.QUALITY_PARTIAL_UNVERIFIED),
        c.make_entry("q:cie:d", quality=c.QUALITY_CONFLICTING),
        c.make_entry("q:cie:e", quality=None),
    ]
    manifest = c.make_manifest(c.make_scope("cie-questions", expected=5))
    row = c.row_for_scope(build_published(entries, manifest), "cie-questions")
    assert row["verified"] == 1
    assert row["partial"] == 3
    assert row["unknown"] == 1
    assert row["observed"] == 5
    assert row["derived_status"] == "partial"
    assert row["percentage"] == 20.0
    assert row.get("identity_complete") == 5
    assert row.get("content_complete") == 3
    assert row.get("answers_verified") == 1


def test_f1_identity_rules_still_hold():
    manifest = c.make_manifest(c.make_scope("cie-questions", expected=2))
    entries = [
        c.make_entry("q:cie:top", quality=c.QUALITY_VERIFIED,
                     identity={"native_id": "n-1", "parent_native_id": c.UNKNOWN}),
        c.make_entry("q:cie:lost", quality=c.QUALITY_VERIFIED,
                     identity={"native_id": c.UNKNOWN}),
    ]
    row = c.row_for_scope(build_published(entries, manifest), "cie-questions")
    assert row["verified"] == 1
    assert row["unknown"] == 1
    assert row["derived_status"] == "partial"


# --------------------------------------------------------------------------- #
# F2 — expected and observed stay distinct; conflicts never render complete.
# --------------------------------------------------------------------------- #
def test_f2_expected_below_published_is_never_complete():
    manifest = c.make_manifest(c.make_scope("cie-questions", expected=1))
    entries = [c.make_entry("q:cie:a", quality=c.QUALITY_VERIFIED),
               c.make_entry("q:cie:b", quality=c.QUALITY_VERIFIED)]
    view = build_published(entries, manifest)
    row = c.row_for_scope(view, "cie-questions")
    assert row["observed"] == 2
    assert row["derived_status"] == "partial", (
        f"expected=1 with 2 published entries still rendered "
        f"{row['derived_status']!r}: {row!r}")
    assert row["percentage"] is None
    assert row.get("expected") == 1
    assert row["missing"] == 0
    assert row.get("unmet") == 0
    assert any(problem.get("code") == "expected_below_published"
               and problem.get("expected") == 1
               and problem.get("published") == 2
               for problem in view.problems), view.problems


def test_f2_missing_entries_stay_on_the_expected_side():
    manifest = c.make_manifest(c.make_scope("cie-questions", expected=3))
    entries = [c.make_entry("q:cie:a", quality=c.QUALITY_VERIFIED)]
    row = c.row_for_scope(build_published(entries, manifest), "cie-questions")
    assert row["observed"] == 1, (
        f"only one entry is published, but the row claims observed="
        f"{row['observed']!r}: {row!r}")
    assert row.get("expected") == 3
    assert row.get("unmet") == 2
    assert row["missing"] == 0
    assert row["derived_status"] == "partial"
    assert row["percentage"] == 33.33
    assert Coverage.from_dict(row).validate() == []


def test_f2_unknown_denominator_never_claims_completion():
    manifest = c.make_manifest(c.make_scope("cie-questions", expected=None))
    entries = [c.make_entry("q:cie:a", quality=c.QUALITY_VERIFIED)]
    row = c.row_for_scope(build_published(entries, manifest), "cie-questions")
    assert row["denominator_known"] is False
    assert row["denominator"] is None
    assert row.get("expected") is None
    assert row["observed"] == 1
    assert row["derived_status"] == "unknown"
    assert row["percentage"] is None


def test_f2_zero_expected_empty_scope_is_not_complete():
    manifest = c.make_manifest(c.make_scope("cie-questions", expected=0))
    row = c.row_for_scope(build_published([], manifest), "cie-questions")
    assert row["observed"] == 0
    assert row.get("expected") == 0
    assert row["derived_status"] == "partial"
    assert row["percentage"] is None
    assert row.get("unmet") == 0


def test_f2_zero_expected_with_published_entries_is_a_conflict():
    manifest = c.make_manifest(c.make_scope("cie-questions", expected=0))
    entries = [c.make_entry("q:cie:a", quality=c.QUALITY_VERIFIED)]
    view = build_published(entries, manifest)
    row = c.row_for_scope(view, "cie-questions")
    assert row["observed"] == 1
    assert row.get("expected") == 0
    assert row["derived_status"] == "partial"
    assert row["percentage"] is None
    assert any(problem.get("code") == "expected_below_published"
               for problem in view.problems), view.problems


def test_f2_exclusions_and_manifest_partials_keep_reasons():
    manifest = c.make_manifest(c.make_scope(
        "cie-questions", expected=4,
        exclusions=(("q:cie:dup", "duplicate of an earlier sample"),),
        partial=(("q:cie:man", "manifest records this sample as partial"),)))
    entries = [c.make_entry("q:cie:ok", quality=c.QUALITY_VERIFIED),
               c.make_entry("q:cie:dup", quality=c.QUALITY_VERIFIED),
               c.make_entry("q:cie:man", quality=c.QUALITY_VERIFIED)]
    view = build_published(entries, manifest)
    row = c.row_for_scope(view, "cie-questions")
    assert row["verified"] == 1
    assert row["excluded"] == 1
    assert row["partial"] == 1
    assert row["unknown"] == 0
    assert row["observed"] == 3
    assert row.get("expected") == 4
    assert row.get("unmet") == 1
    assert row["percentage"] == 33.33
    assert row["derived_status"] == "partial"
    assert row["exclusions"] == [{"public_id": "q:cie:dup",
                                  "reason": "duplicate of an earlier sample"}]
    assert view.problems == []


# --------------------------------------------------------------------------- #
# Multi-scope processing across the supported iterable input types.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("container", ["list", "tuple", "generator"])
def test_multi_scope_processing_accepts_supported_iterables(container):
    manifest = c.make_manifest(
        c.make_scope("cie-questions", system="cie", kind="question", expected=1),
        c.make_scope("edexcel-questions", system="edexcel", kind="question",
                     expected=1))
    base = [c.make_entry("q:cie:a", system="cie", quality=c.QUALITY_VERIFIED),
            c.make_entry("q:edexcel:a", system="edexcel",
                         quality=c.QUALITY_VERIFIED)]
    if container == "list":
        entries = list(base)
    elif container == "tuple":
        entries = tuple(base)
    else:
        entries = (entry for entry in base)
    view = build_published(entries, manifest)
    for scope_id in ("cie-questions", "edexcel-questions"):
        row = c.row_for_scope(view, scope_id)
        assert row["observed"] == 1, f"{container} input: {row!r}"
        assert row["verified"] == 1
        assert row["derived_status"] == "complete"
        assert row["percentage"] == 100.0


def test_published_rows_keep_contract_fields_and_validate():
    manifest = c.make_manifest(c.make_scope("cie-questions", expected=2))
    entries = [c.make_entry("q:cie:a", quality=c.QUALITY_VERIFIED),
               c.make_entry("q:cie:b", quality=c.QUALITY_COMPLETE_UNVERIFIED)]
    row = c.row_for_scope(build_published(entries, manifest), "cie-questions")
    missing_keys = ROW_CONTRACT_KEYS - set(row)
    assert not missing_keys, f"row lost contract fields: {sorted(missing_keys)}"
    assert row["denominator_known"] is True
    assert "expected=2" in row["denominator"]
    assert Coverage.from_dict(row).validate() == []
