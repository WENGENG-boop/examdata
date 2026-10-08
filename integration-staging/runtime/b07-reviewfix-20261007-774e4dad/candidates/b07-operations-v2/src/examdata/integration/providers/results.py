"""Typed provider results and multi-provider aggregation (plan 5.2, A05).

The central rule: a *success* is the only status that may carry data, and an
empty success is only produced when the provider genuinely found nothing. Every
other status (unsupported, unavailable, filter_rejected, not_found, failed) is a
non-success and can never be mistaken for "zero results".

`DispatchResult` aggregates provider-level results with the plan's rule for
multi-provider requests: at least one success -> data with warnings (partial);
all requested providers fail -> an error, never an empty 200.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from ..contracts.base import Gap
from .capabilities import _StrEnum


class OutcomeStatus(_StrEnum):
    OK = "ok"
    UNSUPPORTED = "unsupported"
    UNAVAILABLE = "unavailable"
    FILTER_REJECTED = "filter_rejected"
    NOT_FOUND = "not_found"
    FAILED = "failed"


#: Deterministic precedence when every provider in a dispatch fails (plan 5.2):
#: the first status in this tuple that occurs becomes the aggregate error code.
ERROR_PRECEDENCE: tuple[OutcomeStatus, ...] = (
    OutcomeStatus.UNSUPPORTED,
    OutcomeStatus.FILTER_REJECTED,
    OutcomeStatus.UNAVAILABLE,
    OutcomeStatus.NOT_FOUND,
    OutcomeStatus.FAILED,
)

_DEFAULT_ERROR_CODE: dict[OutcomeStatus, str] = {
    OutcomeStatus.UNSUPPORTED: "unsupported_capability",
    OutcomeStatus.UNAVAILABLE: "provider_unavailable",
    OutcomeStatus.FILTER_REJECTED: "unsupported_filter",
    OutcomeStatus.NOT_FOUND: "not_found",
    OutcomeStatus.FAILED: "provider_failed",
}


_PATH_RE = re.compile(r"(?:[A-Za-z]:[\\/]|/)[^\s'\"]+")


def _sanitize(text: str, limit: int = 240) -> str:
    """Keep a short, path-free detail string for public error surfaces.

    Phase A providers never emit absolute paths, but a wrapped exception could,
    so any drive-rooted or POSIX path is replaced with `<path>` before the
    string is bounded and whitespace-collapsed. The v2 layer (A10) sanitizes
    again, so a local path or a raw traceback can never reach a response.
    """
    collapsed = " ".join(str(text).split())
    return _PATH_RE.sub("<path>", collapsed)[:limit]


@dataclass
class ProviderResult:
    """One provider's answer to one capability request."""

    provider_id: str
    capability: str
    status: OutcomeStatus
    items: list[Any] = field(default_factory=list)
    gaps: list[Gap] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    detail: str | None = None
    error_code: str | None = None
    retryable: bool = False
    filter_key: str | None = None

    @property
    def ok(self) -> bool:
        """True only for a genuine success (which may still be an empty list)."""
        return self.status is OutcomeStatus.OK

    @property
    def count(self) -> int:
        return len(self.items)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "capability": self.capability,
            "status": self.status.value,
            "count": len(self.items),
            "ok": self.ok,
            "error_code": self.error_code,
            "retryable": self.retryable,
            "filter_key": self.filter_key,
            "detail": self.detail,
            "gaps": [g.to_dict() for g in self.gaps],
            "warnings": list(self.warnings),
        }

    # -- constructors -------------------------------------------------------- #
    @classmethod
    def success(cls, provider_id: str, capability: str, *, items: Iterable[Any] = (),
                gaps: Iterable[Gap] = (), warnings: Iterable[str] = ()) -> "ProviderResult":
        return cls(provider_id=provider_id, capability=capability,
                   status=OutcomeStatus.OK, items=list(items),
                   gaps=list(gaps), warnings=list(warnings))

    @classmethod
    def unsupported(cls, provider_id: str, capability: str, *, detail: str | None = None) -> "ProviderResult":
        return cls(provider_id=provider_id, capability=capability,
                   status=OutcomeStatus.UNSUPPORTED,
                   error_code=_DEFAULT_ERROR_CODE[OutcomeStatus.UNSUPPORTED],
                   detail=_sanitize(detail) if detail else None)

    @classmethod
    def unavailable(cls, provider_id: str, capability: str, *, detail: str | None = None) -> "ProviderResult":
        return cls(provider_id=provider_id, capability=capability,
                   status=OutcomeStatus.UNAVAILABLE,
                   error_code=_DEFAULT_ERROR_CODE[OutcomeStatus.UNAVAILABLE],
                   detail=_sanitize(detail) if detail else None, retryable=True)

    @classmethod
    def filter_rejected(cls, provider_id: str, capability: str, *, filter_key: str,
                        detail: str | None = None) -> "ProviderResult":
        return cls(provider_id=provider_id, capability=capability,
                   status=OutcomeStatus.FILTER_REJECTED, filter_key=filter_key,
                   error_code=_DEFAULT_ERROR_CODE[OutcomeStatus.FILTER_REJECTED],
                   detail=_sanitize(detail) if detail else None)

    @classmethod
    def not_found(cls, provider_id: str, capability: str, *, detail: str | None = None) -> "ProviderResult":
        return cls(provider_id=provider_id, capability=capability,
                   status=OutcomeStatus.NOT_FOUND,
                   error_code=_DEFAULT_ERROR_CODE[OutcomeStatus.NOT_FOUND],
                   detail=_sanitize(detail) if detail else None)

    @classmethod
    def failed(cls, provider_id: str, capability: str, *, detail: str | None = None,
               error_code: str | None = None, retryable: bool = False) -> "ProviderResult":
        return cls(provider_id=provider_id, capability=capability,
                   status=OutcomeStatus.FAILED,
                   error_code=error_code or _DEFAULT_ERROR_CODE[OutcomeStatus.FAILED],
                   detail=_sanitize(detail) if detail else None, retryable=retryable)


