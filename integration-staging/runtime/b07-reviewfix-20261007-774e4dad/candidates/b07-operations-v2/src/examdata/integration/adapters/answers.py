"""Answer resolution for the read adapters (plan A07).

A raw index states answers in three different ways and an adapter must not blur
them:

* ``exact``   - the answer is recorded on the question itself;
* ``ancestor``- the question carries no answer, so the nearest ancestor's answer
  applies to it; the resolved answer is tagged ``matching_method=ancestor`` and
  keeps a lineage reference to the ancestor, so nobody mistakes it for an answer
  the question actually stated;
* ``descendants`` - the question carries no answer of its own but its parts do;
  the adapter synthesises one answer whose alternatives are the parts' values, in
  order, tagged ``matching_method=descendants``;
* ``none``    - no resolution at all: only an answer the question itself states
  is kept, and nothing is inherited or derived.

Whatever the mode, an answer the index does not state is never invented: a
question with no answer reachable in its mode yields a ``missing_answer``
problem and no answer. Every emitted answer stays ``verification=unverified``
and ``content_class=synthetic``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from ..contracts.base import Gap
from ..contracts.canonical import public_id
from ..contracts.enums import (
    AnswerMatchingMethod,
    ContentClass,
    EntityKind,
    GapScope,
)
from ..contracts.models import Answer, Conflict, Lineage, ManualDecision, SourceRef
from .problems import AdapterProblem, ProblemCode, problem


class AnswerMode(str, Enum):
    EXACT = "exact"
    ANCESTOR = "ancestor"
    DESCENDANTS = "descendants"
    NONE = "none"

    @classmethod
    def coerce(cls, value: Any) -> "AnswerMode | None":
        if value is None:
            return None
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value).lower())
        except ValueError:
            return None


@dataclass
class ResolvedAnswers:
    """Answers keyed by question native id, plus the mode used and any problems."""

    by_native_id: dict[str, list[Answer]] = field(default_factory=dict)
    modes: dict[str, str] = field(default_factory=dict)
    problems: list[AdapterProblem] = field(default_factory=list)

    def for_question(self, native_id: str) -> list[Answer]:
        return list(self.by_native_id.get(native_id, []))


def resolve_answers(questions: list[Mapping[str, Any]], *, default_mode: Any = AnswerMode.EXACT,
                    system: str, container_native: Mapping[str, Any],
                    source_id: str, provider_id: str, fixture_name: str) -> ResolvedAnswers:
    """Resolve the answers of a raw question tree in one system's fixture."""
    fallback = AnswerMode.coerce(default_mode) or AnswerMode.EXACT
    result = ResolvedAnswers()

    def visit(raw: Mapping[str, Any], ancestor_value: Any, ancestor_ref: str | None,
              parent_path: list[str]) -> None:
        native = str(raw["question"])
        raw_mode = raw.get("answer_mode")
        mode = AnswerMode.coerce(raw_mode) if raw_mode is not None else fallback
        if mode is None:
            result.problems.append(problem(
                ProblemCode.UNRESOLVED_ANSWER_MODE, GapScope.ANSWER,
                f"question {native}: answer_mode {raw_mode!r} is not a known mode; "
                f"no answer was resolved", native_ref=native))
            mode = AnswerMode.NONE
        result.modes[native] = mode.value

        own_value = raw.get("answer")
        own_conflicts = raw.get("answer_conflicts") or []
        has_own = own_value is not None or bool(own_conflicts)

        children = list(raw.get("parts", []) or [])
        for child in children:
            visit(child,
                  own_value if has_own else ancestor_value,
                  native if has_own else ancestor_ref,
                  parent_path + [native])

        answers: list[Answer] = []
        if has_own:
            answers = [_own_answer(raw, native, system=system,
                                   source_id=source_id, provider_id=provider_id,
                                   fixture_name=fixture_name)]
        elif mode is AnswerMode.ANCESTOR and ancestor_value is not None:
            answers = [_inherited_answer(native, ancestor_value, ancestor_ref, system=system,
                                         source_id=source_id, provider_id=provider_id,
                                         fixture_name=fixture_name)]
        elif mode is AnswerMode.DESCENDANTS:
            child_values = [(str(c["question"]), c.get("answer"))
                            for c in children if c.get("answer") is not None]
            if child_values:
                answers = [_derived_answer(native, child_values, system=system,
                                           source_id=source_id, provider_id=provider_id,
                                           fixture_name=fixture_name)]

        if answers:
            result.by_native_id[native] = answers
        elif mode is not AnswerMode.NONE:
            result.problems.append(problem(
                ProblemCode.MISSING_ANSWER, GapScope.QUESTION,
                f"question {native}: no answer is reachable in {mode.value!r} mode "
                f"(the slot is kept, the gap is reported, nothing is fabricated)",
                native_ref=native))

    for raw in questions:
        visit(raw, None, None, [])

    return result


