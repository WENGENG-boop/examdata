"""Type-specific completeness rules (plan 4.7).

Rules frozen here:

* a requirement list is built per question type, so an essay is not "incomplete"
  for having no options, while a diagram-label question *is* incomplete when its
  required image is missing;
* a table-choice question requires columns, rows and the applicable answer
  structure;
* a percentage is produced only when the denominator is known - unknown expected
  coverage yields ``None`` plus an explicit gap;
* exclusions stay visible with their reasons;
* unrelated systems are never averaged into one project percentage.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from .base import Gap
from .enums import GapCode, GapScope, QuestionType
from .models import Container, Coverage, Question
from .quality import QualityAnswerPresence


class CrossSystemAggregationError(ValueError):
    """Raised when a single percentage across exam systems is requested."""


@dataclass
class Requirement:
    name: str
    satisfied: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "satisfied": self.satisfied, "detail": self.detail}


@dataclass
class CompletenessResult:
    scope: str
    requirements: list[Requirement] = field(default_factory=list)
    gaps: list[Gap] = field(default_factory=list)
    raw_counts: dict[str, int] = field(default_factory=dict)
    denominator_known: bool = False
    derived_status: str = "unknown"
    percentage: float | None = None

    @property
    def satisfied(self) -> int:
        return sum(1 for r in self.requirements if r.satisfied)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "derived_status": self.derived_status,
            "denominator_known": self.denominator_known,
            "percentage": self.percentage,
            "raw_counts": dict(self.raw_counts),
            "requirements": [r.to_dict() for r in self.requirements],
            "gaps": [g.to_dict() for g in self.gaps],
        }

    def to_coverage(self, *, public_id: str | None = None, computed_at: str | None = None,
                    evidence: Sequence[str] = ()) -> Coverage:
        """Project this result onto a :class:`Coverage` whose buckets partition ``observed``.

        Every evaluated requirement is placed in exactly one bucket, so
        ``observed == excluded + unknown + missing + partial + verified`` (the
        invariant :meth:`Coverage.validate` enforces). A requirement confirmed
        satisfied for this scope lands in ``verified``; an unsatisfied one lands
        in ``missing``. This counts *requirement satisfaction for the scope*, not
        source-content verification - content quality is tracked separately by
        the ``Quality`` dimensions and is never inferred from a coverage bucket.
        """
        counts = dict(self.raw_counts)
        verified = int(counts.get("verified", counts.get("satisfied", 0)) or 0)
        missing = int(counts.get("missing", counts.get("unsatisfied", 0)) or 0)
        unknown = int(counts.get("unknown", 0) or 0)
        partial = int(counts.get("partial", 0) or 0)
        excluded = int(counts.get("excluded", 0) or 0)
        return Coverage(
            public_id=public_id,
            scope=self.scope,
            denominator=str(len(self.requirements)),
            denominator_known=self.denominator_known,
            observed=verified + missing + unknown + partial + excluded,
            excluded=excluded,
            unknown=unknown,
            missing=missing,
            partial=partial,
            verified=verified,
            exclusions=list(counts.get("exclusions", []) if isinstance(counts.get("exclusions"), list) else []),
            computed_at=computed_at,
            evidence=list(evidence),
            derived_status=self.derived_status,
            percentage=self.percentage,
        )


def _requirement(name: str, satisfied: bool, detail: str = "") -> Requirement:
    return Requirement(name=name, satisfied=bool(satisfied), detail=detail)


def _type_requirements(question: Question) -> list[Requirement]:
    """Required structure per question type (plan 4.7)."""
    from .models import (LabelsPayload, MatchingPayload, OptionsPayload, TablePayload,
                         TextPayload)

    payload = question.payload
    qtype = question.question_type
    reqs: list[Requirement] = []

    if qtype in (QuestionType.SINGLE_CHOICE, QuestionType.MULTIPLE_CHOICE):
        reqs.append(_requirement("options", isinstance(payload, OptionsPayload)
                                 and len(payload.options) > 0,
                                 "choice questions require a non-empty options list"))
    elif qtype is QuestionType.TABLE_CHOICE:
        table_ok = isinstance(payload, TablePayload)
        reqs.append(_requirement("table_columns", table_ok and bool(payload.columns)))
        reqs.append(_requirement("table_rows", table_ok and bool(payload.rows)))
        reqs.append(_requirement("table_answer_structure", table_ok and bool(payload.answer_cells),
                                 "a table-choice question requires its answer cells"))
    elif qtype is QuestionType.MATCHING:
        reqs.append(_requirement("matching_lists", isinstance(payload, MatchingPayload)
                                 and bool(payload.left) and bool(payload.right)))
    elif qtype is QuestionType.DIAGRAM_LABELS:
        reqs.append(_requirement("diagram_asset", isinstance(payload, LabelsPayload)
                                 and bool(payload.asset_ref),
                                 "a diagram-label question is incomplete without its image"))
        reqs.append(_requirement("diagram_labels", isinstance(payload, LabelsPayload)
                                 and bool(payload.labels)))
    elif qtype in (QuestionType.FILL_BLANK, QuestionType.SHORT_ANSWER, QuestionType.ESSAY,
                   QuestionType.SPEAKING):
        # no options are required for these types
        reqs.append(_requirement("stem", bool(question.stem) or
                                 (isinstance(payload, TextPayload) and bool(payload.stem))))
    elif qtype is QuestionType.UNKNOWN:
        reqs.append(_requirement("native_shape_known", False,
                                 "unknown question type: completeness cannot be judged"))

    for asset in question.required_assets:
        if asset.required:
            reqs.append(_requirement(
                f"required_asset:{asset.role}",
                bool(asset.sha256 or asset.asset_ref),
                "required asset has neither a hash nor a reference",
            ))
    return reqs


def evaluate_question(question: Question, *, expected_children: int | None = None) -> CompletenessResult:
    """Evaluate one question (and its sub-parts) against its type requirements."""
    reqs = _type_requirements(question)
    gaps: list[Gap] = []

    for child in question.children:
        child_result = evaluate_question(child)
        reqs.append(_requirement(f"child:{child.native_id or child.public_id}",
                                 child_result.derived_status == "complete",
                                 "; ".join(g.detail or g.code for g in child_result.gaps)))
        gaps.extend(child_result.gaps)

    if expected_children is not None:
        reqs.append(_requirement("expected_children", len(question.children) == expected_children,
                                 f"expected {expected_children}, found {len(question.children)}"))

    quality = question.quality
    answer_present = bool(question.answers) or any(
        a.original_value is not None or a.conflicts for a in question.answers)
    if quality is not None and quality.answer_presence is QualityAnswerPresence.MISSING:
        gaps.append(Gap(code=GapCode.MISSING_ANSWER_SLOT.value, scope=GapScope.QUESTION.value,
                        detail="answer slot preserved as missing"))
    elif not answer_present and question.question_type is not QuestionType.UNKNOWN:
        gaps.append(Gap(code=GapCode.MISSING_ANSWER.value, scope=GapScope.QUESTION.value,
                        detail="no answer recorded"))

    if question.payload is None and question.question_type is not QuestionType.UNKNOWN:
        gaps.append(Gap(code=GapCode.MISSING_OPTIONS.value, scope=GapScope.QUESTION.value,
                        detail=f"no payload for type {question.question_type.value}"))
    if any(not r.satisfied and r.name.startswith("required_asset:") for r in reqs):
        gaps.append(Gap(code=GapCode.MISSING_REQUIRED_IMAGE.value, scope=GapScope.QUESTION.value,
                        detail="a required image/asset is missing"))

    result = CompletenessResult(
        scope=f"question:{question.native_id or question.public_id}",
        requirements=reqs,
        gaps=gaps,
        denominator_known=question.question_type is not QuestionType.UNKNOWN,
    )
    _finalise(result)
    return result


def evaluate_container(container: Container, questions: Sequence[Question],
                       *, expected_questions: int | None = None) -> CompletenessResult:
    """Evaluate a container from its questions; the denominator is the container."""
    reqs: list[Requirement] = []
    gaps: list[Gap] = []
    for question in questions:
        q_result = evaluate_question(question)
        reqs.append(_requirement(f"question:{question.native_id or question.public_id}",
                                 q_result.derived_status == "complete"))
        gaps.extend(q_result.gaps)
    if expected_questions is not None:
        reqs.append(_requirement("expected_questions", len(questions) == expected_questions,
                                 f"expected {expected_questions}, found {len(questions)}"))
    denominator_known = expected_questions is not None and expected_questions > 0
    result = CompletenessResult(
        scope=f"container:{container.native_identity.get('native_id') or container.public_id}",
        requirements=reqs,
        gaps=gaps,
        denominator_known=denominator_known,
    )
    _finalise(result)
    return result


def _finalise(result: CompletenessResult) -> None:
    total = len(result.requirements)
    ok = result.satisfied
    result.raw_counts = {
        "requirements": total,
        "satisfied": ok,
        "unsatisfied": total - ok,
        "gaps": len(result.gaps),
    }
    if not result.denominator_known:
        result.derived_status = "unknown"
        result.percentage = None
        result.gaps.append(Gap(code=GapCode.UNKNOWN_COVERAGE.value, scope=GapScope.COVERAGE.value,
                               detail="expected coverage is unknown: no percentage is computed"))
        return
    if total == 0:
        result.derived_status = "unknown"
        result.percentage = None
        return
    result.percentage = round(100.0 * ok / total, 2)
    if ok == total:
        result.derived_status = "complete"
    elif ok == 0:
        result.derived_status = "missing"
    else:
        result.derived_status = "partial"


def per_system_coverage(results: Mapping[str, CompletenessResult]) -> dict[str, dict[str, Any]]:
    """Group completeness by exam system; never merge them into one number."""
    grouped: dict[str, dict[str, Any]] = {}
    for system, result in results.items():
        grouped[system] = {
            "derived_status": result.derived_status,
            "percentage": result.percentage,
            "denominator_known": result.denominator_known,
            "raw_counts": dict(result.raw_counts),
        }
    return grouped


def project_percentage(*_args: Any, **_kwargs: Any) -> float:
    """Always refused: unrelated systems must not be averaged (plan 4.7)."""
    raise CrossSystemAggregationError(
        "a single project percentage across CIE, Edexcel, IELTS and TOEFL is not meaningful; "
        "report per-system coverage instead"
    )


__all__ = [
    "Requirement",
    "CompletenessResult",
    "CrossSystemAggregationError",
    "evaluate_question",
    "evaluate_container",
    "per_system_coverage",
    "project_percentage",
]