@dataclass
class DispatchResult:
    """The aggregate of one capability request across several providers."""

    capability: str
    results: list[ProviderResult] = field(default_factory=list)

    @property
    def successes(self) -> list[ProviderResult]:
        return [r for r in self.results if r.ok]

    @property
    def failures(self) -> list[ProviderResult]:
        return [r for r in self.results if not r.ok]

    @property
    def items(self) -> list[Any]:
        return [item for r in self.successes for item in r.items]

    @property
    def gaps(self) -> list[Gap]:
        return [g for r in self.successes for g in r.gaps]

    @property
    def warnings(self) -> list[str]:
        out: list[str] = []
        for r in self.results:
            out.extend(r.warnings)
            if not r.ok and r.status is not OutcomeStatus.UNSUPPORTED:
                out.append(f"{r.provider_id}: {r.status.value}"
                           + (f" ({r.filter_key})" if r.filter_key else ""))
        return out

    @property
    def status(self) -> str:
        """`ok`, `partial` or `error` (plan 5.2)."""
        if not self.results:
            return "error"
        if self.successes:
            return "ok" if not self.failures else "partial"
        return "error"

    @property
    def error(self) -> dict[str, Any] | None:
        """A deterministic error object when every requested provider failed."""
        if self.status != "error":
            return None
        if not self.results:
            return {
                "code": "no_provider_requested",
                "message": f"no provider was requested for capability {self.capability!r}",
                "retryable": False,
                "details": {"providers": []},
            }
        ranked = sorted(
            self.failures,
            key=lambda r: (ERROR_PRECEDENCE.index(r.status)
                           if r.status in ERROR_PRECEDENCE else len(ERROR_PRECEDENCE)),
        )
        lead = ranked[0]
        return {
            "code": lead.error_code or "provider_failed",
            "message": lead.detail or f"capability {self.capability!r} failed",
            "retryable": any(r.retryable for r in self.failures),
            "details": {"providers": [r.to_dict() for r in self.results]},
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "status": self.status,
            "count": len(self.items),
            "warnings": self.warnings,
            "error": self.error,
            "providers": [r.to_dict() for r in self.results],
        }


__all__ = ["OutcomeStatus", "ERROR_PRECEDENCE", "ProviderResult", "DispatchResult"]