# --------------------------------------------------------------------------- #
# answer construction
# --------------------------------------------------------------------------- #
def _identity(system: str, native: str, source: str, native_answer_key: str) -> str:
    return public_id(EntityKind.ANSWER, {
        "system": system, "question_native_id": native,
        "source": source, "native_answer_key": native_answer_key})


def _source(source_id: str, provider_id: str, fixture_name: str) -> SourceRef:
    return SourceRef(source_id=source_id, provider_id=provider_id,
                     locator={"fixture": fixture_name},
                     content_class=ContentClass.SYNTHETIC)


def _own_answer(raw: Mapping[str, Any], native: str, *, system: str,
                source_id: str, provider_id: str, fixture_name: str) -> Answer:
    conflicts = [Conflict.from_dict(c) for c in raw.get("answer_conflicts", [])]
    decision = (ManualDecision.from_dict(raw["manual_decision"])
                if raw.get("manual_decision") else None)
    alternatives = list(raw.get("alternative_answers", []))
    method = (AnswerMatchingMethod.GROUPED if alternatives
              else AnswerMatchingMethod.EXACT)
    return Answer(
        public_id=_identity(system, native, source_id, native),
        question_ref=native, original_value=raw.get("answer"), normalized_value=None,
        alternatives=alternatives, ordering_rule=None, matching_method=method,
        verification="unverified", source=_source(source_id, provider_id, fixture_name),
        conflicts=conflicts, manual_decision=decision,
        content_class=ContentClass.SYNTHETIC,
        lineage=Lineage(operation="adapter_exact_answer", parent_refs=[native],
                        note="answer stated on the question itself"),
    )


def _inherited_answer(native: str, value: Any, ancestor_ref: str | None, *, system: str,
                      source_id: str, provider_id: str, fixture_name: str) -> Answer:
    return Answer(
        public_id=_identity(system, native, source_id, native),
        question_ref=native, original_value=value, normalized_value=None,
        alternatives=[], ordering_rule=None, matching_method=AnswerMatchingMethod.ANCESTOR,
        verification="unverified", source=_source(source_id, provider_id, fixture_name),
        conflicts=[], manual_decision=None, content_class=ContentClass.SYNTHETIC,
        lineage=Lineage(operation="adapter_ancestor_answer",
                        parent_refs=[ancestor_ref] if ancestor_ref else [],
                        note="answer inherited from the nearest ancestor that states one"),
    )


def _derived_answer(native: str, child_values: list[tuple[str, Any]], *, system: str,
                    source_id: str, provider_id: str, fixture_name: str) -> Answer:
    values = [v for _child, v in child_values]
    return Answer(
        public_id=_identity(system, native, f"{source_id}:derived", native),
        question_ref=native, original_value=None, normalized_value=None,
        alternatives=values, ordering_rule="descendant_order",
        matching_method=AnswerMatchingMethod.DESCENDANTS, verification="unverified",
        source=_source(f"{source_id}:derived", provider_id, fixture_name),
        conflicts=[], manual_decision=None, content_class=ContentClass.SYNTHETIC,
        lineage=Lineage(operation="adapter_descendants_answer",
                        parent_refs=[child for child, _v in child_values],
                        note="answer derived from the question's parts, in order"),
    )


def conflicts_without_decision(answers: list[Answer]) -> list[Gap]:
    """Contract gaps for answers that carry more than one undecided candidate."""
    out = []
    for answer in answers:
        if len(answer.conflicts) > 1 and answer.manual_decision is None:
            out.append(Gap(code="answer_conflict", scope="answer",
                           detail="two candidate answers disagree and no manual decision "
                                  "is recorded; both are preserved"))
    return out


__all__ = ["AnswerMode", "ResolvedAnswers", "resolve_answers", "conflicts_without_decision"]
