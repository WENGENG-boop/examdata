"""Read a staged source document: a synthetic fixture or a copied snapshot (A08).

The A07 reader (:mod:`~.reader`) accepts only a document explicitly labelled
``fixture_kind == "synthetic"``. A08 also reads *copied snapshots*: byte-identical
copies of small, non-protected original metadata files recorded in the frozen A03
provenance manifest (the TOEFL reading index, the IELTS printed-page map, the
IELTS PDF-import provenance and the IELTS revision pointers). Those files carry no
``fixture_kind`` field, so this module decides the kind from the path
(``fixtures/copied/`` vs ``fixtures/synthetic/``) and validates it against the
kinds the caller allows.

Nothing here opens a file the caller did not name, walks a tree, resolves a path
outside the staging root, or fetches anything. A missing file, unreadable bytes,
malformed JSON, a path outside staging, an unexpected kind or an unsupported
schema version each become an explicit :class:`SourceProblem`, and the caller
receives ``(None, kind, problems)`` - never a half-parsed document.

Two source-shape helpers used by the TOEFL adapter also live here because they are
read-step rules, not board-specific mapping: strict KMF URL validation (a URL is
never followed, only checked) and cache-entry iteration that reports a malformed
entry instead of dropping it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit

from ..contracts.base import Gap
from ..contracts.enums import GapCode, GapScope
from .problems import AdapterProblem

STAGING = Path(__file__).resolve().parents[3]
COPIED_ROOT = STAGING / "fixtures" / "copied"
SYNTHETIC_ROOT = STAGING / "fixtures" / "synthetic"

SUPPORTED_SCHEMA_VERSIONS = frozenset({"1"})

# The only host a TOEFL link may point at; the adapter validates the shape and
# never requests it (plan 8.4: strict KMF URL validation, no online refetch).
KMF_HOST = "toefl.kmf.com"


class SourceKind(str, Enum):
    """Where a staged source came from, which fixes its evidence label."""

    SYNTHETIC = "synthetic"
    COPIED_SNAPSHOT = "copied_snapshot"
    UNKNOWN = "unknown"
    OUTSIDE_STAGING = "outside_staging"

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return self.value


class SourceProblemCode(str, Enum):
    """A08 read-step diagnostics. Adapter-local, with their own gap mapping."""

    MISSING_SOURCE = "missing_source"
    UNREADABLE_SOURCE = "unreadable_source"
    INVALID_JSON = "invalid_json"
    UNKNOWN_SOURCE_KIND = "unknown_source_kind"
    OUTSIDE_STAGING = "outside_staging"
    WRONG_SOURCE_KIND = "wrong_source_kind"
    UNSUPPORTED_SCHEMA_VERSION = "unsupported_schema_version"
    BAD_CACHE_ENTRY = "bad_cache_entry"
    INVALID_KMF_URL = "invalid_kmf_url"
    UNRESOLVED_IDENTITY = "unresolved_identity"
    RESTRICTED_SOURCE = "restricted_source"
    MISSING_OPTIONS = "missing_options"
    MISSING_TABLE = "missing_table"
    MISSING_ANSWER_SLOT = "missing_answer_slot"
    MISSING_ASSET = "missing_asset"
    MISSING_DOCUMENT_HASH = "missing_document_hash"
    UNKNOWN_DATE = "unknown_date"
    UNRESOLVED_PAGE = "unresolved_page"
    UNRESOLVED_EDITION = "unresolved_edition"
    ANSWER_CONFLICT = "answer_conflict"
    MISSING_TIME_WINDOW = "missing_time_window"
    UNVERIFIED_CONTENT = "unverified_content"

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return self.value


# Which A08 problem is also a frozen contract gap, and under which code.
_GAP_FOR: dict[str, str] = {
    SourceProblemCode.MISSING_SOURCE.value: GapCode.DEFERRED_SOURCE.value,
    SourceProblemCode.UNREADABLE_SOURCE.value: GapCode.DEFERRED_SOURCE.value,
    SourceProblemCode.INVALID_JSON.value: GapCode.DEFERRED_SOURCE.value,
    SourceProblemCode.UNKNOWN_SOURCE_KIND.value: GapCode.DEFERRED_SOURCE.value,
    SourceProblemCode.OUTSIDE_STAGING.value: GapCode.DEFERRED_SOURCE.value,
    SourceProblemCode.WRONG_SOURCE_KIND.value: GapCode.DEFERRED_SOURCE.value,
    SourceProblemCode.UNSUPPORTED_SCHEMA_VERSION.value: GapCode.DEFERRED_SOURCE.value,
    SourceProblemCode.BAD_CACHE_ENTRY.value: GapCode.UNVERIFIED_CONTENT.value,
    SourceProblemCode.INVALID_KMF_URL.value: GapCode.UNVERIFIED_CONTENT.value,
    SourceProblemCode.UNRESOLVED_IDENTITY.value: GapCode.UNRESOLVED_IDENTITY.value,
    SourceProblemCode.RESTRICTED_SOURCE.value: GapCode.DEFERRED_SOURCE.value,
    SourceProblemCode.MISSING_OPTIONS.value: GapCode.MISSING_OPTIONS.value,
    SourceProblemCode.MISSING_TABLE.value: GapCode.MISSING_TABLE.value,
    SourceProblemCode.MISSING_ANSWER_SLOT.value: GapCode.MISSING_ANSWER_SLOT.value,
    SourceProblemCode.MISSING_ASSET.value: GapCode.MISSING_REQUIRED_IMAGE.value,
    SourceProblemCode.MISSING_DOCUMENT_HASH.value: GapCode.MISSING_DOCUMENT_HASH.value,
    SourceProblemCode.UNKNOWN_DATE.value: GapCode.UNKNOWN_DATE.value,
    SourceProblemCode.UNRESOLVED_PAGE.value: GapCode.MISSING_REGION.value,
    SourceProblemCode.UNRESOLVED_EDITION.value: GapCode.UNRESOLVED_EDITION.value,
    SourceProblemCode.ANSWER_CONFLICT.value: GapCode.ANSWER_CONFLICT.value,
    SourceProblemCode.MISSING_TIME_WINDOW.value: GapCode.UNKNOWN_COVERAGE.value,
    SourceProblemCode.UNVERIFIED_CONTENT.value: GapCode.UNVERIFIED_CONTENT.value,
}


@dataclass
class SourceProblem(AdapterProblem):
    """An A08 read-step problem, an :class:`AdapterProblem` with its own gap map."""

    def to_gap(self) -> Gap | None:
        gap_code = _GAP_FOR.get(self.code)
        if gap_code is None:
            return None
        return Gap(code=gap_code, scope=self.scope, detail=self.detail)


def source_problem(code: SourceProblemCode, scope: GapScope | str, detail: str,
                   native_ref: str | None = None) -> SourceProblem:
    scope_value = scope.value if isinstance(scope, GapScope) else str(scope)
    return SourceProblem(code=code.value, scope=scope_value, detail=detail,
                         native_ref=native_ref)


def classify_path(path: str | Path) -> SourceKind:
    """Classify a staged source path without reading it."""
    try:
        rel = Path(path).resolve().relative_to(STAGING.resolve())
    except (ValueError, OSError):
        return SourceKind.OUTSIDE_STAGING
    parts = rel.parts
    if len(parts) >= 2 and parts[0] == "fixtures" and parts[1] == "copied":
        return SourceKind.COPIED_SNAPSHOT
    if len(parts) >= 2 and parts[0] == "fixtures" and parts[1] == "synthetic":
        return SourceKind.SYNTHETIC
    return SourceKind.UNKNOWN


def read_source(path: str | Path, *,
                allowed_kinds: Iterable[SourceKind] = (SourceKind.SYNTHETIC,
                                                       SourceKind.COPIED_SNAPSHOT),
                require_schema_version: bool = False
                ) -> tuple[dict[str, Any] | None, SourceKind, list[SourceProblem]]:
    """Read and validate one staged source. Never raises for a data problem."""
    p = Path(path)
    allowed = tuple(allowed_kinds)
    kind = classify_path(p)
    if kind is SourceKind.OUTSIDE_STAGING:
        # never even open a file outside the staging root
        return None, kind, [source_problem(
            SourceProblemCode.OUTSIDE_STAGING, GapScope.SYSTEM,
            f"source {p.name!r} resolves outside the staging root; the adapter layer "
            f"reads only files under integration-staging/")]
    if not p.is_file():
        return None, kind, [source_problem(
            SourceProblemCode.MISSING_SOURCE, GapScope.SYSTEM,
            f"source {p.name!r} does not exist")]
    try:
        text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return None, kind, [source_problem(
            SourceProblemCode.UNREADABLE_SOURCE, GapScope.SYSTEM,
            f"source {p.name!r} could not be read: {type(exc).__name__}")]
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, kind, [source_problem(
            SourceProblemCode.INVALID_JSON, GapScope.SYSTEM,
            f"source {p.name!r} is not valid JSON: {exc.msg}")]
    parsed, problems = validate_source(data, kind=kind, allowed_kinds=allowed,
                                       source_name=p.name,
                                       require_schema_version=require_schema_version)
    return parsed, kind, problems


def validate_source(data: Any, *, kind: SourceKind,
                    allowed_kinds: Iterable[SourceKind] = (SourceKind.SYNTHETIC,
                                                           SourceKind.COPIED_SNAPSHOT),
                    source_name: str = "<memory>",
                    require_schema_version: bool = False
                    ) -> tuple[dict[str, Any] | None, list[SourceProblem]]:
    """Validate an already-parsed source document (used by the reader and tests)."""
    allowed = tuple(allowed_kinds)
    if not isinstance(data, Mapping):
        return None, [source_problem(
            SourceProblemCode.INVALID_JSON, GapScope.SYSTEM,
            f"source {source_name!r} is not a JSON object")]
    if kind is SourceKind.OUTSIDE_STAGING:
        return None, [source_problem(
            SourceProblemCode.OUTSIDE_STAGING, GapScope.SYSTEM,
            f"source {source_name!r} resolves outside the staging root; the adapter "
            f"layer reads only files under integration-staging/")]
    if kind is SourceKind.UNKNOWN:
        return None, [source_problem(
            SourceProblemCode.UNKNOWN_SOURCE_KIND, GapScope.SYSTEM,
            f"source {source_name!r} is neither under fixtures/synthetic/ nor "
            f"fixtures/copied/; its provenance kind is unknown")]
    if kind not in allowed:
        return None, [source_problem(
            SourceProblemCode.WRONG_SOURCE_KIND, GapScope.SYSTEM,
            f"source {source_name!r} has kind {kind.value!r}; this adapter accepts "
            f"{[k.value for k in allowed]}")]
    declared = data.get("fixture_kind")
    if declared is not None and declared != "synthetic":
        return None, [source_problem(
            SourceProblemCode.WRONG_SOURCE_KIND, GapScope.SYSTEM,
            f"source {source_name!r} declares fixture_kind {declared!r}; the staged "
            f"adapter layer only accepts synthetic or copied_snapshot sources")]
    if kind is SourceKind.SYNTHETIC and declared != "synthetic":
        return None, [source_problem(
            SourceProblemCode.WRONG_SOURCE_KIND, GapScope.SYSTEM,
            f"synthetic source {source_name!r} is not labelled fixture_kind='synthetic'")]
    if kind is SourceKind.COPIED_SNAPSHOT and declared == "synthetic":
        return None, [source_problem(
            SourceProblemCode.WRONG_SOURCE_KIND, GapScope.SYSTEM,
            f"copied source {source_name!r} claims to be synthetic; a copied snapshot "
            f"must not be relabelled")]
    if require_schema_version:
        version = str(data.get("schema_version"))
        if version not in SUPPORTED_SCHEMA_VERSIONS:
            return None, [source_problem(
                SourceProblemCode.UNSUPPORTED_SCHEMA_VERSION, GapScope.SYSTEM,
                f"source {source_name!r} declares schema_version {version!r}; "
                f"supported: {sorted(SUPPORTED_SCHEMA_VERSIONS)}")]
    return dict(data), []


# --------------------------------------------------------------------------- #
# TOEFL source-shape rules (validation only; a URL is never requested)
# --------------------------------------------------------------------------- #
def validate_kmf_url(url: Any) -> tuple[bool, str]:
    """Return ``(ok, reason)`` for a KMF detail URL. Never fetches it."""
    if not isinstance(url, str) or not url.strip():
        return False, "url is absent"
    parts = urlsplit(url.strip())
    if parts.scheme != "https":
        return False, f"scheme {parts.scheme or '(none)'!r} is not https"
    if parts.hostname != KMF_HOST:
        return False, f"host {parts.hostname or '(none)'!r} is not {KMF_HOST}"
    segments = [s for s in parts.path.split("/") if s]
    # a KMF detail URL is /detail/read/<hash>.html, optionally followed by one or
    # more alphanumeric question anchors (the copied index uses /detail/read/<hash>.html/1)
    if len(segments) < 3 or segments[0] != "detail" or segments[1] != "read" \
            or not segments[2].endswith(".html"):
        return False, f"path {parts.path!r} is not /detail/read/<hash>.html"
    token = segments[2][: -len(".html")]
    if not token or not all(c.isalnum() for c in token):
        return False, f"detail token {token!r} is not alphanumeric"
    for anchor in segments[3:]:
        if not anchor.isalnum():
            return False, f"trailing segment {anchor!r} is not alphanumeric"
    return True, "ok"


@dataclass
class CacheEntry:
    """One cache entry, or a problem describing why it could not be used."""

    index: int
    native_id: str | None
    payload: dict[str, Any] | None
    problem: SourceProblem | None


def iter_cache_entries(cache: Any, *, source_name: str,
                       entries_key: str = "entries") -> list[CacheEntry]:
    """Iterate a cache document's entries, reporting a malformed one, not dropping it.

    A cache entry must be an object with a non-empty ``native_id`` (or ``id``).
    Anything else - a non-object, a missing identity, a duplicate identity - is a
    :class:`SourceProblem` attached to that entry index, so a caller can keep the
    usable entries and still show exactly what was rejected (plan 8.4: content
    validation before cache publication).
    """
    out: list[CacheEntry] = []
    if not isinstance(cache, Mapping):
        out.append(CacheEntry(0, None, None, source_problem(
            SourceProblemCode.BAD_CACHE_ENTRY, GapScope.SYSTEM,
            f"cache {source_name!r} is not a JSON object")))
        return out
    raw_entries = cache.get(entries_key)
    if not isinstance(raw_entries, list):
        out.append(CacheEntry(0, None, None, source_problem(
            SourceProblemCode.BAD_CACHE_ENTRY, GapScope.SYSTEM,
            f"cache {source_name!r} has no {entries_key!r} list")))
        return out
    seen: dict[str, int] = {}
    for index, raw in enumerate(raw_entries):
        if not isinstance(raw, Mapping):
            out.append(CacheEntry(index, None, None, source_problem(
                SourceProblemCode.BAD_CACHE_ENTRY, GapScope.SYSTEM,
                f"cache {source_name!r} entry {index} is not a JSON object",
                native_ref=str(index))))
            continue
        native_id = raw.get("native_id") or raw.get("id")
        if not isinstance(native_id, str) or not native_id.strip():
            out.append(CacheEntry(index, None, None, source_problem(
                SourceProblemCode.BAD_CACHE_ENTRY, GapScope.SYSTEM,
                f"cache {source_name!r} entry {index} has no native_id",
                native_ref=str(index))))
            continue
        if native_id in seen:
            out.append(CacheEntry(index, native_id, None, source_problem(
                SourceProblemCode.BAD_CACHE_ENTRY, GapScope.SYSTEM,
                f"cache {source_name!r} entry {index} repeats native_id {native_id!r} "
                f"(first seen at entry {seen[native_id]}); the identity is unresolved",
                native_ref=native_id)))
            continue
        seen[native_id] = index
        out.append(CacheEntry(index, native_id, dict(raw), None))
    return out


__all__ = [
    "STAGING",
    "COPIED_ROOT",
    "SYNTHETIC_ROOT",
    "SUPPORTED_SCHEMA_VERSIONS",
    "KMF_HOST",
    "SourceKind",
    "SourceProblemCode",
    "SourceProblem",
    "source_problem",
    "classify_path",
    "read_source",
    "validate_source",
    "validate_kmf_url",
    "CacheEntry",
    "iter_cache_entries",
]
