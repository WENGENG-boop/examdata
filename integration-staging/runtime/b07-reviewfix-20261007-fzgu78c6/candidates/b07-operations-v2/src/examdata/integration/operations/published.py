"""Published-data coverage from explicit expected manifests (plan B07).

"Generate coverage from published data and explicit expected manifests": the
observed side is the published dataset (the same catalog entries the read API
serves); the expected side is an *explicit* manifest file - a declared
denominator per scope, with reasoned exclusions and explicit partial
expectations. Nothing here guesses a denominator: a scope whose manifest
declares no denominator keeps ``denominator_known`` false and therefore can
never render a percentage; a scope that does not meet its declared denominator
stays ``partial`` and is never rounded up to complete.

The row counters keep four questions separate that an inferred state used to
conflate:

* publication presence: ``observed`` is the *actual* published count the
  scope selects, never the manifest figure. The expected-side shortfall is
  ``unmet = max(expected - observed, 0)`` (``None`` when the denominator is
  unknown), and a manifest that declares fewer entries than are published is
  an explicit ``expected_below_published`` problem rendered ``partial`` with
  no percentage - a conflict can never read as complete coverage;
* identity completeness: ``identity_complete`` counts selected entries whose
  identity is not an UNKNOWN sentinel (the known-absence fields in
  ``NOT_APPLICABLE_IDENTITY_FIELDS`` never count against it);
* content quality: ``content_complete`` counts selected entries whose quality
  summary records complete content;
* answer verification: ``answers_verified`` counts selected entries whose
  answers are source-verified or manually adjudicated.

``verified`` needs both complete content and verified answers on the same
entry: an entry whose quality evidence falls short (partial content,
unverified or conflicting answers) is ``partial``, and an entry with no
recognised quality evidence is ``unknown`` - verification is never inferred
from identity alone. The axis counters are raw counts over every entry the
scope selects and stay independent of the classification buckets.

``percentage`` is ``verified`` over the accountable denominator
``expected - excluded`` and is only rendered when that denominator is known,
positive and conflict-free. Rows still carry every ``coverage/1`` contract
field and validate against that contract - now plus the additive
``expected``/``unmet`` and axis keys - but never emit the internal schema tag
itself, and their static labels use ``#`` separators so the public redactor
cannot mistake a label for a filesystem path. Counters partition the observed
universe exactly
(``observed == excluded + unknown + missing + partial + verified``; ``missing``
is always 0 so the expected-side gap lives only in ``unmet``), and a manifest
that is inconsistent with the published data is recorded as an explicit
problem instead of being silently repaired. Classification is deliberate: a
manifest exclusion or partial expectation wins over the inferred unknown
state, an unknown identity wins over quality evidence, and the "not
applicable" identity fields (a top-level question's ``parent_native_id``)
never make an identified entry count as unknown.

``entries`` may be any iterable (list, tuple or generator); it is consumed
once into an internal list so every scope of a multi-scope manifest sees
every entry.

Nothing here writes, reads the network, a database or a service.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from ..contracts.base import UNKNOWN, UnknownType

SCHEMA = "operations-expected/1"
MANIFEST_NAME = "expected-manifest.json"


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


def _require_text(value: Any, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"expected manifest: {what} must be a non-empty string")
    return value.strip()


def _parse_reasoned_list(value: Any, what: str, item_cls: type) -> tuple:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"expected manifest: {what} must be a list")
    out = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"expected manifest: {what}[{index}] must be an object")
        public_id = _require_text(item.get("public_id"), f"{what}[{index}].public_id")
        reason = _require_text(item.get("reason"), f"{what}[{index}].reason")
        out.append(item_cls(public_id=public_id, reason=reason))
    return tuple(out)


def parse_manifest(document: Any, *, source_label: str = MANIFEST_NAME) -> ExpectedManifest:
    """Parse and validate an expected manifest; invalid input raises ``ValueError``."""
    if not isinstance(document, dict):
        raise ValueError("expected manifest must be a JSON object")
    if document.get("schema") != SCHEMA:
        raise ValueError(
            f"expected manifest schema must be {SCHEMA!r}, got {document.get('schema')!r}")
    raw_scopes = document.get("scopes")
    if not isinstance(raw_scopes, list) or not raw_scopes:
        raise ValueError("expected manifest: scopes must be a non-empty list")
    scopes: list[ExpectedScope] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_scopes):
        if not isinstance(raw, dict):
            raise ValueError(f"expected manifest: scopes[{index}] must be an object")
        scope_id = _require_text(raw.get("id"), f"scopes[{index}].id")
        if scope_id in seen:
            raise ValueError(f"expected manifest: duplicate scope id {scope_id!r}")
        seen.add(scope_id)
        expected = raw.get("expected")
        if expected is not None and (not isinstance(expected, int) or isinstance(expected, bool)
                                     or expected < 0):
            raise ValueError(
                f"expected manifest: scopes[{index}].expected must be a non-negative "
                f"integer or null, got {expected!r}")
        note = raw.get("note")
        scopes.append(ExpectedScope(
            id=scope_id,
            system=_require_text(raw.get("system"), f"scopes[{index}].system"),
            kind=_require_text(raw.get("kind"), f"scopes[{index}].kind"),
            expected=expected,
            note=note if isinstance(note, str) else None,
            exclusions=_parse_reasoned_list(raw.get("exclusions"), f"scopes[{index}].exclusions",
                                            Exclusion),
            partial=_parse_reasoned_list(raw.get("partial"), f"scopes[{index}].partial",
                                         PartialExpectation),
        ))
    note = document.get("note")
    return ExpectedManifest(scopes=tuple(scopes), source_label=source_label,
                            note=note if isinstance(note, str) else None)


def load_expected_manifest(root: str | Path) -> ExpectedManifest | None:
    """Load ``expected-manifest.json`` from ``root``; missing file reads as ``None``."""
    path = Path(root) / MANIFEST_NAME
    if not path.is_file():
        return None
    document = json.loads(path.read_text(encoding="utf-8"))
    return parse_manifest(document, source_label=MANIFEST_NAME)


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


#: Identity fields where the catalog's UNKNOWN sentinel records a *known
#: absence* ("this question has no parent"), not an unknown state; such a field
#: must never push an otherwise identified entry into the unknown bucket.
NOT_APPLICABLE_IDENTITY_FIELDS = frozenset({"parent_native_id"})

#: Quality-summary fields this module recognises. A quality summary with none
#: of them carries no usable evidence and leaves its entry ``unknown``.
_QUALITY_FIELDS = frozenset({"content", "answer_presence", "answer_verification"})

#: Answer-verification values that count as verified answers. Everything else
#: (``unverified``, ``conflicting``, any unknown value) falls short.
_ANSWER_VERIFIED = frozenset({"source_verified", "manual_adjudicated"})


def _identity_is_unknown(entry: Any) -> bool:
    fields = getattr(entry, "identity_fields", None)
    if not isinstance(fields, dict):
        return False
    return any(
        key not in NOT_APPLICABLE_IDENTITY_FIELDS
        and (isinstance(value, UnknownType) or value is UNKNOWN)
        for key, value in fields.items())


def _quality_summary(entry: Any) -> dict[str, Any]:
    summary = getattr(entry, "quality_summary", None)
    return summary if isinstance(summary, dict) else {}


def _content_complete(entry: Any) -> bool:
    return _quality_summary(entry).get("content") == "complete"


def _answers_verified(entry: Any) -> bool:
    value = _quality_summary(entry).get("answer_verification")
    return isinstance(value, str) and value in _ANSWER_VERIFIED


def _quality_bucket(entry: Any) -> str | None:
    """``"verified"``/``"partial"`` from quality evidence, or ``None`` if absent.

    A verified entry needs complete content and source-verified or manually
    adjudicated answers. A summary that carries a recognised quality field but
    does not reach that bar is explicitly ``"partial"``; a summary with no
    recognised field (empty or missing) has no evidence at all and reads as
    ``None``, which leaves the entry in the unknown bucket.
    """
    summary = _quality_summary(entry)
    if not _QUALITY_FIELDS & summary.keys():
        return None
    if _content_complete(entry) and _answers_verified(entry):
        return "verified"
    return "partial"


def _coverage_row(scope: ExpectedScope, *, excluded: list[Any], unknown: list[Any],
                  partial: list[Any], verified: list[Any],
                  identity_complete: int, content_complete: int,
                  answers_verified: int,
                  manifest_label: str, dataset_revision: str | None,
                  computed_at: str, problems: list[dict[str, Any]]) -> dict[str, Any]:
    excluded_n = len(excluded)
    unknown_n = len(unknown)
    partial_n = len(partial)
    verified_n = len(verified)
    observed = excluded_n + unknown_n + partial_n + verified_n

    if scope.expected is None:
        denominator_known = False
        expected = None
        unmet = None
        percentage = None
        derived_status = "unknown"
    else:
        denominator_known = True
        expected = scope.expected
        conflict = observed > expected
        unmet = max(expected - observed, 0)
        if conflict:
            problems.append({
                "code": "expected_below_published",
                "scope": scope.id,
                "expected": expected,
                "published": observed,
            })
        accountable = expected - excluded_n
        percentage = (round(100.0 * verified_n / accountable, 2)
                      if not conflict and accountable > 0 else None)
        derived_status = ("complete" if observed == expected and expected > 0
                          and partial_n == 0 and unknown_n == 0 else "partial")

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
        "excluded": excluded_n,
        "unknown": unknown_n,
        "missing": 0,
        "partial": partial_n,
        "verified": verified_n,
        "expected": expected,
        "unmet": unmet,
        "identity_complete": identity_complete,
        "content_complete": content_complete,
        "answers_verified": answers_verified,
        "exclusions": [{"public_id": entry.public_id, "reason": reason}
                       for entry, reason in excluded],
        "computed_at": computed_at,
        "evidence": evidence,
        "derived_status": derived_status,
        "percentage": percentage,
    }


def build_published(entries: Iterable[Any], manifest: ExpectedManifest, *,
                    computed_at: str | None = None,
                    dataset_revision: str | None = None) -> PublishedView:
    """Derive one ``coverage/1`` row per manifest scope from the published entries."""
    computed = computed_at or _utc_now()
    # A multi-scope manifest must see every entry, and callers pass any
    # iterable (the read API passes a generator): consume it exactly once.
    published_entries = list(entries)
    view = PublishedView(manifest_label=manifest.source_label)
    for scope in manifest.scopes:
        selected = [entry for entry in published_entries
                    if getattr(entry, "system", None) == scope.system
                    and getattr(entry, "kind", None) == scope.kind]
        selected.sort(key=lambda entry: str(getattr(entry, "public_id", "")))
        exclusion_reasons = {item.public_id: item.reason for item in scope.exclusions}
        partial_reasons = {item.public_id: item.reason for item in scope.partial}

        excluded: list[tuple[Any, str]] = []
        rest: list[Any] = []
        for entry in selected:
            public_id = str(getattr(entry, "public_id", ""))
            if public_id in exclusion_reasons:
                excluded.append((entry, exclusion_reasons[public_id]))
            else:
                rest.append(entry)

        # Classification order is deliberate: an exclusion or a partial
        # expectation the manifest states explicitly wins over the inferred
        # unknown state, because the manifest is the authored authority for
        # scope classification. An unknown identity in turn wins over quality
        # evidence: a lost entry stays unknown even when its quality summary
        # claims otherwise, and quality evidence alone decides the rest -
        # never identity alone.
        partial: list[Any] = []
        unknown: list[Any] = []
        verified: list[Any] = []
        for entry in rest:
            public_id = str(getattr(entry, "public_id", ""))
            if public_id in partial_reasons:
                partial.append(entry)
            elif _identity_is_unknown(entry):
                unknown.append(entry)
            else:
                bucket = _quality_bucket(entry)
                if bucket == "verified":
                    verified.append(entry)
                elif bucket == "partial":
                    partial.append(entry)
                else:
                    unknown.append(entry)

        published_ids = {str(getattr(entry, "public_id", "")) for entry in selected}
        for public_id in sorted(set(exclusion_reasons) | set(partial_reasons)):
            if public_id not in published_ids:
                view.problems.append({
                    "code": "manifest_id_not_published",
                    "scope": scope.id,
                    "public_id": public_id,
                })

        row = _coverage_row(
            scope, excluded=excluded, unknown=unknown, partial=partial,
            verified=verified,
            identity_complete=sum(1 for entry in selected
                                  if not _identity_is_unknown(entry)),
            content_complete=sum(1 for entry in selected if _content_complete(entry)),
            answers_verified=sum(1 for entry in selected if _answers_verified(entry)),
            manifest_label=manifest.source_label,
            dataset_revision=dataset_revision, computed_at=computed,
            problems=view.problems)
        if scope.note:
            row["evidence"] = list(row["evidence"]) + [f"note:{scope.note}"]
        view.rows.append(row)
    return view


__all__ = [
    "MANIFEST_NAME",
    "NOT_APPLICABLE_IDENTITY_FIELDS",
    "SCHEMA",
    "Exclusion",
    "ExpectedManifest",
    "ExpectedScope",
    "PartialExpectation",
    "PublishedView",
    "build_published",
    "load_expected_manifest",
    "parse_manifest",
]
