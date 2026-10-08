"""Catalog model: one mapping row and one immutable snapshot (plan 7.2, 7.3).

Three shapes live here:

* :class:`CatalogSource` - one *input* mapping: the native identity fields, the
  exact native locator a provider needs, the derived searchable fields, the
  source revision, a quality summary and the evidence labels behind it. A staged
  catalog fixture is a list of these.
* :class:`CatalogEntry` - one *stored* row: the same data plus the stable public
  ID. An entry never duplicates a raw document or audio file, only references it
  (plan 7.2).
* :class:`CatalogSnapshot` - an immutable revision body: the entries, their
  counts, the fixed input revisions, any explanations for removals and the
  problems recorded while building it.

The dataset revision is a pure function of the entries (:func:`compute_revision`),
so two builds of the same entries produce the same revision no matter when they
run: a valid build is reproducible. ``created_at`` and ``input_revisions`` are
deliberately *not* part of the revision, so they cannot make a build
non-reproducible.

Stdlib only. Nothing here reads the original project, the network, or a database.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from ..contracts.base import UNKNOWN, ContractModel
from ..contracts.canonical import public_id as derive_public_id
from ..contracts.enums import EntityKind
from ..contracts import trust

CATALOG_SOURCE_SCHEMA = "catalog-source/1"
CATALOG_ENTRY_SCHEMA = "catalog-entry/1"
CATALOG_SNAPSHOT_SCHEMA = "catalog-snapshot/1"

REVISION_PREFIX = "rev-"
REVISION_HEX_CHARS = 32

#: The explicit "known to be unknown" sentinel (``UNKNOWN``) is not JSON-native
#: and the frozen ``plain()`` would flatten it to the string ``"unknown"``, which
#: would change a canonical identity on a round-trip. The catalog therefore
#: encodes it as this reserved token and decodes it back, so an entry's identity
#: survives ``to_dict`` -> ``from_dict`` unchanged.
UNKNOWN_TOKEN = "__unknown__"


def encode_unknown(value: Any) -> Any:
    """Replace the ``UNKNOWN`` sentinel with its reserved JSON token, recursively."""
    if value is UNKNOWN:
        return UNKNOWN_TOKEN
    if isinstance(value, Mapping):
        return {k: encode_unknown(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [encode_unknown(v) for v in value]
    return value


def decode_unknown(value: Any) -> Any:
    """Replace the reserved token with the ``UNKNOWN`` sentinel, recursively."""
    if value == UNKNOWN_TOKEN:
        return UNKNOWN
    if isinstance(value, Mapping):
        return {k: decode_unknown(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [decode_unknown(v) for v in value]
    return value


def compute_revision(entries: Iterable["CatalogEntry"]) -> str:
    """Deterministic dataset revision: sha256 over the sorted entry rows.

    Only the entries participate, so the revision is reproducible and is never
    perturbed by a timestamp or by a run-local path.
    """
    rows = [e.to_dict() for e in sorted(entries, key=lambda e: e.public_id)]
    blob = json.dumps(rows, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")
    return REVISION_PREFIX + hashlib.sha256(blob).hexdigest()[:REVISION_HEX_CHARS]


def _merge_problems(existing: Iterable[dict[str, Any]],
                    extra: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """``existing`` plus every record of ``extra`` whose identity is new.

    Identity is ``trust.problem_key`` (code, scope, detail, ref); the order of
    ``existing`` is preserved and duplicates are dropped, so merging the same
    records twice is a no-op.
    """
    out = [dict(p) for p in existing]
    seen = {trust.problem_key(p) for p in out}
    for record in extra:
        key = trust.problem_key(record)
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(record))
    return out


@dataclass
class CatalogSource(ContractModel):
    """One mapping input: native identity + locator + searchable fields + quality."""

    SCHEMA = CATALOG_SOURCE_SCHEMA

    kind: str = ""
    system: str = ""
    identity_fields: dict[str, Any] = field(default_factory=dict)
    native_locator: dict[str, Any] = field(default_factory=dict)
    aliases: list[str] = field(default_factory=list)
    container_ref: str | None = None
    course_ref: str | None = None
    searchable: dict[str, Any] = field(default_factory=dict)
    source_revision: str | None = None
    quality_summary: dict[str, str] = field(default_factory=dict)
    content_class: str = "unknown"
    evidence_labels: list[str] = field(default_factory=list)
    lineage: dict[str, Any] | None = None
    content_revision: str | None = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CatalogSource":
        return cls(
            kind=str(payload.get("kind", "")),
            system=str(payload.get("system", "")),
            identity_fields=decode_unknown(dict(payload.get("identity_fields", {}))),
            native_locator=decode_unknown(dict(payload.get("native_locator", {}))),
            aliases=list(payload.get("aliases", [])),
            container_ref=payload.get("container_ref"),
            course_ref=payload.get("course_ref"),
            searchable=dict(payload.get("searchable", {})),
            source_revision=payload.get("source_revision"),
            quality_summary=dict(payload.get("quality_summary", {})),
            content_class=str(payload.get("content_class", "unknown")),
            evidence_labels=list(payload.get("evidence_labels", [])),
            lineage=(dict(payload["lineage"]) if payload.get("lineage") else None),
            content_revision=payload.get("content_revision"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "kind": self.kind,
            "system": self.system,
            "identity_fields": encode_unknown(self.identity_fields),
            "native_locator": encode_unknown(self.native_locator),
            "aliases": list(self.aliases),
            "container_ref": self.container_ref,
            "course_ref": self.course_ref,
            "searchable": dict(self.searchable),
            "source_revision": self.source_revision,
            "quality_summary": dict(self.quality_summary),
            "content_class": self.content_class,
            "evidence_labels": list(self.evidence_labels),
            "lineage": dict(self.lineage) if self.lineage else None,
            "content_revision": self.content_revision,
        }

    def entry_public_id(self) -> str:
        """The stable public ID for this source's native identity.

        Raises ``ValueError``/``KeyError``/``TypeError`` for an unknown kind or
        identity fields that do not match the kind's frozen identity keys; the
        caller turns that into a visible problem rather than a guess.
        """
        return derive_public_id(EntityKind.coerce(self.kind), self.identity_fields)

    def validate(self) -> list[str]:
        problems: list[str] = []
        try:
            EntityKind.coerce(self.kind)
        except ValueError as exc:
            problems.append(f"source: {exc}")
        if not self.system:
            problems.append("source: system is required")
        if not self.identity_fields:
            problems.append("source: identity_fields is empty")
        if not self.native_locator:
            problems.append("source: native_locator is empty")
        # The same identity + evidence rules every entry path enforces: a source
        # that would not survive them is already invalid here.
        problems.extend(f"source: {code}" for code in trust.entry_problems(self))
        return problems


@dataclass
class CatalogEntry(ContractModel):
    """One stored catalog row: a stable ID bound to a native locator and quality."""

    SCHEMA = CATALOG_ENTRY_SCHEMA

    public_id: str = ""
    kind: str = ""
    system: str = ""
    identity_fields: dict[str, Any] = field(default_factory=dict)
    native_locator: dict[str, Any] = field(default_factory=dict)
    aliases: list[str] = field(default_factory=list)
    container_ref: str | None = None
    course_ref: str | None = None
    searchable: dict[str, Any] = field(default_factory=dict)
    source_revision: str | None = None
    quality_summary: dict[str, str] = field(default_factory=dict)
    content_class: str = "unknown"
    evidence_labels: list[str] = field(default_factory=list)
    lineage: dict[str, Any] | None = None
    content_revision: str | None = None

    @classmethod
    def from_source(cls, source: CatalogSource, public_id: str) -> "CatalogEntry":
        return cls(
            public_id=public_id,
            kind=source.kind,
            system=source.system,
            identity_fields=dict(source.identity_fields),
            native_locator=dict(source.native_locator),
            aliases=list(source.aliases),
            container_ref=source.container_ref,
            course_ref=source.course_ref,
            searchable=dict(source.searchable),
            source_revision=source.source_revision,
            quality_summary=dict(source.quality_summary),
            content_class=source.content_class,
            evidence_labels=list(source.evidence_labels),
            lineage=(dict(source.lineage) if source.lineage else None),
            content_revision=source.content_revision,
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CatalogEntry":
        return cls(
            public_id=str(payload.get("public_id", "")),
            kind=str(payload.get("kind", "")),
            system=str(payload.get("system", "")),
            identity_fields=decode_unknown(dict(payload.get("identity_fields", {}))),
            native_locator=decode_unknown(dict(payload.get("native_locator", {}))),
            aliases=list(payload.get("aliases", [])),
            container_ref=payload.get("container_ref"),
            course_ref=payload.get("course_ref"),
            searchable=dict(payload.get("searchable", {})),
            source_revision=payload.get("source_revision"),
            quality_summary=dict(payload.get("quality_summary", {})),
            content_class=str(payload.get("content_class", "unknown")),
            evidence_labels=list(payload.get("evidence_labels", [])),
            lineage=(dict(payload["lineage"]) if payload.get("lineage") else None),
            content_revision=payload.get("content_revision"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "public_id": self.public_id,
            "kind": self.kind,
            "system": self.system,
            "identity_fields": encode_unknown(self.identity_fields),
            "native_locator": encode_unknown(self.native_locator),
            "aliases": list(self.aliases),
            "container_ref": self.container_ref,
            "course_ref": self.course_ref,
            "searchable": dict(self.searchable),
            "source_revision": self.source_revision,
            "quality_summary": dict(self.quality_summary),
            "content_class": self.content_class,
            "evidence_labels": list(self.evidence_labels),
            "lineage": dict(self.lineage) if self.lineage else None,
            "content_revision": self.content_revision,
        }

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not self.public_id:
            problems.append("entry: public_id is empty")
        try:
            EntityKind.coerce(self.kind)
        except ValueError as exc:
            problems.append(f"entry: {exc}")
        if not self.native_locator:
            problems.append("entry: native_locator is empty")
        problems.extend(f"entry: {code}" for code in trust.entry_problems(self))
        return problems

    def load_problems(self) -> list[str]:
        """The trust problems a loader must not silently admit (``trust/1``)."""
        return trust.entry_problems(self)

    def content_hash(self) -> str:
        """A hash of this row's own content (identity + locator + quality)."""
        blob = json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True,
                          separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()


