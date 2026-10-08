"""The active-owner feature seam (plan 8.5, B05).

Materials, syllabuses and timetables are the plan's *active-owner* families: the
original project owner keeps them, and the staged integration serves clearly
labelled synthetic fixtures until the real owner module is released. This module
is the single seam a feature source plugs into:

* :class:`FeatureSource` - the five family methods the app factory reads through;
* :func:`validate_feature_source` and the ``check_*`` validators - every row must
  carry the synthetic provenance markers, and each family's fields must stay
  coherent: no live access is ever claimed, an event date never appears without
  the raw line it came from, and unknown timetable boundaries stay null and
  declared;
* :class:`FixtureFeatureSource` - the read-only fixture implementation the
  staged dataset serves, which validates every row in its constructor.

A later real-owner integration replaces the *source*, not the routes: the
application reads ``Dataset.features``, so the seam is the one extension point.
Nothing here reads the original tree, the network, a database or Kimi-owned
timetable code.
"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any, Protocol

EVIDENCE_SYNTHETIC = "synthetic_fixture"
DEFERRED_ACTIVE_OWNER = "deferred_active_owner"

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_BOUNDARIES = ("start", "end")


class FeatureRowError(ValueError):
    """A feature row would over-claim what the staged layer knows."""


def _require_mapping(row: Any, family: str) -> Mapping[str, Any]:
    if not isinstance(row, Mapping):
        raise FeatureRowError(f"{family} row {row!r} is not a mapping")
    return row


def _label(row: Mapping[str, Any], keys: tuple[str, ...]) -> str:
    return "/".join(str(row.get(k, "?")) for k in keys)


def _markers(row: Mapping[str, Any], family: str, label: str) -> None:
    if row.get("evidence") != EVIDENCE_SYNTHETIC:
        raise FeatureRowError(
            f"{family} {label} is not labelled {EVIDENCE_SYNTHETIC!r} "
            f"(found {row.get('evidence')!r}); every staged row must carry the "
            "synthetic evidence marker")
    if row.get("integration_status") != DEFERRED_ACTIVE_OWNER:
        raise FeatureRowError(
            f"{family} {label} is not labelled {DEFERRED_ACTIVE_OWNER!r} "
            f"(found {row.get('integration_status')!r}); the real active-owner "
            "integration stays deferred")


def _text(row: Mapping[str, Any], key: str, family: str, label: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value:
        raise FeatureRowError(
            f"{family} {label} needs a non-empty {key!r}, found {value!r}")
    return value


def _nonempty_list(row: Mapping[str, Any], key: str, family: str,
                   label: str) -> list[Any]:
    value = row.get(key)
    if not isinstance(value, (list, tuple)) or not value:
        raise FeatureRowError(
            f"{family} {label} needs a non-empty {key!r} list, found {value!r}")
    return list(value)


def _is_year(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _iso_or_none(value: Any, what: str) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not _ISO_DATE.match(value):
        raise FeatureRowError(
            f"{what} must be an ISO date (YYYY-MM-DD) or null, found {value!r}")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise FeatureRowError(f"{what} is not a real calendar date: {value!r}") from exc


def check_syllabus(row: Mapping[str, Any]) -> None:
    """One syllabus row: both markers, identity text, synthetic source evidence."""
    family = "syllabus"
    row = _require_mapping(row, family)
    label = _label(row, ("public_id",))
    _markers(row, family, label)
    for key in ("public_id", "system", "version"):
        _text(row, key, family, label)
    evidence = _nonempty_list(row, "source_evidence", family, label)
    if EVIDENCE_SYNTHETIC not in evidence:
        raise FeatureRowError(
            f"{family} {label} source_evidence {evidence!r} does not carry "
            f"{EVIDENCE_SYNTHETIC!r}")
    years = row.get("applicable_years")
    if not isinstance(years, list) or not all(_is_year(y) for y in years):
        raise FeatureRowError(
            f"{family} {label} applicable_years must be a list of integer years, "
            f"found {years!r}")


def check_material(row: Mapping[str, Any]) -> None:
    """One material row: both markers, identity text, fixture-only access, versions."""
    family = "material"
    row = _require_mapping(row, family)
    label = _label(row, ("public_id",))
    _markers(row, family, label)
    for key in ("public_id", "system", "kind", "native_id"):
        _text(row, key, family, label)
    access = row.get("access_mode")
    if access != "fixture_only":
        raise FeatureRowError(
            f"{family} {label} declares access_mode {access!r}; the staged layer "
            "serves fixture-only materials and never claims live access")
    for version in _nonempty_list(row, "versions", family, label):
        if not isinstance(version, str) or not version:
            raise FeatureRowError(
                f"{family} {label} versions must be non-empty strings, "
                f"found {version!r}")


def check_season(row: Mapping[str, Any]) -> None:
    """One timetable season row: both markers, a declared availability, a year."""
    family = "timetable season"
    row = _require_mapping(row, family)
    label = _label(row, ("system", "season", "year"))
    _markers(row, family, label)
    _text(row, "system", family, label)
    if not _is_year(row.get("year")):
        raise FeatureRowError(
            f"{family} {label} needs an integer year, found {row.get('year')!r}")
    availability = row.get("availability")
    if availability not in ("available", "unavailable", "unknown"):
        raise FeatureRowError(
            f"{family} {label} availability must be exactly one of 'available', "
            f"'unavailable', 'unknown', found {availability!r}")
    if availability == "unavailable":
        reason = row.get("reason")
        if not isinstance(reason, str) or not reason:
            raise FeatureRowError(
                f"{family} {label} is unavailable without a reason; an unavailable "
                "season is reported explicitly, never silently dropped")


def check_event(row: Mapping[str, Any]) -> None:
    """One timetable event row: both markers, a null-or-sourced date, a session."""
    family = "timetable event"
    row = _require_mapping(row, family)
    label = _label(row, ("system", "zone", "course_native_code", "component"))
    _markers(row, family, label)
    _text(row, "system", family, label)
    _iso_or_none(row.get("date"), f"{family} {label} date")
    session = row.get("session")
    if session is not None and not isinstance(session, str):
        raise FeatureRowError(
            f"{family} {label} session must be a string or null, found {session!r}")
    if row.get("date") is not None:
        raw_text = row.get("raw_text")
        if not isinstance(raw_text, str) or not raw_text:
            raise FeatureRowError(
                f"{family} {label} carries a date without the raw timetable line "
                "it came from; a date may never be inferred")


def check_window(row: Mapping[str, Any]) -> None:
    """One timetable window row: declared unknown boundaries match the parsed map."""
    family = "timetable window"
    row = _require_mapping(row, family)
    label = _label(row, ("system", "zone"))
    _markers(row, family, label)
    _text(row, "system", family, label)
    unknown = row.get("unknown_boundaries")
    if not isinstance(unknown, (list, tuple)) or not all(
            b in _BOUNDARIES for b in unknown):
        raise FeatureRowError(
            f"{family} {label} unknown_boundaries must list only 'start'/'end', "
            f"found {unknown!r}")
    if len(set(unknown)) != len(unknown):
        raise FeatureRowError(
            f"{family} {label} unknown_boundaries repeats a boundary: {unknown!r}")
    parsed = row.get("parsed")
    if not isinstance(parsed, Mapping):
        raise FeatureRowError(
            f"{family} {label} needs a parsed boundaries mapping, found {parsed!r}")
    for key in _BOUNDARIES:
        value = parsed.get(key)
        if key in unknown:
            if value is not None:
                raise FeatureRowError(
                    f"{family} {label} declares {key!r} unknown but carries a "
                    f"parsed {key!r} of {value!r}")
            continue
        if value is None:
            raise FeatureRowError(
                f"{family} {label} has no parsed {key!r} and does not declare it "
                "unknown; a missing boundary must be declared, never defaulted")
        _iso_or_none(value, f"{family} {label} parsed {key!r}")


class FeatureSource(Protocol):
    """The family methods the app factory reads through the seam.

    Every method returns a fresh list of row mappings; mutating a returned row
    must never change the source or a later caller's view of it.
    """

    def syllabuses(self) -> list[dict[str, Any]]:
        """Clearly labelled synthetic syllabus rows."""

    def materials(self) -> list[dict[str, Any]]:
        """Clearly labelled synthetic material rows."""

    def timetable_seasons(self) -> list[dict[str, Any]]:
        """Clearly labelled synthetic season rows."""

    def timetable_events(self) -> list[dict[str, Any]]:
        """Clearly labelled synthetic event rows."""

    def timetable_windows(self) -> list[dict[str, Any]]:
        """Clearly labelled synthetic window rows."""


def _validated_rows(family: str, rows: Any, check: Any) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(rows, (list, tuple)):
        raise FeatureRowError(
            f"{family}() must return a list of rows, found {type(rows).__name__}")
    for row in rows:
        check(row)
    return tuple(rows)


class FixtureFeatureSource:
    """The read-only fixture source the staged dataset serves.

    Every row is validated in the constructor, so an application can only be
    built on a source whose provenance markers and family shapes are complete.
    Accessors hand out fresh ``dict`` copies: a caller can never mutate the
    staged fixtures, or another caller's view of them, in place.
    """

    def __init__(self, *, syllabuses: Sequence[Mapping[str, Any]],
                 materials: Sequence[Mapping[str, Any]],
                 timetable_seasons: Sequence[Mapping[str, Any]],
                 timetable_events: Sequence[Mapping[str, Any]],
                 timetable_windows: Sequence[Mapping[str, Any]]) -> None:
        self._syllabuses = _validated_rows("syllabuses", syllabuses, check_syllabus)
        self._materials = _validated_rows("materials", materials, check_material)
        self._timetable_seasons = _validated_rows(
            "timetable_seasons", timetable_seasons, check_season)
        self._timetable_events = _validated_rows(
            "timetable_events", timetable_events, check_event)
        self._timetable_windows = _validated_rows(
            "timetable_windows", timetable_windows, check_window)

    def syllabuses(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._syllabuses]

    def materials(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._materials]

    def timetable_seasons(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._timetable_seasons]

    def timetable_events(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._timetable_events]

    def timetable_windows(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._timetable_windows]


_FAMILIES: tuple[tuple[str, str, Any], ...] = (
    ("syllabuses", "syllabuses", check_syllabus),
    ("materials", "materials", check_material),
    ("timetable_seasons", "timetable_seasons", check_season),
    ("timetable_events", "timetable_events", check_event),
    ("timetable_windows", "timetable_windows", check_window),
)


def validate_feature_source(source: FeatureSource) -> dict[str, int]:
    """Validate every family and return the per-family row counts.

    The first violating row raises :class:`FeatureRowError`, so a source that
    would over-claim can never quietly reach the routes.
    """
    counts: dict[str, int] = {}
    for name, method, check in _FAMILIES:
        rows = getattr(source, method)()
        counts[name] = len(_validated_rows(name, rows, check))
    return counts


__all__ = [
    "DEFERRED_ACTIVE_OWNER",
    "EVIDENCE_SYNTHETIC",
    "FeatureRowError",
    "FeatureSource",
    "FixtureFeatureSource",
    "check_event",
    "check_material",
    "check_season",
    "check_syllabus",
    "check_window",
    "validate_feature_source",
]
