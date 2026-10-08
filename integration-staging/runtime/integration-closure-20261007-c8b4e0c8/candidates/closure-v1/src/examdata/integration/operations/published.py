"""Published-data coverage from explicit expected manifests (plan B07).

"Generate coverage from published data and explicit expected manifests": the
observed side is the published dataset (the same catalog entries the read API
serves); the expected side is an *explicit* manifest file - a declared
denominator per scope, with reasoned exclusions and explicit partial
expectations. Nothing here guesses a denominator: a scope whose manifest
declares no denominator keeps ``denominator_known`` false and therefore can
never render a percentage; a scope that does not meet its declared denominator
stays ``partial`` and is never rounded up to complete.

Contract: ``coverage-contract/2.1`` (decision record:
``docs/integration/execution/COVERAGE_CONTRACT_DECISION.md``). Every scope row
carries four disjoint axis counters - ``excluded``, ``unknown``, ``partial``,
``verified`` - that partition the observed universe exactly
(``observed == excluded + unknown + missing + partial + verified``). The
expected-side gap is carried separately as ``unmet``: ``missing`` stays 0
because ``missing`` and ``unmet`` are not interchangeable, and conflating them
would let an unpopulated scope render complete coverage. ``expected`` and
``observed`` are never conflated either: ``observed`` is always the actual
published count, an overfilled scope carries ``overfilled = observed -
expected``, and every contradiction (an overfilled denominator, a manifest
reference that is not published, a duplicate public id with conflicting
content, or an unsupported quality claim) is recorded in the row's ``problems``
and can never render ``complete`` coverage or a percentage. Missing information
is not a contradiction: an entry whose identity fields are not recorded
(``identity_unresolved``) keeps its problem code, lands in the ``unknown``
bucket and leaves the scope ``partial`` - it is an unknown member of the scope,
not a disagreement between the expected and observed sides.

``derived_status`` is one of four states:

* ``unknown`` - the manifest declares no denominator (``expected`` is null);
* ``conflict`` - the row carries at least one contradiction code
  (:data:`CONTRADICTION_CODES`): the observed and expected sides hold mutually
  inconsistent information, so neither a status nor a percentage may be
  rendered (missing information - ``identity_unresolved`` - is not a
  contradiction and never reaches this state on its own);
* ``partial`` - the denominator is known but not fully accounted for
  (``unmet > 0``, unknown or partial entries, a non-positive accountable
  denominator, or the counters do not add up to the accountable denominator);
* ``complete`` - a non-empty accountable denominator (``expected - excluded``
  greater than 0) is fully verified; an empty accountable denominator never
  renders complete.

``percentage`` is the verified share of the *accountable* denominator
(``expected - excluded``); it is ``None`` whenever the denominator is unknown,
the scope is in conflict, or nothing is accountable - a missing percentage is
never rendered as 0 or 100.

The four quality axes are separated explicitly: publication presence
(``observed``), identity completeness (``identity_complete``), content quality
(``content_complete``) and answer verification (``answers_verified``). The
identity and evidence rules are shared with the catalog path through
``contracts.trust`` (schema ``trust/1``): an entry counts as ``verified`` only
when its identity resolves and its quality summary says the content is complete
*and* the answer verification is backed by authoritative evidence
(``source_verified`` or ``manual_adjudicated``). A claim the entry's own
evidence does not support is a ``quality_claim_invalid`` problem and can only
be ``partial``, never ``verified``; an entry with no quality information at all
is ``unknown`` - missing evidence is never promoted to verification.
Classification order is deliberate: a manifest exclusion or partial
expectation wins over the inferred state, and the "not applicable" identity
fields (a top-level question's ``parent_native_id``) never make an identified
entry count as unknown.

Every row carries the ``coverage/1`` contract fields and validates against that
contract, but never emits the internal schema tag itself - a public payload
does not carry internal schema tags - and its static labels use ``#``
separators so the public redactor cannot mistake a label for a filesystem
path.

Nothing here writes, reads the network, a database or a service.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from ..contracts import trust

# ``NOT_APPLICABLE_IDENTITY_FIELDS`` and ``ANSWER_BEARING_KINDS`` are
# re-exported from ``contracts.trust`` (their single source of truth) so
# existing importers of this module keep working.
from ..contracts.trust import ANSWER_BEARING_KINDS, NOT_APPLICABLE_IDENTITY_FIELDS
from .budget import ScanBudget
from .checkpoints import CheckpointTooLargeError, read_bytes_bounded

SCHEMA = "operations-expected/1"
MANIFEST_NAME = "expected-manifest.json"


class ExpectedManifestTooLargeError(Exception):
    """Raised when ``expected-manifest.json`` exceeds its bounded read budget.

    Deliberately *not* a :class:`ValueError` (invalid content) and not an
    ``OSError`` (unreadable file), because the callers map those cases to
    distinct problem codes - a shared base class would make the mapping
    order-dependent. ``bytes_read`` records the true bytes the bounded read
    consumed (probe included) before refusing.
    """

    def __init__(self, message: str, *, bytes_read: int | None = None) -> None:
        super().__init__(message)
        self.bytes_read = bytes_read


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Exclusion:
    public_id: str
    reason: str


@dataclass(frozen=True)
class PartialExpectation:
    public_id: str
    reason: str


@dataclass(frozen=True)
class ExpectedScope:
    id: str
    system: str
    kind: str
    expected: int | None
    note: str | None = None
    exclusions: tuple[Exclusion, ...] = ()
    partial: tuple[PartialExpectation, ...] = ()


@dataclass(frozen=True)
class ExpectedManifest:
    scopes: tuple[ExpectedScope, ...]
    source_label: str
    note: str | None = None

    @property
    def by_id(self) -> dict[str, ExpectedScope]:
        return {scope.id: scope for scope in self.scopes}


def _require_text(value: Any, what: str, *, max_len: int | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"expected manifest: {what} must be a non-empty string")
    text = value.strip()
    if max_len is not None and len(text) > max_len:
        raise ValueError(f"expected manifest: {what} exceeds {max_len} characters")
    return text


def _parse_reasoned_list(value: Any, what: str, item_cls: type, *,
                         id_max_len: int | None = None,
                         reason_max_len: int | None = None) -> tuple:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"expected manifest: {what} must be a list")
    out = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"expected manifest: {what}[{index}] must be an object")
        public_id = _require_text(item.get("public_id"), f"{what}[{index}].public_id",
                                  max_len=id_max_len)
        reason = _require_text(item.get("reason"), f"{what}[{index}].reason",
                               max_len=reason_max_len)
        out.append(item_cls(public_id=public_id, reason=reason))
    return tuple(out)


def _document_depth(document: Any, *, max_depth: int) -> None:
    """Refuse a document nested deeper than ``max_depth`` container levels.

    Iterative (never recursive) and run before the structural walk, so a
    hostile manifest cannot make parsing itself the denial-of-service. The
    root document counts as level 1.
    """
    stack: list[tuple[Any, int]] = [(document, 1)]
    while stack:
        node, depth = stack.pop()
        if depth > max_depth:
            raise ValueError(f"expected manifest: nesting exceeds {max_depth} levels")
        if isinstance(node, dict):
            children: Iterable[Any] = node.values()
        elif isinstance(node, list):
            children = node
        else:
            continue
        for child in children:
            if isinstance(child, (dict, list)):
                stack.append((child, depth + 1))


def _raw_declaration_count(raw: dict[str, Any]) -> int:
    """Raw exclusion/partial entry count a scope declares (lists count only)."""
    total = 0
    for key in ("exclusions", "partial"):
        value = raw.get(key)
        if isinstance(value, list):
            total += len(value)
    return total


def parse_manifest(document: Any, *, source_label: str = MANIFEST_NAME,
                   budget: ScanBudget | None = None) -> ExpectedManifest:
    """Parse and validate an expected manifest; invalid input raises ``ValueError``.

    Structural limits from ``budget`` (a :class:`~.budget.ScanBudget`, or the
    production defaults) are enforced before the expensive work: nesting
    depth, the scope count, the declaration counts and every id/text length
    are bounded first, and every failure message is path-free.
    """
    settings = budget if budget is not None else ScanBudget()
    if not isinstance(document, dict):
        raise ValueError("expected manifest must be a JSON object")
    if document.get("schema") != SCHEMA:
        raise ValueError(
            f"expected manifest schema must be {SCHEMA!r}, got {document.get('schema')!r}")
    _document_depth(document, max_depth=settings.max_depth)
    raw_scopes = document.get("scopes")
    if not isinstance(raw_scopes, list) or not raw_scopes:
        raise ValueError("expected manifest: scopes must be a non-empty list")
    if len(raw_scopes) > settings.max_scopes:
        raise ValueError(
            f"expected manifest: scopes exceed the {settings.max_scopes} scope limit")
    note = document.get("note")
    if isinstance(note, str) and len(note) > settings.max_text_len:
        raise ValueError(
            f"expected manifest: note exceeds {settings.max_text_len} characters")
    scopes: list[ExpectedScope] = []
    seen: set[str] = set()
    total_declarations = 0
    for index, raw in enumerate(raw_scopes):
        if not isinstance(raw, dict):
            raise ValueError(f"expected manifest: scopes[{index}] must be an object")
        scope_id = _require_text(raw.get("id"), f"scopes[{index}].id",
                                 max_len=settings.max_id_len)
        if scope_id in seen:
            raise ValueError(f"expected manifest: duplicate scope id {scope_id!r}")
        seen.add(scope_id)
        declarations = _raw_declaration_count(raw)
        if declarations > settings.max_declarations:
            raise ValueError(
                f"expected manifest: scopes[{index}] declares {declarations} entries, "
                f"over the {settings.max_declarations} per-scope limit")
        total_declarations += declarations
        if total_declarations > settings.max_total_declarations:
            raise ValueError(
                f"expected manifest: declarations exceed the "
                f"{settings.max_total_declarations} total limit")
        expected = raw.get("expected")
        if expected is not None and (not isinstance(expected, int) or isinstance(expected, bool)
                                     or expected < 0):
            raise ValueError(
                f"expected manifest: scopes[{index}].expected must be a non-negative "
                f"integer or null, got {expected!r}")
        note = raw.get("note")
        if isinstance(note, str) and len(note) > settings.max_text_len:
            raise ValueError(
                f"expected manifest: scopes[{index}].note exceeds "
                f"{settings.max_text_len} characters")
        exclusions = _parse_reasoned_list(raw.get("exclusions"), f"scopes[{index}].exclusions",
                                          Exclusion, id_max_len=settings.max_id_len,
                                          reason_max_len=settings.max_text_len)
        partial = _parse_reasoned_list(raw.get("partial"), f"scopes[{index}].partial",
                                       PartialExpectation, id_max_len=settings.max_id_len,
                                       reason_max_len=settings.max_text_len)
        for what, items in (("exclusions", exclusions), ("partial", partial)):
            seen_ids: set[str] = set()
            for item in items:
                if item.public_id in seen_ids:
                    raise ValueError(
                        f"expected manifest: scopes[{index}].{what} repeats public_id "
                        f"{item.public_id!r}")
                seen_ids.add(item.public_id)
        overlap = ({item.public_id for item in exclusions}
                   & {item.public_id for item in partial})
        if overlap:
            raise ValueError(
                f"expected manifest: scopes[{index}] lists {sorted(overlap)!r} in both "
                "exclusions and partial")
        if expected is not None and expected < len(exclusions):
            raise ValueError(
                f"expected manifest: scopes[{index}].expected={expected} is smaller than "
                f"its {len(exclusions)} exclusions")
        scopes.append(ExpectedScope(
            id=scope_id,
            system=_require_text(raw.get("system"), f"scopes[{index}].system"),
            kind=_require_text(raw.get("kind"), f"scopes[{index}].kind"),
            expected=expected,
            note=note if isinstance(note, str) else None,
            exclusions=exclusions,
            partial=partial,
        ))
    note = document.get("note")
    return ExpectedManifest(scopes=tuple(scopes), source_label=source_label,
                            note=note if isinstance(note, str) else None)


def load_expected_manifest(root: str | Path, *, max_bytes: int | None = None,
                           budget: ScanBudget | None = None
                           ) -> ExpectedManifest | None:
    """Load ``expected-manifest.json`` from ``root``; missing file reads as ``None``.

    The file is read through the bounded byte machinery with a
    ``max_manifest_bytes`` cap (1 MiB by default) - never ``Path.read_text``
    - so an oversized manifest raises :class:`ExpectedManifestTooLargeError`
    with no partial parse, and an unreadable file raises ``OSError``
    (:class:`~.checkpoints.CheckpointReadError`).
    """
    settings = budget if budget is not None else ScanBudget()
    cap = settings.max_manifest_bytes if max_bytes is None else max_bytes
    path = Path(root) / MANIFEST_NAME
    if not path.is_file():
        return None
    try:
        data = read_bytes_bounded(path, max_bytes=cap, subject="manifest")
    except CheckpointTooLargeError as exc:
        raise ExpectedManifestTooLargeError(
            f"expected manifest exceeds the {cap} byte read budget",
            bytes_read=exc.bytes_read) from exc
    try:
        document = json.loads(data.decode("utf-8"))
    except RecursionError as exc:
        raise ValueError("expected manifest: too deeply nested to parse") from exc
    return parse_manifest(document, source_label=MANIFEST_NAME, budget=settings)


@dataclass
class PublishedView:
    """Contract-shaped coverage rows plus every derivation problem."""

    rows: list[dict[str, Any]] = field(default_factory=list)
    problems: list[dict[str, Any]] = field(default_factory=list)
    manifest_label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest": self.manifest_label,
            "rows": [dict(row) for row in self.rows],
            "problems": [dict(problem) for problem in self.problems],
        }


# The identity/evidence rules are shared with the catalog path via
# ``contracts.trust`` (schema ``trust/1``); ``NOT_APPLICABLE_IDENTITY_FIELDS``
# and ``ANSWER_BEARING_KINDS`` are re-exported at the top of this module. See
# ``contracts.trust`` for the exact rules and their rationale.


def _identity_is_unknown(entry: Any) -> bool:
    """True when the entry's identity does not resolve under ``trust/1``.

    A missing, empty, ``None`` or ``UNKNOWN`` identity value - or the persisted
    ``"__unknown__"`` encoding - is not a resolved identity, whatever quality
    the entry claims. The not-applicable fields (``parent_native_id``) stay
    exempt: there ``UNKNOWN`` records a known absence, not an unknown state.
    """
    return not trust.identity_resolved(entry)


def _quality_summary(entry: Any) -> dict[str, Any]:
    summary = _field(entry, "quality_summary")
    return summary if isinstance(summary, dict) else {}


def _content_complete(entry: Any) -> bool:
    """True only when the entry's own quality summary declares complete content."""
    return _quality_summary(entry).get("content") == "complete"