@dataclass
class CatalogSnapshot(ContractModel):
    """An immutable revision body: the entries plus how they were built."""

    SCHEMA = CATALOG_SNAPSHOT_SCHEMA

    dataset_revision: str = ""
    created_at: str | None = None
    input_revisions: dict[str, Any] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    explanations: dict[str, str] = field(default_factory=dict)
    entries: list[CatalogEntry] = field(default_factory=list)
    problems: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CatalogSnapshot":
        snapshot = cls(
            dataset_revision=str(payload.get("dataset_revision", "")),
            created_at=payload.get("created_at"),
            input_revisions=dict(payload.get("input_revisions", {})),
            counts={str(k): int(v) for k, v in payload.get("counts", {}).items()},
            explanations={str(k): str(v) for k, v in payload.get("explanations", {}).items()},
            entries=[CatalogEntry.from_dict(e) for e in payload.get("entries", [])],
            problems=[dict(p) for p in payload.get("problems", [])],
        )
        # A deserialised entry is validated on load: a trust problem the rules
        # reject is recorded on the snapshot, never silently admitted - and never
        # raised, because the rules only downgrade an entry (unknown / partial).
        # The merge is idempotent, so a load/save round-trip is stable.
        snapshot.problems = _merge_problems(snapshot.problems, snapshot.trust_problems())
        return snapshot

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "dataset_revision": self.dataset_revision,
            "created_at": self.created_at,
            "input_revisions": dict(self.input_revisions),
            "counts": dict(self.counts),
            "explanations": dict(self.explanations),
            "entries": [e.to_dict() for e in self.entries],
            "problems": [dict(p) for p in self.problems],
        }

    def by_id(self) -> dict[str, CatalogEntry]:
        return {e.public_id: e for e in self.entries}

    def recompute_revision(self) -> str:
        return compute_revision(self.entries)

    def trust_problems(self) -> list[dict[str, Any]]:
        """The trust problem records of this snapshot's entries (``trust/1``)."""
        out: list[dict[str, Any]] = []
        for entry in self.entries:
            out.extend(trust.entry_problem_records(entry))
        return out

    def validate_entries(self) -> list[dict[str, Any]]:
        """``{public_id, problems}`` for every entry the trust rules reject."""
        out: list[dict[str, Any]] = []
        for entry in self.entries:
            problems = trust.entry_problems(entry)
            if problems:
                out.append({"public_id": entry.public_id, "problems": problems})
        return out

    def validate(self) -> list[str]:
        """Flat ``<public_id>: <code>`` strings for every rejected entry."""
        problems: list[str] = []
        for record in self.validate_entries():
            problems.extend(f"{record['public_id']}: {code}"
                            for code in record["problems"])
        return problems


def counts_for(entries: Iterable[CatalogEntry]) -> dict[str, int]:
    """Per-kind and total counts; deterministic and never a coverage claim."""
    out: dict[str, int] = {"total": 0}
    for entry in entries:
        out["total"] += 1
        out[entry.kind] = out.get(entry.kind, 0) + 1
    return out


__all__ = [
    "CATALOG_SOURCE_SCHEMA",
    "CATALOG_ENTRY_SCHEMA",
    "CATALOG_SNAPSHOT_SCHEMA",
    "REVISION_PREFIX",
    "UNKNOWN_TOKEN",
    "encode_unknown",
    "decode_unknown",
    "compute_revision",
    "counts_for",
    "CatalogSource",
    "CatalogEntry",
    "CatalogSnapshot",
]
