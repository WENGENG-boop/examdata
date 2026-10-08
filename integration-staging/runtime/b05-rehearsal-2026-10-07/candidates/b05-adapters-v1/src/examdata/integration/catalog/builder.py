"""The catalog builder: staged fixtures in, a validated snapshot (or nothing) out.

``CatalogBuilder.build`` follows the plan 7.3 publication transaction up to the
point where a revision is published (the publisher does steps 6-8):

1. select fixed input revisions (recorded, not invented);
2. build into memory (the run-owned staging directory is the publisher's);
3. validate schema, identities, references and counts;
4. diff the previous revision against the new one;
5. reject an unexplained removal or a quality upgrade without evidence;
6-8. (published by :mod:`examdata.integration.catalog.revision`);
9. on any failure return ``snapshot=None`` so a caller cannot publish it.

A build that fails leaves the current pointer untouched because there is no
snapshot to publish. A build that succeeds is reproducible: the dataset revision
is a pure function of the entries.

Stdlib only. Nothing here reads the original project, the network, or a database.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Sequence

from ..contracts.base import UNKNOWN
from ..contracts.enums import ContentClass
from ..contracts.models import Asset, Container, Course, Question, Region
from ..contracts.quality import AUTHORITATIVE_EVIDENCE
from .model import CatalogEntry, CatalogSnapshot, CatalogSource, compute_revision, counts_for
from .store import CatalogStore, DuplicateNativeIdError, problem

#: A value on the "verification" axis. Only a move *up* this axis is a promotion.
_VERIFICATION_ORDER: dict[str, int] = {
    "unknown": 0, "unverified": 0, "conflicting": 0, "unresolved": 0, "not_applicable": 0,
    "manual_adjudicated": 1,
    "verified": 2, "source_verified": 2,
}

_UNVERIFIED_STATES = frozenset({"unknown", "unverified", "conflicting", "unresolved"})


# --------------------------------------------------------------------------- #
# mapping frozen contract entities -> catalog sources
# --------------------------------------------------------------------------- #
def _content_class(value: Any) -> str:
    return value.value if isinstance(value, ContentClass) else str(value)


def source_from_container(system: Any, container: Container) -> CatalogSource:
    """A container's native identity + locator, exactly as the model carries it."""
    kind = container.kind.value if hasattr(container.kind, "value") else str(container.kind)
    return CatalogSource(
        kind="container",
        system=str(system),
        identity_fields={"system": str(system), "kind": kind,
                         "native_identity": dict(container.native_identity)},
        native_locator={"kind": "container", "native_identity": dict(container.native_identity)},
        searchable={"kind": kind, "revision": container.revision, "coverage": container.coverage},
        source_revision=container.revision,
        content_class=_content_class(container.content_class),
        lineage=(container.lineage.to_dict() if container.lineage else None),
        content_revision=container.revision,
    )


def source_from_course(course: Course) -> CatalogSource:
    """A course's native code identity (system, qualification, code, spec version)."""
    return CatalogSource(
        kind="course",
        system=course.system.value,
        identity_fields={
            "system": course.system.value,
            "qualification": course.qualification,
            "native_code": course.native_code,
            "specification_version": course.specification_version,
        },
        native_locator={"kind": "course", "native_code": course.native_code,
                        "qualification": course.qualification},
        aliases=list(course.aliases),
        searchable={"native_code": course.native_code, "names": list(course.names)},
        source_revision=course.specification_version,
        content_class="unknown",
    )


def source_from_question(system: Any, question: Question, *,
                         container_native_identity: Any,
                         parent_native_id: Any = None) -> CatalogSource:
    """A question's native identity; keys the model does not carry use ``UNKNOWN``.

    ``container_native_identity`` and ``parent_native_id`` are required because a
    question's identity depends on its container and parent; a caller that does
    not know them must pass the explicit ``UNKNOWN`` sentinel, never a guess.
    """
    return CatalogSource(
        kind="question",
        system=str(system),
        identity_fields={
            "system": str(system),
            "container_native_identity": container_native_identity,
            "native_id": question.native_id if question.native_id is not None else UNKNOWN,
            "number_path": list(question.number_path),
            "parent_native_id": parent_native_id if parent_native_id is not None else UNKNOWN,
        },
        native_locator={"kind": "question",
                        "container_native_identity": container_native_identity,
                        "native_id": question.native_id,
                        "number_path": list(question.number_path)},
        searchable={"native_id": question.native_id, "stem": question.stem,
                    "question_type": question.question_type.value},
        content_class=_content_class(question.content_class),
        lineage=(question.lineage.to_dict() if question.lineage else None),
    )


def source_from_asset(system: Any, asset: Asset) -> CatalogSource:
    """An asset's content identity (media type + hash + storage mode)."""
    return CatalogSource(
        kind="asset",
        system=str(system),
        identity_fields={"system": str(system), "media_type": asset.media_type,
                         "sha256": asset.sha256, "storage_mode": asset.storage_mode},
        native_locator={"kind": "asset", "sha256": asset.sha256,
                        "storage_mode": asset.storage_mode, "content_link": asset.content_link},
        searchable={"media_type": asset.media_type, "byte_size": asset.byte_size},
        source_revision=asset.revision,
        content_class="unknown",
    )