def _answers_verified(entry: Any) -> bool:
    """True only for authoritative answer verification, never for absence."""
    return (_quality_summary(entry).get("answer_verification")
            in trust.ANSWER_VERIFIED_VALUES)


def _quality_bucket(entry: Any) -> str | None:
    """Classify one identified entry by its quality evidence (``trust/1``).

    Returns ``"verified"`` (content complete and answers verified with the
    supporting evidence), ``"partial"`` (some quality information, or a claim
    the entry's own evidence does not support), or ``None`` when the entry
    carries no quality information at all - the caller maps that to the
    ``unknown`` bucket.
    """
    state = trust.quality_state(entry)
    return None if state == "unknown" else state


#: The problem codes that mean the observed and expected sides hold *mutually
#: inconsistent information*; any of them forces ``derived_status == "conflict"``
#: and ``percentage is None``. A contradiction is a disagreement - an overfilled
#: denominator, a manifest reference that is not published, a duplicate public
#: id with conflicting content, or an entry whose own quality claim contradicts
#: its evidence - never mere *missing* information. ``identity_unresolved`` is
#: therefore deliberately not here: an entry whose identity fields are not
#: recorded is an unknown member of the scope, so it keeps its problem code,
#: lands in the ``unknown`` bucket and leaves the scope ``partial`` (a
#: percentage is still rendered when the accountable denominator is positive).
#: ``duplicate_public_id_identical`` is not here either: an identical duplicate
#: is deduplicated and recorded, but does not by itself make the scope a
#: conflict.
CONTRADICTION_CODES = frozenset({
    "expected_below_published",
    "expected_below_exclusions",
    "manifest_id_not_published",
    "manifest_id_wrong_scope",
    "manifest_duplicate_reference",
    "manifest_exclusion_partial_overlap",
    "duplicate_public_id",
    "quality_claim_invalid",
})


