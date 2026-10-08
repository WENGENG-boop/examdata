"""The private mapping/catalog store (plan 7.2, 4.2; packet A09).

``CatalogStore`` is where a native identity becomes a stable public ID and a
stored row. It is the only place that decides:

* the public ID of a mapping input (delegated to the frozen A04 identity rules -
  the same native identity always yields the same ID, and the ID never depends on
  a row number);
* whether a re-registration is a *benign duplicate* (same identity, same content)
  or a *duplicate native id* (same identity, different content) - the second is
  recorded **and** raised, so it can never be silently merged;
* whether two different native identities collide on one public ID - delegated to
  the registry, which records and raises;
* whether an entry's cross-references resolve inside the catalog.

Nothing here opens a file the caller did not name and nothing here reads the
original project. Stdlib only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from ..contracts.base import Gap
from ..contracts.canonical import canonical_identity_string, public_id as derive_public_id
from ..contracts.enums import EntityKind, GapCode, GapScope
from ..contracts.ids import (
    AliasConflictError,
    IdentityCollisionError,
    IdentityRegistry,
)
from ..contracts import trust
from .model import CatalogEntry, CatalogSnapshot, CatalogSource, counts_for


class CatalogError(Exception):
    """Base class for catalog-mapping failures."""


class DuplicateNativeIdError(CatalogError):
    """One native identity was registered with two different content revisions."""


class UnresolvedReferenceError(CatalogError):
    """An entry references a public ID that is not in the catalog."""


#: Catalog problem code -> the frozen contract gap it corresponds to. Codes not
#: listed here are catalog diagnostics and do not become contract gaps.
GAP_FOR_CODE: dict[str, str] = {
    "duplicate_native_id": GapCode.UNRESOLVED_IDENTITY.value,
    "identity_collision": GapCode.UNRESOLVED_IDENTITY.value,
    "alias_conflict": GapCode.UNRESOLVED_IDENTITY.value,
    "unresolved_identity": GapCode.UNRESOLVED_IDENTITY.value,
    "invalid_identity": GapCode.UNRESOLVED_IDENTITY.value,
}


def problem(code: str, scope: str, detail: str, ref: str | None = None) -> dict[str, Any]:
    """A visible catalog problem; never silently dropped, never a pass."""
    out: dict[str, Any] = {"code": code, "scope": scope, "detail": detail}
    if ref:
        out["ref"] = ref
    return out


def to_gap(record: dict[str, Any]) -> Gap | None:
    """Translate a catalog problem into a frozen contract gap when one applies.

    A catalog problem is a mapping concern, so it maps to the system scope; the
    problem's own ``scope`` field keeps the finer role (``container_ref`` /
    ``course_ref``) visible.
    """
    code = GAP_FOR_CODE.get(record.get("code", ""))
    if code is None:
        return None
    return Gap(code=code, scope=GapScope.SYSTEM.value, detail=record.get("detail"))


@dataclass
class CatalogStore:
    """A mapping store: public ID -> entry, with identity and reference checks."""

    registry: IdentityRegistry = field(default_factory=IdentityRegistry)
    entries: dict[str, CatalogEntry] = field(default_factory=dict)
    problems: list[dict[str, Any]] = field(default_factory=list)
    duplicates: list[dict[str, Any]] = field(default_factory=list)
    #: Entries whose identity keys are all present (so their public ID is
    #: derivable) but whose values are ``None``/``UNKNOWN``/empty: the entry is
    #: stored and visibly flagged, never silently treated as resolved. Kept
    #: apart from ``problems`` because it does not by itself fail a build.
    identity_problems: list[dict[str, Any]] = field(default_factory=list)

    # -- registration -----------------------------------------------------------
    def add(self, source: CatalogSource) -> CatalogEntry | None:
        """Register one mapping input; return the stored entry or ``None``.

        A structurally invalid identity is recorded as a problem and skipped. An
        identity collision or an alias conflict is recorded (the registry also
        records it) and skipped. A duplicate native id - the same identity seen
        again with different content - is recorded **and raised**. A stored entry
        whose identity values are unresolved is flagged in
        :attr:`identity_problems`; a stored entry whose quality claims are not
        backed by evidence is recorded in :attr:`problems` (fatal to a build).
        """
        try:
            kind = EntityKind.coerce(source.kind)
            canonical_identity_string(kind, source.identity_fields)
            pid = derive_public_id(kind, source.identity_fields)
        except (ValueError, KeyError, TypeError) as exc:
            self.problems.append(problem("invalid_identity", "catalog", str(exc)))
            return None

        try:
            self.registry.register(
                kind,
                source.identity_fields,
                native_locator=source.native_locator,
                aliases=source.aliases,
                content_revision=source.content_revision,
            )
        except IdentityCollisionError as exc:
            self.problems.append(problem("identity_collision", "catalog", str(exc), pid))
            return None
        except AliasConflictError as exc:
            self.problems.append(problem("alias_conflict", "catalog", str(exc), pid))
            return None

        existing = self.entries.get(pid)
        if existing is not None:
            identical = (existing.content_revision == source.content_revision
                         and existing.native_locator == dict(source.native_locator))
            record = {
                "public_id": pid,
                "code": "duplicate_native_id",
                "benign": identical,
                "detail": ("identical re-registration" if identical
                           else "same native identity with different content"),
            }
            self.duplicates.append(record)
            if identical:
                return existing
            self.problems.append(problem(
                "duplicate_native_id", "catalog",
                "native identity registered twice with different content", pid))
            raise DuplicateNativeIdError(
                f"{pid}: native identity registered with different content "
                f"({existing.content_revision!r} vs {source.content_revision!r})")

        entry = CatalogEntry.from_source(source, pid)
        self.entries[pid] = entry
        for record in trust.entry_problem_records(entry):
            target = (self.identity_problems
                      if record["code"] == trust.IDENTITY_PROBLEM_CODE
                      else self.problems)
            target.append(record)
        return entry

    def add_all(self, sources: Iterable[CatalogSource]) -> list[CatalogEntry | None]:
        """Register many sources, catching duplicate native ids so a build keeps going."""
        out: list[CatalogEntry | None] = []
        for source in sources:
            try:
                out.append(self.add(source))
            except DuplicateNativeIdError:
                out.append(None)
        return out

    # -- lookup -----------------------------------------------------------------
    def resolve(self, reference: str) -> str | None:
        """Resolve a public ID or an alias to a public ID, or ``None``."""
        if reference in self.entries:
            return reference
        return self.registry.resolve_alias(reference)

    def native_locator(self, public_id: str) -> dict[str, Any]:
        """Round-trip helper: the exact native locator a provider needs."""
        entry = self.entries.get(public_id)
        if entry is not None:
            return dict(entry.native_locator)
        return self.registry.native_locator(public_id)

    def sorted_entries(self) -> list[CatalogEntry]:
        return [self.entries[k] for k in sorted(self.entries)]

    # -- validation -------------------------------------------------------------
    def validate_references(self) -> list[dict[str, Any]]:
        """Every cross-reference must resolve inside the catalog (incomplete -> problem)."""
        problems: list[dict[str, Any]] = []
        for pid in sorted(self.entries):
            entry = self.entries[pid]
            for role, ref in (("container_ref", entry.container_ref),
                              ("course_ref", entry.course_ref)):
                if ref and self.resolve(ref) is None:
                    problems.append(problem(
                        "unresolved_identity", role,
                        f"{role} {ref!r} does not resolve to any catalog entry", pid))
        return problems

    def to_snapshot(self, *, created_at: str | None, input_revisions: dict[str, Any] | None = None,
                    explanations: dict[str, str] | None = None,
                    problems: Iterable[dict[str, Any]] | None = None) -> CatalogSnapshot:
        from .model import compute_revision

        entries = self.sorted_entries()
        return CatalogSnapshot(
            dataset_revision=compute_revision(entries),
            created_at=created_at,
            input_revisions=dict(input_revisions or {}),
            counts=counts_for(entries),
            explanations=dict(explanations or {}),
            entries=entries,
            problems=[dict(p) for p in (problems or [])],
        )


__all__ = [
    "CatalogError",
    "DuplicateNativeIdError",
    "UnresolvedReferenceError",
    "GAP_FOR_CODE",
    "problem",
    "to_gap",
    "CatalogStore",
]