def source_from_region(system: Any, region: Region) -> CatalogSource:
    """A region's document-bound identity (role + document hash + page + bbox)."""
    return CatalogSource(
        kind="region",
        system=str(system),
        identity_fields={
            "system": str(system),
            "document_role": region.document_role,
            "document_sha256": region.document_sha256,
            "page": region.page,
            "bbox": list(region.bbox),
            "coordinate_system": region.coordinate_system,
        },
        native_locator={"kind": "region", "document_sha256": region.document_sha256,
                        "page": region.page, "bbox": list(region.bbox)},
        searchable={"document_role": region.document_role, "page": region.page},
        content_class="unknown",
    )


# --------------------------------------------------------------------------- #
# diff + quality rules
# --------------------------------------------------------------------------- #
def _entry_quality_upgrades(previous: CatalogEntry, current: CatalogEntry) -> list[str]:
    """Dimensions promoted from an unverified state to a verified one."""
    upgrades: list[str] = []
    for dimension, new_value in current.quality_summary.items():
        old_value = previous.quality_summary.get(dimension)
        if old_value is None:
            continue
        old_rank = _VERIFICATION_ORDER.get(str(old_value))
        new_rank = _VERIFICATION_ORDER.get(str(new_value))
        if old_rank is None or new_rank is None:
            continue
        if str(old_value) in _UNVERIFIED_STATES and new_rank > old_rank:
            upgrades.append(dimension)
    return sorted(upgrades)


def has_authoritative_evidence(entry: CatalogEntry) -> bool:
    """True when the entry carries at least one authoritative evidence label."""
    allowed = {label.value for label in AUTHORITATIVE_EVIDENCE}
    return any(label in allowed for label in entry.evidence_labels)


def diff_snapshots(previous: CatalogSnapshot | None,
                   entries: Sequence[CatalogEntry]) -> dict[str, Any]:
    """Added / removed / changed entries and any quality upgrade between revisions."""
    new = {e.public_id: e for e in entries}
    old = previous.by_id() if previous is not None else {}
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    common = set(new) & set(old)
    changed = sorted(pid for pid in common
                     if new[pid].content_hash() != old[pid].content_hash())
    upgrades = sorted(pid for pid in common
                      if _entry_quality_upgrades(old[pid], new[pid]))
    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "quality_upgrades": upgrades,
        "counts": {"added": len(added), "removed": len(removed),
                   "changed": len(changed), "quality_upgrades": len(upgrades)},
    }


@dataclass
class BuildResult:
    """What one build produced: a publishable snapshot, or the reasons it failed."""

    ok: bool
    snapshot: CatalogSnapshot | None
    candidate_revision: str
    counts: dict[str, int] = field(default_factory=dict)
    diff: dict[str, Any] = field(default_factory=dict)
    problems: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "candidate_revision": self.candidate_revision,
            "counts": dict(self.counts),
            "diff": dict(self.diff),
            "problems": [dict(p) for p in self.problems],
        }


class CatalogBuilder:
    """Builds a catalog snapshot from staged sources only."""

    def build(self, sources: Iterable[CatalogSource], *,
              input_revisions: dict[str, Any] | None = None,
              previous: CatalogSnapshot | None = None,
              explanations: dict[str, str] | None = None,
              created_at: str | None = None) -> BuildResult:
        explanations = dict(explanations or {})
        store = CatalogStore()
        for source in sources:
            try:
                store.add(source)
            except DuplicateNativeIdError:
                pass  # recorded as a problem; the build will fail below

        problems: list[dict[str, Any]] = list(store.problems)
        problems.extend(store.validate_references())

        entries = store.sorted_entries()
        counts = counts_for(entries)
        revision = compute_revision(entries)
        diff = diff_snapshots(previous, entries)

        if previous is not None:
            for pid in diff["removed"]:
                if pid not in explanations:
                    problems.append(problem(
                        "unexplained_removal", "catalog",
                        f"entry {pid} was removed without an explanation", pid))
            for pid in diff["quality_upgrades"]:
                entry = next((e for e in entries if e.public_id == pid), None)
                if entry is not None and not has_authoritative_evidence(entry):
                    problems.append(problem(
                        "unexplained_quality_upgrade", "catalog",
                        f"entry {pid} claims a verified quality state without authoritative "
                        f"evidence", pid))

        ok = not problems
        snapshot = None
        if ok:
            snapshot = CatalogSnapshot(
                dataset_revision=revision,
                created_at=created_at or datetime.now().astimezone().isoformat(timespec="seconds"),
                input_revisions=dict(input_revisions or {}),
                counts=counts,
                explanations=explanations,
                entries=entries,
                problems=[],
            )
        return BuildResult(ok=ok, snapshot=snapshot, candidate_revision=revision,
                           counts=counts, diff=diff, problems=problems)


__all__ = [
    "source_from_container",
    "source_from_course",
    "source_from_question",
    "source_from_asset",
    "source_from_region",
    "has_authoritative_evidence",
    "diff_snapshots",
    "BuildResult",
    "CatalogBuilder",
]
