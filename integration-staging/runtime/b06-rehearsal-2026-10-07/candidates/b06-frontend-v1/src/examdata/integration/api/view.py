"""Read-only views over the catalog snapshot and the provider registry (plan A10).

`CatalogView` turns a snapshot into the lookups the routes need: by public id or
alias, filtered listings, container/question grouping. `ProviderView` wraps a
registry dispatch and maps the frozen multi-provider outcome onto the plan's
HTTP statuses (plan 5.2): at least one success -> partial data with warnings;
every provider failed -> an error, never an empty 200.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from ..catalog.model import CatalogEntry
from ..contracts.canonical import normalize_alias, normalize_text
from ..providers.capabilities import Capability
from ..providers.results import DispatchResult
from .dataset import Dataset
from .envelope import ApiError

#: Dispatch error code -> the plan's HTTP status (plan 5.2).
_DISPATCH_STATUS: dict[str, int] = {
    "unsupported_capability": 422,
    "unsupported_filter": 422,
    "provider_unavailable": 503,
    "not_found": 404,
    "provider_failed": 502,
    "unknown_provider": 500,
    "no_provider_requested": 500,
}


def _flatten(value: Any) -> str:
    if isinstance(value, Mapping):
        return " ".join(_flatten(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return " ".join(_flatten(v) for v in value)
    return "" if value is None else str(value)


def _matches_mapping(row: Mapping[str, Any], key: str, wanted: Any) -> bool:
    """Match a plain dict fixture row (deferred families) against one filter."""
    if key == "query":
        return normalize_text(wanted).casefold() in _flatten(row).casefold()
    if key not in row:
        return False
    candidate = row[key]
    if isinstance(candidate, (list, tuple, set, frozenset)):
        return str(wanted) in {str(c) for c in candidate}
    return str(candidate) == str(wanted)


@dataclass
class CatalogView:
    """Deterministic lookups over one immutable catalog snapshot."""

    dataset: Dataset

    @property
    def revision(self) -> str:
        return self.dataset.revision

    @property
    def available_revisions(self) -> tuple[str, ...]:
        return self.dataset.available_revisions

    def entries(self, kind: str | None = None) -> list[CatalogEntry]:
        return self.dataset.entries(kind)

    def _aliases(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for entry in self.dataset.snapshot.entries:
            for alias in entry.aliases:
                out.setdefault(normalize_alias(alias), entry.public_id)
        return out

    def find(self, reference: str, kind: str | None = None) -> CatalogEntry | None:
        """Resolve a public id or an alias; return ``None`` when unknown."""
        entries = self.dataset.by_id()
        entry = entries.get(reference)
        if entry is None:
            resolved = self._aliases().get(normalize_alias(reference))
            entry = entries.get(resolved) if resolved else None
        if entry is None or (kind is not None and entry.kind != kind):
            return None
        return entry

    def require(self, reference: str, kind: str | None = None) -> CatalogEntry:
        entry = self.find(reference, kind)
        if entry is None:
            what = f"{kind} {reference!r}" if kind else f"identity {reference!r}"
            raise ApiError(404, "not_found", f"no catalog entry matches {what}")
        return entry

    def filter(self, entries: Iterable[Any], filters: Mapping[str, Any],
               *, allowed: frozenset[str],
               query_matcher: Any = None) -> list[Any]:
        """Apply only allowlisted filters; anything else is a 422, never ignored.

        Entries are catalog entries for the catalog routes and plain dict rows
        for the deferred fixture routes; `_matches` handles both shapes. A
        caller may replace the ``query`` key's semantics with ``query_matcher``
        (entry, value) -> bool; every other key keeps ``_matches`` unchanged.
        """
        wanted = {k: v for k, v in filters.items() if v not in (None, "")}
        unknown = sorted(k for k in wanted if k not in allowed)
        if unknown:
            raise ApiError(422, "unsupported_filter",
                           f"filter(s) {unknown} are not supported here",
                           details={"unsupported": unknown, "allowed": sorted(allowed)})

        def keep(entry: Any) -> bool:
            for key, value in wanted.items():
                if key == "query" and query_matcher is not None:
                    if not query_matcher(entry, value):
                        return False
                elif not self._matches(entry, key, value):
                    return False
            return True

        return [e for e in entries if keep(e)]

    @staticmethod
    def _matches(entry: Any, key: str, wanted: Any) -> bool:
        if isinstance(entry, Mapping):
            return _matches_mapping(entry, key, wanted)
        if key in ("system", "kind"):
            return str(getattr(entry, key)) == str(wanted)
        if key == "query":
            needle = normalize_text(wanted).casefold()
            haystack = " ".join([_flatten(entry.searchable),
                                 _flatten(entry.identity_fields),
                                 " ".join(entry.aliases)]).casefold()
            return needle in haystack
        for source in (entry.searchable, entry.identity_fields, entry.native_locator):
            if key in source:
                candidate = source[key]
                if isinstance(candidate, (list, tuple, set, frozenset)):
                    return str(wanted) in {str(c) for c in candidate}
                return str(candidate) == str(wanted)
        return False

    def native_id(self, entry: CatalogEntry) -> str | None:
        value = entry.native_locator.get("native_id", entry.identity_fields.get("native_id"))
        return None if value is None else str(value)

    def questions_for_container(self, container_id: str) -> list[CatalogEntry]:
        container = self.dataset.by_id().get(container_id)
        refs = list(container.searchable.get("question_refs", [])) if container else []
        by_id = self.dataset.by_id()
        return [by_id[ref] for ref in refs if ref in by_id]


@dataclass
class ProviderView:
    """One registry dispatch, mapped onto the v2 envelope's data and meta."""

    dataset: Dataset

    def dispatch(self, capability: Capability, *, system: str | None = None,
                 filters: Mapping[str, Any] | None = None,
                 target: str | None = None,
                 require_system: bool = True) -> dict[str, Any]:
        provider_ids: list[str] | None = None
        if system is not None:
            provider = self.dataset.provider_for_system(system)
            if provider is None:
                raise ApiError(503, "provider_unavailable",
                               f"no provider is registered for system {system!r}",
                               retryable=False)
            provider_ids = [provider.descriptor.provider_id]
        elif require_system:
            raise ApiError(500, "system_required",
                           "an internal caller requested a dispatch without a system")

        result = self.dataset.registry.dispatch(
            capability, provider_ids=provider_ids, filters=filters, target=target)
        return self._translate(result, capability)

    @staticmethod
    def _translate(result: DispatchResult, capability: Capability) -> dict[str, Any]:
        providers = [r.to_dict() for r in result.results]
        if result.status == "error":
            error = result.error or {}
            status = _DISPATCH_STATUS.get(error.get("code") or "", 502)
            raise ApiError(status, error.get("code") or "provider_failed",
                           error.get("message") or "the provider request failed",
                           retryable=bool(error.get("retryable")),
                           details={"providers": error.get("details", {}).get("providers", providers)})
        return {
            "items": list(result.items),
            "gaps": list(result.gaps),
            "warnings": list(result.warnings),
            "providers": providers,
            "completeness": "complete" if result.status == "ok" else "partial",
            "capability": capability.value,
        }


