"""The v2 JSON envelope, the error map and public sanitisation (plan 5.1, 5.2).

Every v2 JSON response has the same shape:

    {"schema_version": "examdata.v2/1", "request_id": ..., "data": ...,
     "meta": {...}, "error": null}

and a failure has ``data = null`` and a populated ``error`` object. The error
map below is the plan's table verbatim; :class:`ApiError` is the only way a
handler raises a non-200 status, so a status can never be chosen ad hoc. The
map is extended only through the two explicit carve-outs documented below
(FRAMEWORK_STATUSES and BINARY_STATUSES).

Nothing public may carry a local absolute path, a credential, raw stderr or a
stack trace: :func:`clean` and :func:`sanitize_text` are applied to every
outgoing value, and the error handlers sanitize again as a backstop.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from ..catalog.model import encode_unknown
from ..contracts.base import ContractModel

SCHEMA_VERSION = "examdata.v2/1"

#: The plan's HTTP -> meaning map (plan 5.2). Kept here so a test can assert the
#: staged layer uses exactly these statuses and no others.
ERROR_MAP: dict[int, str] = {
    200: "successful result, including explicitly partial or genuinely empty lists",
    400: "malformed request syntax where framework-level parsing cannot apply",
    401: "authentication required",
    403: "access policy forbids the resource",
    404: "known requested identity or resource is absent",
    409: "identity, revision or hash conflict (including a stale cursor revision)",
    410: "a previously recorded asset is no longer available",
    413: "resource or response budget exceeded",
    422: "invalid or unsupported parameter combination",
    429: "rate limit",
    500: "unexpected internal error, public message sanitized",
    502: "invalid or failing upstream response",
    503: "required component unavailable or queue full",
    504: "operation timed out",
}

#: Only these statuses may be produced by a staged v2 handler in Phase A; 413
#: and 416 are the binary transport's budget and range failures (plan 5.3).
#: 401, 403, 410, 429 and 504 need capabilities (auth, asset retention, rate
#: limits, upstream calls) that are not staged yet, so they are documented but
#: never emitted here.
EMITTABLE_STATUSES: frozenset[int] = frozenset(
    {200, 400, 404, 409, 413, 416, 422, 500, 502, 503})

#: Statuses the framework's own routing may answer for a v2 path that the plan
#: 5.2 map does not name. A wrong HTTP method is rejected by Starlette's router
#: (405) before any v2 handler runs, so it is documented here as framework-level
#: and surfaced through the same error envelope rather than the plan's map.
FRAMEWORK_STATUSES: frozenset[int] = frozenset({405})

#: Statuses the binary transport (plan 5.3) may answer that the plan's 5.2 map
#: does not name, the same carve-out idea as FRAMEWORK_STATUSES above: 206 is a
#: successful partial response and 304 a conditional-request hit (RFC 9110,
#: both with their own success semantics), while 416 reports an unsatisfiable
#: range through the same error envelope as every other failure.
BINARY_STATUSES: frozenset[int] = frozenset({206, 304, 416})

_PATH_RE = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\[^\s]+|/)[^\s'\"]*")
_TOKEN_RE = re.compile(
    r"(?i)\b(api[_-]?key|token|secret|password|bearer)\b\s*[:=]?\s*\S+")
_STACK_RE = re.compile(r"(?m)^\s*(Traceback \(most recent call last\)|File \".*\", line \d+)")
_FRAME_RE = re.compile(r'File "[^"]*", line \d+')


def sanitize_text(value: Any, *, limit: int = 300) -> str:
    """Collapse whitespace, strip paths/credentials/stack frames, bound length."""
    text = str(value)
    text = _STACK_RE.sub("[stack]", text)
    text = _FRAME_RE.sub("[stack]", text)
    text = " ".join(text.split())
    text = _TOKEN_RE.sub(r"\1=<redacted>", text)
    text = _PATH_RE.sub("<path>", text)
    return text[:limit]


def sanitize_details(value: Any, *, depth: int = 0) -> Any:
    """Recursively sanitize a details payload, keeping the public shape."""
    if depth > 6:
        return "<depth-limit>"
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, Mapping):
        return {str(k): sanitize_details(v, depth=depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize_details(v, depth=depth + 1) for v in value]
    if isinstance(value, Enum):
        return value.value
    return value


def clean(value: Any) -> Any:
    """Turn staged models into plain JSON-safe values.

    * the ``UNKNOWN`` sentinel becomes its reserved token (never ``null``),
    * enums become their string values,
    * contract models become their dict form with the internal ``schema`` key
      removed at every level, so a public payload never carries an internal
      schema tag.
    """
    value = encode_unknown(value)
    if isinstance(value, ContractModel):
        return clean(value.to_dict())
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(k): clean(v) for k, v in value.items() if str(k) != "schema"}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    return value


@dataclass
class ApiError(Exception):
    """A typed, sanitized non-200 outcome; the only non-200 raise path."""

    status: int = 500
    code: str = "internal_error"
    message: str = "unexpected internal error"
    retryable: bool = False
    details: Any = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if (self.status not in ERROR_MAP
                and self.status not in FRAMEWORK_STATUSES
                and self.status not in BINARY_STATUSES):
            raise ValueError(f"{self.status!r} is not one of the plan's statuses")
        Exception.__init__(self, self.message)
        self.message = sanitize_text(self.message)
        self.details = sanitize_details(self.details)

    def to_error(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "retryable": bool(self.retryable),
            "details": self.details if self.details is not None else {},
        }


def ok_envelope(*, request_id: str, data: Any, dataset_revision: str | None,
                retrieved_at: str, limit: int | None = None,
                next_cursor: str | None = None, completeness: str = "complete",
                warnings: Any = (), providers: Any = ()) -> dict[str, Any]:
    """Build a successful v2 envelope (plan 5.1)."""
    return {
        "schema_version": SCHEMA_VERSION,
        "request_id": request_id,
        "data": clean(data),
        "meta": {
            "dataset_revision": dataset_revision,
            "retrieved_at": retrieved_at,
            "pagination": {"limit": limit, "next_cursor": next_cursor},
            "completeness": completeness,
            "warnings": [sanitize_text(w) for w in warnings],
            "providers": list(providers),
        },
        "error": None,
    }


def error_envelope(*, request_id: str, error: ApiError,
                   dataset_revision: str | None = None,
                   retrieved_at: str | None = None) -> dict[str, Any]:
    """Build a failing v2 envelope: ``data`` is null and ``error`` is populated."""
    return {
        "schema_version": SCHEMA_VERSION,
        "request_id": request_id,
        "data": None,
        "meta": {
            "dataset_revision": dataset_revision,
            "retrieved_at": retrieved_at,
            "pagination": {"limit": None, "next_cursor": None},
            "completeness": "unknown",
            "warnings": [],
            "providers": [],
        },
        "error": error.to_error(),
    }


__all__ = [
    "SCHEMA_VERSION",
    "ERROR_MAP",
    "EMITTABLE_STATUSES",
    "FRAMEWORK_STATUSES",
    "BINARY_STATUSES",
    "ApiError",
    "sanitize_text",
    "sanitize_details",
    "clean",
    "ok_envelope",
    "error_envelope",
]
