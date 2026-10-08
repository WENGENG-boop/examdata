"""Quality dimensions and the evidence-permitted transition table (plan 4.6).

The plan forbids a single misleading ``verified`` flag. Instead every record
carries independent dimensions, and a dimension may only move to a stronger
value when the evidence actually supports it:

* a hash check proves file identity/integrity, **not** that an audio file is
  correctly associated with a question - so ``audio_integrity`` can reach
  ``hash_verified`` while ``audio_alignment`` stays ``unverified``;
* agreement between two unofficial sources never yields ``source_verified``;
* an HTTP 200, a plausible filename, or a title match proves nothing at all and
  is listed in :data:`FORBIDDEN_BASIS`.

``can_transition`` is the single decision point; adapters must call it instead
of assigning quality values directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

from .base import ContractModel, Gap
from .enums import (
    EvidenceLabel,
    GapCode,
    GapScope,
    QualityAnswerPresence,
    QualityAnswerVerification,
    QualityAssets,
    QualityAudioAlignment,
    QualityAudioIntegrity,
    QualityContent,
    QualityRegionVerification,
)

DIMENSIONS: dict[str, type[Enum]] = {
    "content": QualityContent,
    "answer_presence": QualityAnswerPresence,
    "answer_verification": QualityAnswerVerification,
    "assets": QualityAssets,
    "audio_integrity": QualityAudioIntegrity,
    "audio_alignment": QualityAudioAlignment,
    "region_verification": QualityRegionVerification,
}

# Evidence that may establish that a value came verbatim from an authoritative
# source. Synthetic fixtures are deliberately absent: synthetic content can be
# internally consistent but it is not source-verified real content.
AUTHORITATIVE_EVIDENCE = frozenset({
    EvidenceLabel.COPIED_SNAPSHOT,
    EvidenceLabel.ISOLATED_REAL_DATA,
    EvidenceLabel.FULL_SOURCE_VALIDATION,
    EvidenceLabel.DEPLOYED_TARGET_VALIDATION,
})

HASH_EVIDENCE = frozenset({
    EvidenceLabel.COPIED_SNAPSHOT,
    EvidenceLabel.ISOLATED_REAL_DATA,
    EvidenceLabel.FULL_SOURCE_VALIDATION,
})

RENDER_EVIDENCE = frozenset({
    EvidenceLabel.ISOLATED_REAL_DATA,
    EvidenceLabel.FULL_SOURCE_VALIDATION,
})

STATIC_EVIDENCE = frozenset({
    EvidenceLabel.STATIC_INSPECTION,
    EvidenceLabel.SYNTHETIC_FIXTURE,
}) | AUTHORITATIVE_EVIDENCE

# Bases that may never justify a quality transition (plan 4.6).
FORBIDDEN_BASIS: dict[str, str] = {
    "http_status_only": "a source page returning 200 proves neither content validity nor completeness",
    "two_unofficial_sources_agree": "agreement between two unofficial sources is not official verification",
    "filename_similarity": "a similar filename is not evidence of identity or correctness",
    "title_similarity": "title/semantic similarity is never an identity or verification rule (plan 4.2 rule 10)",
    "row_number": "a database row number is not a cross-system identity (plan 4.2 rule 2)",
    "hash_implies_alignment": "a hash proves integrity, not audio-to-question association",
    "fixture_implies_real": "synthetic or fixture content never becomes verified real content",
}


class QualityTransitionError(ValueError):
    """A requested quality transition is not permitted by its evidence."""


@dataclass(frozen=True)
class Transition:
    dimension: str
    source: str
    target: str
    evidence: frozenset[EvidenceLabel]
    requires: str | None = None
    note: str = ""


def _t(dimension: str, source: str, target: str, evidence: Iterable[EvidenceLabel],
       requires: str | None = None, note: str = "") -> Transition:
    return Transition(dimension, source, target, frozenset(evidence), requires, note)


TRANSITIONS: tuple[Transition, ...] = (
    # -- content ---------------------------------------------------------------
    _t("content", "unknown", "missing", STATIC_EVIDENCE,
       note="the record is known to lack the required content"),
    _t("content", "unknown", "partial", STATIC_EVIDENCE,
       note="some required content is present and some is known to be absent"),
    _t("content", "unknown", "complete", AUTHORITATIVE_EVIDENCE | {EvidenceLabel.SYNTHETIC_FIXTURE},
       requires="denominator_known",
       note="completeness needs an explicit denominator; without one only partial is reachable"),
    _t("content", "missing", "partial", STATIC_EVIDENCE),
    _t("content", "partial", "complete", AUTHORITATIVE_EVIDENCE | {EvidenceLabel.SYNTHETIC_FIXTURE},
       requires="denominator_known"),
    _t("content", "complete", "partial", STATIC_EVIDENCE,
       note="demotion is always allowed when new gaps are found"),
    _t("content", "partial", "missing", STATIC_EVIDENCE),
    # -- answer presence -------------------------------------------------------
    _t("answer_presence", "unknown", "present", STATIC_EVIDENCE, requires="answer_value_present"),
    _t("answer_presence", "unknown", "missing", STATIC_EVIDENCE, requires="missing_slot_marked",
       note="a missing slot is only 'missing' when the source marks it as such"),
    _t("answer_presence", "present", "missing", STATIC_EVIDENCE, requires="missing_slot_marked"),
    _t("answer_presence", "missing", "present", AUTHORITATIVE_EVIDENCE, requires="answer_value_present"),
    # -- answer verification ---------------------------------------------------
    _t("answer_verification", "unknown", "unverified", STATIC_EVIDENCE),
    _t("answer_verification", "unverified", "source_verified", AUTHORITATIVE_EVIDENCE,
       note="synthetic fixtures can never reach source_verified"),
    _t("answer_verification", "unverified", "conflicting", STATIC_EVIDENCE,
       requires="conflict_candidates_present"),
    _t("answer_verification", "conflicting", "manual_adjudicated", STATIC_EVIDENCE,
       requires="manual_decision_present"),
    _t("answer_verification", "source_verified", "conflicting", AUTHORITATIVE_EVIDENCE,
       requires="conflict_candidates_present"),
    _t("answer_verification", "manual_adjudicated", "source_verified", AUTHORITATIVE_EVIDENCE,
       note="a later authoritative source may supersede a manual decision; the decision is kept"),
    # -- assets ----------------------------------------------------------------
    _t("assets", "unknown", "external_only", STATIC_EVIDENCE),
    _t("assets", "unknown", "missing", STATIC_EVIDENCE, requires="required_asset_missing"),
    _t("assets", "unknown", "embedded", HASH_EVIDENCE, requires="asset_hash_present"),
    _t("assets", "external_only", "embedded", HASH_EVIDENCE, requires="asset_hash_present"),
    _t("assets", "embedded", "missing", STATIC_EVIDENCE, requires="required_asset_missing"),
    _t("assets", "unknown", "not_applicable", STATIC_EVIDENCE, requires="no_required_assets"),
    # -- audio -----------------------------------------------------------------
    _t("audio_integrity", "unknown", "unverified", STATIC_EVIDENCE),
    _t("audio_integrity", "unverified", "hash_verified", HASH_EVIDENCE, requires="asset_hash_present"),
    _t("audio_integrity", "hash_verified", "hash_mismatch", HASH_EVIDENCE, requires="hash_mismatch_observed"),
    _t("audio_integrity", "unknown", "not_applicable", STATIC_EVIDENCE, requires="no_required_assets"),
    _t("audio_alignment", "unknown", "unverified", STATIC_EVIDENCE,
       note="alignment starts unverified; a hash check must never promote it"),
    _t("audio_alignment", "unverified", "verified", RENDER_EVIDENCE, requires="alignment_evidence_present",
       note="requires explicit alignment evidence, not merely a matching hash"),
    _t("audio_alignment", "verified", "unverified", STATIC_EVIDENCE),
    _t("audio_alignment", "unknown", "not_applicable", STATIC_EVIDENCE, requires="no_required_assets"),
    # -- regions ---------------------------------------------------------------
    _t("region_verification", "unknown", "unverified", STATIC_EVIDENCE),
    _t("region_verification", "unverified", "verified", RENDER_EVIDENCE, requires="region_evidence_present"),
    _t("region_verification", "verified", "unverified", STATIC_EVIDENCE),
    _t("region_verification", "unknown", "not_applicable", STATIC_EVIDENCE, requires="no_regions"),
)


@dataclass(frozen=True)
class TransitionResult:
    allowed: bool
    reason: str
    transition: Transition | None = None


def _find(dimension: str, source: str, target: str) -> Transition | None:
    for t in TRANSITIONS:
        if t.dimension == dimension and t.source == source and t.target == target:
            return t
    return None


def allowed_targets(dimension: str, source: str) -> list[str]:
    return sorted({t.target for t in TRANSITIONS if t.dimension == dimension and t.source == source})


def can_transition(
    dimension: str,
    source: str,
    target: str,
    evidence: EvidenceLabel | str,
    *,
    context: Mapping[str, Any] | None = None,
    basis: str | None = None,
) -> TransitionResult:
    """Decide whether a dimension may move from `source` to `target`."""
    if dimension not in DIMENSIONS:
        return TransitionResult(False, f"unknown quality dimension {dimension!r}")
    enum_cls = DIMENSIONS[dimension]
    try:
        src = enum_cls.coerce(source).value
        dst = enum_cls.coerce(target).value
    except ValueError as exc:
        return TransitionResult(False, str(exc))
    try:
        label = EvidenceLabel.coerce(evidence)
    except ValueError as exc:
        return TransitionResult(False, str(exc))
    if basis is not None:
        if basis in FORBIDDEN_BASIS:
            return TransitionResult(False, f"forbidden basis {basis!r}: {FORBIDDEN_BASIS[basis]}")
        return TransitionResult(False, f"unrecognised basis {basis!r}: evidence must be a recorded observation")
    if src == dst:
        return TransitionResult(True, "no change")
    transition = _find(dimension, src, dst)
    if transition is None:
        return TransitionResult(
            False,
            f"{dimension}: {src} -> {dst} is not in the transition table "
            f"(allowed: {allowed_targets(dimension, src)})",
        )
    if label not in transition.evidence:
        return TransitionResult(
            False,
            f"{dimension}: {src} -> {dst} requires evidence in "
            f"{sorted(e.value for e in transition.evidence)}, not {label.value}",
            transition,
        )
    if transition.requires:
        ctx = context or {}
        if not ctx.get(transition.requires):
            return TransitionResult(
                False,
                f"{dimension}: {src} -> {dst} requires {transition.requires}, which is not satisfied",
                transition,
            )
    return TransitionResult(True, transition.note or "permitted", transition)


@dataclass
class Quality(ContractModel):
    """Independent quality dimensions plus visible gaps (plan 4.6)."""

    SCHEMA = "quality/1"

    content: QualityContent = QualityContent.UNKNOWN
    answer_presence: QualityAnswerPresence = QualityAnswerPresence.UNKNOWN
    answer_verification: QualityAnswerVerification = QualityAnswerVerification.UNKNOWN
    assets: QualityAssets = QualityAssets.UNKNOWN
    audio_integrity: QualityAudioIntegrity = QualityAudioIntegrity.UNKNOWN
    audio_alignment: QualityAudioAlignment = QualityAudioAlignment.UNKNOWN
    region_verification: QualityRegionVerification = QualityRegionVerification.UNKNOWN
    gaps: list[Gap] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Quality":
        def pick(name: str, enum_cls):
            return enum_cls.coerce(payload.get(name, "unknown"))

        return cls(
            content=pick("content", QualityContent),
            answer_presence=pick("answer_presence", QualityAnswerPresence),
            answer_verification=pick("answer_verification", QualityAnswerVerification),
            assets=pick("assets", QualityAssets),
            audio_integrity=pick("audio_integrity", QualityAudioIntegrity),
            audio_alignment=pick("audio_alignment", QualityAudioAlignment),
            region_verification=pick("region_verification", QualityRegionVerification),
            gaps=[Gap.from_dict(g) for g in payload.get("gaps", [])],
        )

    def value(self, dimension: str) -> str:
        return getattr(self, dimension).value

    def validate(self) -> list[str]:
        problems = []
        for gap in self.gaps:
            try:
                GapCode.coerce(gap.code)
            except ValueError:
                problems.append(f"quality: unknown gap code {gap.code!r}")
            try:
                GapScope.coerce(gap.scope)
            except ValueError:
                problems.append(f"quality: unknown gap scope {gap.scope!r}")
        if self.audio_alignment is QualityAudioAlignment.VERIFIED \
                and self.audio_integrity is QualityAudioIntegrity.UNVERIFIED:
            problems.append(
                "quality: audio alignment is verified while integrity is unverified - "
                "alignment evidence must also establish integrity")
        return problems

    def apply(
        self,
        dimension: str,
        target: str,
        evidence: EvidenceLabel | str,
        *,
        context: Mapping[str, Any] | None = None,
        basis: str | None = None,
        gap: Gap | None = None,
    ) -> "Quality":
        """Return a copy with the dimension moved, or raise if not permitted."""
        current = self.value(dimension) if dimension in DIMENSIONS else None
        if current is None:
            raise QualityTransitionError(f"unknown quality dimension {dimension!r}")
        result = can_transition(dimension, current, target, evidence, context=context, basis=basis)
        if not result.allowed:
            raise QualityTransitionError(result.reason)
        setattr(self, dimension, DIMENSIONS[dimension].coerce(target))
        if gap is not None:
            self.gaps.append(gap)
        return self


def transition_table() -> list[dict[str, Any]]:
    """Machine-readable form of the transition table (used by the A04 evidence)."""
    return [
        {
            "dimension": t.dimension,
            "from": t.source,
            "to": t.target,
            "evidence": sorted(e.value for e in t.evidence),
            "requires": t.requires,
            "note": t.note,
        }
        for t in TRANSITIONS
    ]


__all__ = [
    "DIMENSIONS",
    "AUTHORITATIVE_EVIDENCE",
    "HASH_EVIDENCE",
    "RENDER_EVIDENCE",
    "STATIC_EVIDENCE",
    "FORBIDDEN_BASIS",
    "Transition",
    "TRANSITIONS",
    "TransitionResult",
    "QualityTransitionError",
    "Quality",
    "can_transition",
    "allowed_targets",
    "transition_table",
]
