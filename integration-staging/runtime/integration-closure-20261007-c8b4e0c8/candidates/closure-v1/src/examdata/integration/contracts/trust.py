"""The validated entry boundary: resolved identity and traceable quality claims.

Schema: ``trust/1``. Decision record:
``docs/integration/execution/COVERAGE_CONTRACT_DECISION.md`` (the
``coverage-contract/2.1`` note).

This module is the single source of truth for the two questions every entry
path - the catalog model, the store, the builder, snapshot deserialisation and
the published-coverage derivation - must answer identically:

* **is this entry's identity resolved?** The identity mapping must carry every
  required key for its kind (``canonical.IDENTITY_KEYS``) with a value that is
  not absent (``None``), not empty (``""``, ``[]``, ``{}``), not the ``UNKNOWN``
  sentinel and not the persisted unknown token. Keys in
  :data:`NOT_APPLICABLE_IDENTITY_FIELDS` are the one exception: there the
  ``UNKNOWN`` sentinel records a *known absence* (a top-level question has no
  parent), which is a resolved value, not an unknown state.
* **are this entry's quality claims backed by traceable evidence?** A claim of
  ``source_verified`` needs at least one label in
  ``quality.AUTHORITATIVE_EVIDENCE``; a claim of ``manual_adjudicated`` needs the
  preserved manual decision (``lineage["manual_decision"]`` with a non-empty
  ``selected_value``); a claim of ``complete`` content needs at least one
  evidence label at all; and two claims that contradict each other (a missing
  answer that is simultaneously verified) are a problem. A kind that carries no
  answer axes must not claim one. An entry with no quality information at all is
  *not* a problem - that is the ``unknown`` bucket, not a violation.

A problem is a *downgrade*, never a promotion: an entry with any quality problem
is at most ``partial``, and an entry whose identity is unresolved is never
counted as identified. Nothing here reads the original project, the network or a
database; it is pure data handling over the fields the catalog already carries.
"""
from __future__ import annotations

from typing import Any, Mapping

from .base import UNKNOWN, UnknownType
from .canonical import IDENTITY_KEYS
from .enums import EntityKind, EvidenceLabel
from .quality import AUTHORITATIVE_EVIDENCE

TRUST_SCHEMA = "trust/1"

#: The persisted encoding of the ``UNKNOWN`` sentinel (``catalog.model``
#: ``UNKNOWN_TOKEN``). A mapping that still carries the raw token was never
#: decoded back to the sentinel and must not be read as a resolved identity.
PERSISTED_UNKNOWN_TOKEN = "__unknown__"

#: Identity fields where the catalog's ``UNKNOWN`` sentinel records a *known
#: absence* ("this question has no parent"), not an unknown state; such a field
#: must never push an otherwise identified entry into the unknown bucket. Moved
#: here from ``operations.published`` and re-exported there so existing
#: importers keep working.
NOT_APPLICABLE_IDENTITY_FIELDS = frozenset({"parent_native_id"})

#: The kinds whose records carry answer axes. Every other kind must not be
#: required to carry answer information, and a *claim* on those axes is not
#: applicable rather than a legitimate value.
ANSWER_BEARING_KINDS = frozenset({"question", "answer"})

#: The ``answer_verification`` values that count as actually verified; every
#: other value - including ``unverified``, ``conflicting`` and ``unknown`` - is
#: not verification.
ANSWER_VERIFIED_VALUES = frozenset({"source_verified", "manual_adjudicated"})

#: The quality-summary fields this module understands. An entry whose summary
#: carries none of them has no quality information at all: ``unknown``.
_QUALITY_FIELDS = ("content", "answer_presence", "answer_verification")


# --------------------------------------------------------------------------- #
# field access (attribute or mapping, so plain dicts validate identically)
# --------------------------------------------------------------------------- #
def _entry_field(entry: Any, name: str) -> Any:
    if isinstance(entry, Mapping):
        return entry.get(name)
    return getattr(entry, name, None)


def _kind_value(kind: Any) -> str:
    value = getattr(kind, "value", kind)
    return value if isinstance(value, str) else str(value)


def _quality_summary(entry: Any) -> Mapping[str, Any]:
    summary = _entry_field(entry, "quality_summary")
    return summary if isinstance(summary, Mapping) else {}


def _evidence_labels(entry: Any) -> list[Any]:
    labels = _entry_field(entry, "evidence_labels")
    return list(labels) if isinstance(labels, (list, tuple)) else []


def _dedupe(codes: list[str]) -> list[str]:
    return list(dict.fromkeys(codes))


