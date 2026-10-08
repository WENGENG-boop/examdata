"""A04 - quality dimensions and the evidence-permitted transition table (plan 4.6).

Proves the frozen rules: synthetic fixtures can never reach ``source_verified``;
a hash check proves integrity, never audio-to-question alignment; every
forbidden basis is refused; ``Quality.apply`` refuses an illegal move; and a
record whose alignment is verified while integrity is unverified is flagged.
"""
from __future__ import annotations

import pytest

from examdata_integration.contracts.enums import (
    QualityAnswerVerification,
    QualityAudioAlignment,
    QualityAudioIntegrity,
)
from examdata_integration.contracts.quality import (
    FORBIDDEN_BASIS,
    Quality,
    QualityTransitionError,
    allowed_targets,
    can_transition,
)


def test_synthetic_fixture_never_reaches_source_verified():
    res = can_transition("answer_verification", "unverified", "source_verified", "synthetic_fixture")
    assert not res.allowed
    assert "source_verified" in res.reason or "requires evidence" in res.reason

    q = Quality()
    q.apply("answer_verification", "unverified", "synthetic_fixture")  # unknown -> unverified is fine
    with pytest.raises(QualityTransitionError):
        q.apply("answer_verification", "source_verified", "synthetic_fixture")
    assert q.answer_verification is QualityAnswerVerification.UNVERIFIED


def test_copied_snapshot_may_verify_answers():
    q = Quality()
    q.apply("answer_verification", "unverified", "synthetic_fixture")
    q.apply("answer_verification", "source_verified", "copied_snapshot")
    assert q.answer_verification is QualityAnswerVerification.SOURCE_VERIFIED


def test_hash_verifies_integrity_not_alignment():
    q = Quality()
    q.apply("audio_integrity", "unverified", "synthetic_fixture")
    q.apply("audio_integrity", "hash_verified", "copied_snapshot",
            context={"asset_hash_present": True})
    q.apply("audio_alignment", "unverified", "synthetic_fixture")

    assert q.audio_integrity is QualityAudioIntegrity.HASH_VERIFIED
    assert q.audio_alignment is QualityAudioAlignment.UNVERIFIED

    # a hash is not alignment evidence: the move must be refused
    res = can_transition("audio_alignment", "unverified", "verified", "copied_snapshot",
                         context={"alignment_evidence_present": True})
    assert not res.allowed
    # alignment needs render evidence
    ok = can_transition("audio_alignment", "unverified", "verified", "isolated_real_data",
                        context={"alignment_evidence_present": True})
    assert ok.allowed


def test_quality_validate_flags_verified_alignment_without_integrity():
    q = Quality(audio_alignment=QualityAudioAlignment.VERIFIED,
                audio_integrity=QualityAudioIntegrity.UNVERIFIED)
    problems = q.validate()
    assert problems and any("integrity" in p for p in problems)


@pytest.mark.parametrize("basis", sorted(FORBIDDEN_BASIS))
def test_forbidden_basis_is_refused(basis):
    res = can_transition("content", "unknown", "partial", "synthetic_fixture", basis=basis)
    assert not res.allowed
    assert "forbidden basis" in res.reason
    with pytest.raises(QualityTransitionError):
        Quality().apply("content", "partial", "synthetic_fixture", basis=basis)


def test_unrecognised_basis_is_refused():
    res = can_transition("content", "unknown", "partial", "synthetic_fixture", basis="vibes")
    assert not res.allowed
    assert "unrecognised basis" in res.reason


def test_apply_raises_on_move_absent_from_the_table():
    from examdata_integration.contracts.enums import QualityContent

    q = Quality(content=QualityContent.COMPLETE)
    with pytest.raises(QualityTransitionError):
        q.apply("content", "unknown", "synthetic_fixture")  # complete -> unknown not in table


def test_requires_context_gate_is_enforced():
    # content: unknown -> complete needs a known denominator
    res = can_transition("content", "unknown", "complete", "synthetic_fixture")
    assert not res.allowed and "denominator_known" in res.reason
    ok = can_transition("content", "unknown", "complete", "synthetic_fixture",
                        context={"denominator_known": True})
    assert ok.allowed


def test_unknown_dimension_and_evidence_are_refused():
    assert not can_transition("not_a_dimension", "unknown", "partial", "synthetic_fixture").allowed
    assert not can_transition("content", "unknown", "partial", "not_an_evidence_label").allowed


def test_allowed_targets_reports_the_table():
    targets = allowed_targets("answer_verification", "unverified")
    assert "source_verified" in targets and "conflicting" in targets
    assert allowed_targets("answer_verification", "source_verified") == ["conflicting"]