def _coverage_row(scope: ExpectedScope, *, selected: list[Any],
                  excluded: list[Any], unknown: list[Any],
                  partial: list[Any], verified: list[Any],
                  manifest_label: str, dataset_revision: str | None,
                  computed_at: str,
                  records: list[dict[str, Any]]) -> dict[str, Any]:
    """Build one scope row; ``records`` carries every problem record of the scope.

    This helper may append its own contradiction records
    (``expected_below_published`` / ``expected_below_exclusions``) to
    ``records``; the caller extends the view with the final list, so the row's
    ``problems`` codes and the view's problem records can never disagree.
    """
    excluded_n = len(excluded)
    unknown_n = len(unknown)
    partial_n = len(partial)
    verified_n = len(verified)
    # ``observed`` is the actual published count, never the expected one: the
    # expected side lives in ``expected``/``unmet`` only.
    observed = excluded_n + unknown_n + partial_n + verified_n

    # Axis counters are reported over every selected entry (the whole scope
    # universe), independent of the classification above.
    identity_complete_n = sum(1 for entry in selected if not _identity_is_unknown(entry))
    content_complete_n = sum(1 for entry in selected if _content_complete(entry))
    answers_verified_n = sum(1 for entry in selected if _answers_verified(entry))

    expected = scope.expected
    overfilled = 0
    if expected is None:
        denominator_known = False
        unmet = None
        percentage = None
        derived_status = "unknown"
    else:
        denominator_known = True
        overfilled = max(observed - expected, 0)
        if overfilled:
            records.append({
                "code": "expected_below_published",
                "scope": scope.id,
                "expected": expected,
                "published": observed,
            })
        accountable = expected - excluded_n
        if accountable < 0:
            records.append({
                "code": "expected_below_exclusions",
                "scope": scope.id,
                "expected": expected,
                "excluded": excluded_n,
            })
            accountable = 0
        unmet = max(expected - observed, 0)
        contradiction = any(str(record.get("code", "")) in CONTRADICTION_CODES
                            for record in records)
        percentage = (round(100.0 * verified_n / accountable, 2)
                      if not contradiction and accountable > 0 else None)
        if contradiction:
            derived_status = "conflict"
        elif (accountable <= 0 or unmet > 0 or unknown_n > 0
              or partial_n > 0 or verified_n != accountable):
            derived_status = "partial"
        else:
            derived_status = "complete"

    evidence = [f"manifest:{manifest_label}"]
    if dataset_revision:
        evidence.append(f"dataset:{dataset_revision}")
    return {
        "public_id": f"coverage:published:{scope.id}",
        "scope": f"published:{scope.system}:{scope.kind}",
        "denominator": (f"manifest:{manifest_label}#{scope.id}:expected={expected}"
                        if denominator_known else None),
        "denominator_known": denominator_known,
        "observed": observed,
        "expected": expected,
        "excluded": excluded_n,
        "unknown": unknown_n,
        "missing": 0,
        "unmet": unmet,
        "overfilled": overfilled,
        "partial": partial_n,
        "verified": verified_n,
        "identity_complete": identity_complete_n,
        "content_complete": content_complete_n,
        "answers_verified": answers_verified_n,
        "exclusions": [{"public_id": entry.public_id, "reason": reason}
                       for entry, reason in excluded],
        "problems": sorted({str(record.get("code", "")) for record in records}),
        "computed_at": computed_at,
        "evidence": evidence,
        "derived_status": derived_status,
        "percentage": percentage,
    }


