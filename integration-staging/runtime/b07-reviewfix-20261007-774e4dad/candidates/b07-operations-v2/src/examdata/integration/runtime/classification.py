"""Stable internal classification of runner outcomes (plan 6.4 rule 7, A06).

Every way a controlled Node invocation can end maps to exactly one
:class:`RunnerOutcome`. The pass condition for A06 is that *every* failure has a
stable internal classification, so this module is deliberately a closed,
frozen enumeration with a fixed error-code table — never a free-form string.

Two outcomes are not infrastructure failures:

* ``OK``               — one valid JSON object on stdout, exit 0;
* ``BUSINESS_FAILURE`` — valid JSON with ``ok: false`` (the aggregator's own
  "the request was understood but the source had nothing" convention, which the
  original gateway returns as HTTP 200 and the caller inspects via ``ok``).

Everything else is an infrastructure failure: the caller cannot trust the
absence of data to mean "nothing found".
"""
from __future__ import annotations

from enum import Enum
from typing import Any


class _StrEnum(str, Enum):
    """Small local StrEnum base (kept private to this module, A06)."""

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return self.value

    @classmethod
    def coerce(cls, value):
        if isinstance(value, cls):
            return value
        try:
            return cls(value)
        except ValueError as exc:
            raise ValueError(
                f"{cls.__name__}: {value!r} is not an allowed value "
                f"({sorted(m.value for m in cls)})"
            ) from exc


class RunnerOutcome(_StrEnum):
    """The closed set of runner outcomes (plan 6.4 rule 7)."""

    OK = "ok"
    BUSINESS_FAILURE = "business_failure"

    COMPONENT_NOT_ALLOWED = "component_not_allowed"
    COMMAND_NOT_ALLOWED = "command_not_allowed"
    MISSING_COMPONENT = "missing_component"
    MISSING_RUNTIME = "missing_runtime"
    STARTUP_FAILURE = "startup_failure"
    QUEUE_FULL = "queue_full"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    OUTPUT_OVERFLOW = "output_overflow"
    NONZERO_EXIT = "nonzero_exit"
    INVALID_JSON = "invalid_json"
    MULTIPLE_JSON_VALUES = "multiple_json_values"


#: Deterministic classification when several conditions hold at once.
#: Earlier entries win, so a killed-overflow process is never reported as a
#: non-zero exit and a cancelled process is never reported as a timeout.
OUTCOME_PRECEDENCE: tuple[RunnerOutcome, ...] = (
    RunnerOutcome.COMPONENT_NOT_ALLOWED,
    RunnerOutcome.COMMAND_NOT_ALLOWED,
    RunnerOutcome.MISSING_COMPONENT,
    RunnerOutcome.MISSING_RUNTIME,
    RunnerOutcome.STARTUP_FAILURE,
    RunnerOutcome.QUEUE_FULL,
    RunnerOutcome.CANCELLED,
    RunnerOutcome.OUTPUT_OVERFLOW,
    RunnerOutcome.TIMEOUT,
    RunnerOutcome.NONZERO_EXIT,
    RunnerOutcome.INVALID_JSON,
    RunnerOutcome.MULTIPLE_JSON_VALUES,
    RunnerOutcome.BUSINESS_FAILURE,
    RunnerOutcome.OK,
)

#: Frozen outcome -> error-code table (stable public classification).
ERROR_CODES: dict[RunnerOutcome, str] = {
    RunnerOutcome.OK: "ok",
    RunnerOutcome.BUSINESS_FAILURE: "business_failure",
    RunnerOutcome.COMPONENT_NOT_ALLOWED: "component_not_allowed",
    RunnerOutcome.COMMAND_NOT_ALLOWED: "command_not_allowed",
    RunnerOutcome.MISSING_COMPONENT: "component_missing",
    RunnerOutcome.MISSING_RUNTIME: "runtime_missing",
    RunnerOutcome.STARTUP_FAILURE: "startup_failure",
    RunnerOutcome.QUEUE_FULL: "queue_full",
    RunnerOutcome.TIMEOUT: "timeout",
    RunnerOutcome.CANCELLED: "cancelled",
    RunnerOutcome.OUTPUT_OVERFLOW: "output_overflow",
    RunnerOutcome.NONZERO_EXIT: "nonzero_exit",
    RunnerOutcome.INVALID_JSON: "invalid_json",
    RunnerOutcome.MULTIPLE_JSON_VALUES: "multiple_json_values",
}

#: Outcomes worth retrying unchanged (transient pressure, not a bad request).
RETRYABLE_OUTCOMES: frozenset[RunnerOutcome] = frozenset(
    {RunnerOutcome.QUEUE_FULL, RunnerOutcome.TIMEOUT}
)

#: Outcomes that mean "the runner could not trust the result".
INFRASTRUCTURE_OUTCOMES: frozenset[RunnerOutcome] = frozenset(
    o for o in RunnerOutcome if o not in (RunnerOutcome.OK, RunnerOutcome.BUSINESS_FAILURE)
)


def is_infrastructure_failure(outcome: RunnerOutcome) -> bool:
    return outcome in INFRASTRUCTURE_OUTCOMES


def is_business_failure(outcome: RunnerOutcome) -> bool:
    return outcome is RunnerOutcome.BUSINESS_FAILURE


def error_code(outcome: RunnerOutcome) -> str:
    return ERROR_CODES[RunnerOutcome.coerce(outcome)]


def error_object(outcome: RunnerOutcome, message: str | None) -> dict[str, Any] | None:
    """The public error object for a non-``OK`` outcome (``None`` for ``OK``)."""
    outcome = RunnerOutcome.coerce(outcome)
    if outcome is RunnerOutcome.OK:
        return None
    return {
        "code": ERROR_CODES[outcome],
        "message": message,
        "retryable": outcome in RETRYABLE_OUTCOMES,
    }


__all__ = [
    "RunnerOutcome",
    "OUTCOME_PRECEDENCE",
    "ERROR_CODES",
    "RETRYABLE_OUTCOMES",
    "INFRASTRUCTURE_OUTCOMES",
    "is_infrastructure_failure",
    "is_business_failure",
    "error_code",
    "error_object",
]