# --------------------------------------------------------------------------- #
# identity
# --------------------------------------------------------------------------- #
def _is_unknown(value: Any) -> bool:
    return isinstance(value, UnknownType)


def _contains_persisted_token(value: Any) -> bool:
    if isinstance(value, str):
        return value == PERSISTED_UNKNOWN_TOKEN
    if isinstance(value, Mapping):
        return any(_contains_persisted_token(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_persisted_token(v) for v in value)
    return False


def _contains_unknown_sentinel(value: Any) -> bool:
    if _is_unknown(value):
        return True
    if isinstance(value, Mapping):
        return any(_contains_unknown_sentinel(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_unknown_sentinel(v) for v in value)
    return False


def _identity_value_problem(key: str, value: Any) -> str | None:
    """The problem code for one identity value, or ``None`` when it is resolved."""
    if key in NOT_APPLICABLE_IDENTITY_FIELDS:
        # A known absence (no parent / not applicable) is a resolved value.
        return None
    if _contains_unknown_sentinel(value) and not _contains_persisted_token(value):
        return f"identity_unknown_value:{key}"
    if _contains_persisted_token(value):
        return f"identity_unknown_encoding:{key}"
    if value is None:
        return f"identity_none_value:{key}"
    if isinstance(value, (str, list, tuple, Mapping)) and len(value) == 0:
        return f"identity_empty_value:{key}"
    return None


def identity_problems(kind: Any, identity_fields: Any) -> list[str]:
    """Every reason ``identity_fields`` does not resolve for ``kind``.

    Deterministic order: the kind's required keys in their frozen order. A kind
    without an entry in ``canonical.IDENTITY_KEYS`` (including an unknown kind)
    falls back to the generic rule: a non-empty mapping whose values are all
    non-empty and not unknown, with the same not-applicable exception.
    """
    if not isinstance(identity_fields, Mapping):
        return ["identity_not_mapping"]
    if not identity_fields:
        return ["identity_empty"]
    try:
        keys = IDENTITY_KEYS.get(EntityKind.coerce(_kind_value(kind)))
    except ValueError:
        keys = None
    if keys is None:
        problems = []
        for key, value in identity_fields.items():
            problem = _identity_value_problem(str(key), value)
            if problem is not None:
                problems.append(problem)
        return problems
    problems = []
    for key in keys:
        if key not in identity_fields:
            problems.append(f"identity_missing_key:{key}")
            continue
        problem = _identity_value_problem(key, identity_fields[key])
        if problem is not None:
            problems.append(problem)
    return problems


def identity_resolved(entry: Any) -> bool:
    """True when the entry's identity mapping resolves under the rules above."""
    return not identity_problems(_entry_field(entry, "kind"),
                                 _entry_field(entry, "identity_fields"))


# --------------------------------------------------------------------------- #
# quality claims
# --------------------------------------------------------------------------- #
def _known_labels(entry: Any) -> list[EvidenceLabel]:
    labels = []
    for label in _evidence_labels(entry):
        try:
            labels.append(EvidenceLabel.coerce(label))
        except ValueError:
            continue
    return labels


def _has_authoritative_evidence(entry: Any) -> bool:
    return any(label in AUTHORITATIVE_EVIDENCE for label in _known_labels(entry))


def _has_manual_decision(entry: Any) -> bool:
    """True when ``lineage["manual_decision"]`` preserves a non-empty selection."""
    lineage = _entry_field(entry, "lineage")
    if not isinstance(lineage, Mapping):
        return False
    decision = lineage.get("manual_decision")
    if decision is None:
        return False
    if isinstance(decision, Mapping):
        selected = decision.get("selected_value")
    else:
        selected = getattr(decision, "selected_value", None)
    if selected is None:
        return False
    if isinstance(selected, str):
        return bool(selected.strip())
    if isinstance(selected, (list, tuple, Mapping)):
        return bool(selected)
    return True


def quality_claim_problems(entry: Any) -> list[str]:
    """Every quality claim on ``entry`` that its own evidence does not support.

    Order is fixed: label validity, then kind applicability, then the content
    claim, then the answer claims. Duplicates are removed and the order is
    stable, so two callers always see the same list.
    """
    problems: list[str] = []
    for label in _evidence_labels(entry):
        try:
            EvidenceLabel.coerce(label)
        except ValueError:
            problems.append(f"unknown_evidence_label:{label}")

    summary = _quality_summary(entry)
    content = summary.get("content")
    presence = summary.get("answer_presence")
    verification = summary.get("answer_verification")
    answer_bearing = _kind_value(_entry_field(entry, "kind")) in ANSWER_BEARING_KINDS

    if not answer_bearing and (verification in ANSWER_VERIFIED_VALUES
                               or presence in {"present", "missing"}):
        problems.append("answer_axis_not_applicable")

    if content == "complete" and not _evidence_labels(entry):
        problems.append("content_claim_without_evidence")

    if answer_bearing:
        if verification == "source_verified" and not _has_authoritative_evidence(entry):
            problems.append("verification_without_authoritative_evidence")
        if verification == "manual_adjudicated" and not _has_manual_decision(entry):
            problems.append("verification_without_manual_decision")
        if verification in ANSWER_VERIFIED_VALUES and (presence == "missing" or content == "missing"):
            problems.append("quality_claim_contradiction")
    return _dedupe(problems)


def quality_state(entry: Any) -> str:
    """``"verified" | "partial" | "unknown"`` for one entry's quality evidence.

    An entry whose claim is invalid is ``partial``, never ``verified``. An entry
    with no quality information at all is ``unknown``.
    """
    if quality_claim_problems(entry):
        return "partial"
    summary = _quality_summary(entry)
    if not any(field in summary for field in _QUALITY_FIELDS):
        return "unknown"
    if summary.get("content") != "complete":
        return "partial"
    if _kind_value(_entry_field(entry, "kind")) in ANSWER_BEARING_KINDS:
        return ("verified" if summary.get("answer_verification") in ANSWER_VERIFIED_VALUES
                else "partial")
    return "verified"


def quality_state_reasons(entry: Any) -> list[str]:
    """Why :func:`quality_state` has its value; empty for ``verified``.

    A ``partial`` entry with no problem code carries the missing preconditions
    (``content_not_complete`` / ``answers_not_verified``) as *state reasons*,
    not as problem codes.
    """
    problems = quality_claim_problems(entry)
    if problems:
        return problems
    state = quality_state(entry)
    if state == "verified":
        return []
    if state == "unknown":
        return ["no_quality_information"]
    summary = _quality_summary(entry)
    reasons = []
    if summary.get("content") != "complete":
        reasons.append("content_not_complete")
    if (_kind_value(_entry_field(entry, "kind")) in ANSWER_BEARING_KINDS
            and summary.get("answer_verification") not in ANSWER_VERIFIED_VALUES):
        reasons.append("answers_not_verified")
    return reasons


def entry_problems(entry: Any) -> list[str]:
    """Identity problems followed by quality-claim problems, in that order."""
    return (identity_problems(_entry_field(entry, "kind"),
                              _entry_field(entry, "identity_fields"))
            + quality_claim_problems(entry))


#: The problem code a store/snapshot records for an entry whose identity is
#: unresolved (the ID is derivable, so the entry is kept and visibly flagged).
IDENTITY_PROBLEM_CODE = "identity_unresolved"

#: The problem code recorded for an entry whose quality claim its own evidence
#: does not support (fatal on a build: an unsupported claim is never published).
QUALITY_PROBLEM_CODE = "quality_claim_invalid"


def entry_problem_records(entry: Any) -> list[dict[str, Any]]:
    """The store/snapshot problem records for one entry, in a stable shape.

    The store, the builder and snapshot deserialisation all emit these exact
    records, so merging them is idempotent and a consumer sees one vocabulary.
    """
    records: list[dict[str, Any]] = []
    ref = _entry_field(entry, "public_id")
    for code, problems in ((IDENTITY_PROBLEM_CODE,
                            identity_problems(_entry_field(entry, "kind"),
                                              _entry_field(entry, "identity_fields"))),
                           (QUALITY_PROBLEM_CODE, quality_claim_problems(entry))):
        if not problems:
            continue
        record: dict[str, Any] = {"code": code, "scope": "catalog",
                                  "detail": "; ".join(problems)}
        if ref:
            record["ref"] = str(ref)
        records.append(record)
    return records


def problem_key(record: Mapping[str, Any]) -> tuple[str, str, str, str]:
    """The dedupe key of a problem record (code, scope, detail, ref)."""
    return (str(record.get("code", "")), str(record.get("scope", "")),
            str(record.get("detail", "")), str(record.get("ref", "")))


__all__ = [
    "TRUST_SCHEMA",
    "PERSISTED_UNKNOWN_TOKEN",
    "NOT_APPLICABLE_IDENTITY_FIELDS",
    "ANSWER_BEARING_KINDS",
    "ANSWER_VERIFIED_VALUES",
    "IDENTITY_PROBLEM_CODE",
    "QUALITY_PROBLEM_CODE",
    "identity_problems",
    "identity_resolved",
    "quality_claim_problems",
    "quality_state",
    "quality_state_reasons",
    "entry_problems",
    "entry_problem_records",
    "problem_key",
]