def _field(entry: Any, name: str) -> Any:
    """Attribute or mapping access, so plain dicts derive identically."""
    if isinstance(entry, dict):
        return entry.get(name)
    return getattr(entry, name, None)


def _entry_content_key(entry: Any) -> Any:
    """A comparable content key for duplicate detection (``content_hash`` first)."""
    content_hash = getattr(entry, "content_hash", None)
    if callable(content_hash):
        try:
            value = content_hash()
        except Exception:  # pragma: no cover - defensive: fall back to the dict
            value = None
        if value is not None:
            return ("hash", value)
    to_dict = getattr(entry, "to_dict", None)
    if callable(to_dict):
        return ("dict", to_dict())
    return ("value", entry)


def build_published(entries: Iterable[Any], manifest: ExpectedManifest, *,
                    computed_at: str | None = None,
                    dataset_revision: str | None = None) -> PublishedView:
    """Derive one ``coverage/1`` row per manifest scope from the published entries."""
    # Consume the input exactly once: a generator (or any other one-shot
    # iterable) must not be silently exhausted by the first scope.
    entries = list(entries)
    computed = computed_at or _utc_now()
    view = PublishedView(manifest_label=manifest.source_label)

    # Where every published public id actually lives, so a manifest reference
    # to an id published under a different (system, kind) is reported as
    # ``manifest_id_wrong_scope`` rather than as "not published"; and the
    # membership index by ``(system, kind)``, built once so selecting one
    # scope's entries never rescans the whole list.
    published_scopes: dict[str, set[str]] = {}
    by_scope: dict[tuple[Any, Any], list[Any]] = {}
    for entry in entries:
        published_scopes.setdefault(str(_field(entry, "public_id") or ""), set()).add(
            f"{_field(entry, 'system')}:{_field(entry, 'kind')}")
        scope_key = (_field(entry, "system"), _field(entry, "kind"))
        try:
            bucket = by_scope.setdefault(scope_key, [])
        except TypeError:  # pragma: no cover - defensive: unhashable field value
            continue
        bucket.append(entry)
    for bucket in by_scope.values():
        bucket.sort(key=lambda entry: str(_field(entry, "public_id") or ""))

    for scope in manifest.scopes:
        records: list[dict[str, Any]] = []
        selected = list(by_scope.get((scope.system, scope.kind), ()))
        exclusion_reasons = {item.public_id: item.reason for item in scope.exclusions}
        partial_reasons = {item.public_id: item.reason for item in scope.partial}

        # Manifest bookkeeping: a repeated reference or an exclusion/partial
        # overlap is a contradiction inside the manifest itself.
        for list_name, items in (("exclusions", scope.exclusions),
                                 ("partial", scope.partial)):
            counts = Counter(item.public_id for item in items)
            for public_id, count in sorted(counts.items()):
                if count > 1:
                    records.append({
                        "code": "manifest_duplicate_reference",
                        "scope": scope.id,
                        "public_id": public_id,
                        "list": list_name,
                        "count": count,
                    })
        for public_id in sorted(set(exclusion_reasons) & set(partial_reasons)):
            records.append({
                "code": "manifest_exclusion_partial_overlap",
                "scope": scope.id,
                "public_id": public_id,
            })

        # Deduplicate by public id: the first entry in the existing sorted
        # order is the logical entry used for bucket assignment, and every
        # extra copy is a collision (identical or conflicting content).
        unique: list[Any] = []
        seen: dict[str, Any] = {}
        for entry in selected:
            public_id = str(_field(entry, "public_id") or "")
            if public_id not in seen:
                seen[public_id] = entry
                unique.append(entry)
        counts = Counter(str(_field(entry, "public_id") or "") for entry in selected)
        for public_id, count in sorted(counts.items()):
            if count <= 1:
                continue
            first_key = _entry_content_key(seen[public_id])
            identical = all(
                _entry_content_key(entry) == first_key
                for entry in selected
                if str(_field(entry, "public_id") or "") == public_id)
            records.append({
                "code": ("duplicate_public_id_identical" if identical
                         else "duplicate_public_id"),
                "scope": scope.id,
                "public_id": public_id,
                "copies": count,
            })

        # A manifest reference must name an entry published in this scope; an
        # id published elsewhere is a wrong-scope reference, not "missing".
        published_ids = set(seen)
        for public_id in sorted(set(exclusion_reasons) | set(partial_reasons)):
            if public_id in published_ids:
                continue
            elsewhere = sorted(published_scopes.get(public_id, ()))
            if elsewhere:
                records.append({
                    "code": "manifest_id_wrong_scope",
                    "scope": scope.id,
                    "public_id": public_id,
                    "published_scopes": elsewhere,
                })
            else:
                records.append({
                    "code": "manifest_id_not_published",
                    "scope": scope.id,
                    "public_id": public_id,
                })

        # Classification order is deliberate: an exclusion or a partial
        # expectation the manifest states explicitly wins over the inferred
        # state, because the manifest is the authored authority for scope
        # classification. An entry with an unresolved identity or an
        # unsupported quality claim is recorded as a problem and can only land
        # in ``unknown`` / ``partial``; an identified entry without quality
        # information at all lands in ``unknown`` - never in ``verified``.
        excluded: list[tuple[Any, str]] = []
        partial: list[tuple[Any, str]] = []
        unknown: list[Any] = []
        verified: list[Any] = []
        for entry in unique:
            public_id = str(_field(entry, "public_id") or "")
            identity_problems = trust.identity_problems(
                _field(entry, "kind"), _field(entry, "identity_fields"))
            quality_problems = trust.quality_claim_problems(entry)
            if identity_problems:
                records.append({
                    "code": "identity_unresolved",
                    "scope": scope.id,
                    "public_id": public_id,
                    "detail": "; ".join(identity_problems),
                })
            if quality_problems:
                records.append({
                    "code": "quality_claim_invalid",
                    "scope": scope.id,
                    "public_id": public_id,
                    "detail": "; ".join(quality_problems),
                })
            if public_id in exclusion_reasons:
                excluded.append((entry, exclusion_reasons[public_id]))
                continue
            if public_id in partial_reasons:
                partial.append((entry, partial_reasons[public_id]))
                continue
            if identity_problems:
                unknown.append(entry)
                continue
            bucket = _quality_bucket(entry)
            if bucket == "verified":
                verified.append(entry)
            elif bucket == "partial":
                partial.append((entry, "quality not verified"))
            else:
                unknown.append(entry)

        row = _coverage_row(scope, selected=unique, excluded=excluded,
                            unknown=unknown, partial=partial,
                            verified=verified, manifest_label=manifest.source_label,
                            dataset_revision=dataset_revision, computed_at=computed,
                            records=records)
        if scope.note:
            row["evidence"] = list(row["evidence"]) + [f"note:{scope.note}"]
        view.problems.extend(records)
        view.rows.append(row)
    return view


__all__ = [
    "ANSWER_BEARING_KINDS",
    "CONTRADICTION_CODES",
    "MANIFEST_NAME",
    "NOT_APPLICABLE_IDENTITY_FIELDS",
    "SCHEMA",
    "Exclusion",
    "ExpectedManifest",
    "ExpectedManifestTooLargeError",
    "ExpectedScope",
    "PartialExpectation",
    "PublishedView",
    "build_published",
    "load_expected_manifest",
    "parse_manifest",
]
