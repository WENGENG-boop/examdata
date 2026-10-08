"""Adapter-layer diagnostics (plan A07).

An adapter never raises on a data problem and never silently drops one: every
irregularity becomes an :class:`AdapterProblem` with a stable code, so a caller
can both keep working and show exactly what was wrong. Codes that correspond to
a frozen contract gap (plan 4.3) also expose :meth:`AdapterProblem.to_gap`.

These codes are adapter-local and deliberately *not* added to the frozen
``GapCode`` vocabulary: a missing index file or a document hash conflict is a
property of the read step, not of the stored content.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from ..contracts.base import Gap
from ..contracts.enums import GapCode, GapScope


class ProblemCode(str, Enum):
    MISSING_INDEX = "missing_index"
    UNREADABLE_INDEX = "unreadable_index"
    INVALID_JSON = "invalid_json"
    WRONG_FIXTURE_KIND = "wrong_fixture_kind"
    UNSUPPORTED_SCHEMA_VERSION = "unsupported_schema_version"
    MISSING_DOCUMENT_ROLE = "missing_document_role"
    MISSING_MS = "missing_ms"
    HASH_CONFLICT = "hash_conflict"
    UNKNOWN_ROTATION = "unknown_rotation"
    MISSING_REGION_BBOX = "missing_region_bbox"
    UNRESOLVED_ANSWER_MODE = "unresolved_answer_mode"
    MISSING_ANSWER = "missing_answer"
    UNKNOWN_DATE = "unknown_date"

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return self.value


# Which adapter problems are also a frozen contract gap, and under which code.
# A problem with no entry here is purely a read-step diagnostic.
_GAP_FOR: dict[ProblemCode, GapCode] = {
    ProblemCode.MISSING_INDEX: GapCode.DEFERRED_SOURCE,
    ProblemCode.UNREADABLE_INDEX: GapCode.DEFERRED_SOURCE,
    ProblemCode.INVALID_JSON: GapCode.DEFERRED_SOURCE,
    ProblemCode.MISSING_MS: GapCode.MISSING_DOCUMENT_HASH,
    ProblemCode.MISSING_DOCUMENT_ROLE: GapCode.MISSING_DOCUMENT_HASH,
    ProblemCode.HASH_CONFLICT: GapCode.UNVERIFIED_CONTENT,
    ProblemCode.UNKNOWN_ROTATION: GapCode.UNVERIFIED_CONTENT,
    ProblemCode.MISSING_REGION_BBOX: GapCode.MISSING_REGION,
    ProblemCode.MISSING_ANSWER: GapCode.MISSING_ANSWER,
    ProblemCode.UNKNOWN_DATE: GapCode.UNKNOWN_DATE,
}


@dataclass
class AdapterProblem:
    """One stable, visible read-step problem."""

    code: str
    scope: str
    detail: str
    native_ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "scope": self.scope,
                "detail": self.detail, "native_ref": self.native_ref}

    def to_gap(self) -> Gap | None:
        """Return the frozen contract gap for this problem, or ``None``."""
        try:
            gap_code = _GAP_FOR[ProblemCode(self.code)]
        except (KeyError, ValueError):
            return None
        return Gap(code=gap_code.value, scope=self.scope, detail=self.detail)


def problem(code: ProblemCode, scope: GapScope | str, detail: str,
            native_ref: str | None = None) -> AdapterProblem:
    scope_value = scope.value if isinstance(scope, GapScope) else str(scope)
    return AdapterProblem(code=code.value, scope=scope_value, detail=detail,
                          native_ref=native_ref)


__all__ = ["ProblemCode", "AdapterProblem", "problem"]