#: season label -> the fixture's own English season name (discovery query tokens)
_SEASON_ENGLISH: dict[str, str] = {
    "jan": "January",
    "january": "January",
    "jun": "June",
    "june": "June",
    "mar": "March",
    "march": "March",
    "nov": "November",
    "november": "November",
    "oct": "October",
    "october": "October",
}


def _has_token(haystack: str, token: str) -> bool:
    """True when ``token`` occurs in ``haystack`` on a token boundary.

    The boundary rule keeps ``mar`` from matching ``mark_scheme`` and lets a
    token like ``01`` match the paper inside ``wma11-01`` without matching a
    fragment of ``2024``.
    """
    pattern = rf"(?<![0-9a-z]){re.escape(token)}(?![0-9a-z])"
    return re.search(pattern, haystack) is not None


def resource_query_matches(entry: CatalogEntry, wanted: Any) -> bool:
    """The frontend discovery query semantics for one catalog entry.

    The legacy frontend searches resources with one space-separated token list
    (subject, year, optional paper, season) and keeps a document only when
    every token belongs to the document's own fields. This matcher keeps that
    behaviour for the resources route: tokens are ANDed, and each may hit the
    subject, year, paper, season (short label or English name) or the
    container's recorded session terms.
    """
    tokens = normalize_text(wanted).casefold().split()
    if not tokens:
        return True
    discovery = entry.searchable.get("discovery") or {}
    parts: list[Any] = [entry.system, entry.identity_fields.get("media_type")]
    parts.extend(value for value in discovery.values() if value not in (None, ""))
    season = discovery.get("season")
    if season:
        parts.append(_SEASON_ENGLISH.get(str(season).casefold(), season))
    terms = entry.searchable.get("discovery_terms")
    if terms:
        parts.append(list(terms))
    haystack = _flatten(parts).casefold()
    return all(_has_token(haystack, token) for token in tokens)


__all__ = ["CatalogView", "ProviderView", "resource_query_matches"]
