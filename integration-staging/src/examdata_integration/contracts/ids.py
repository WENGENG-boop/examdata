"""Public-ID mapping registry: aliases, collisions, and native round-trip (plan 4.2).

The registry is the only place that turns a native identity into a public ID. It
enforces the plan's identity rules:

* deterministic IDs - the same native identity always yields the same public ID
  (rule 1), and the ID never depends on a database row number (rule 2);
* aliases are normalised before lookup (rule 4) and native question IDs and old
  integer IDs are kept as aliases (rule 5);
* collisions are detected by comparing canonical identities, never assumed
  impossible (rule 8) - a collision is recorded *and* raised;
* the exact native locator needed by the provider round-trips (rule 9);
* similarity is never an identity rule (rule 10): only exact canonical identity
  matches resolve, everything else must be registered explicitly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .canonical import (
    UNKNOWN,
    canonical_identity_string,
    normalize_alias,
    normalize_code,
    normalize_text,
    public_id as derive_public_id,
)
from .enums import EntityKind


class IdentityError(Exception):
    """Base class for identity-mapping failures."""


class IdentityCollisionError(IdentityError):
    """Two different canonical identities produced the same public ID."""


class AliasConflictError(IdentityError):
    """One normalised alias was claimed by two different public IDs."""


@dataclass(frozen=True)
class IdentityRecord:
    public_id: str
    kind: EntityKind
    canonical_identity: str
    identity_fields: dict[str, Any]
    native_locator: dict[str, Any]
    aliases: tuple[str, ...] = ()
    content_revision: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "public_id": self.public_id,
            "kind": self.kind.value,
            "canonical_identity": self.canonical_identity,
            "identity_fields": dict(self.identity_fields),
            "native_locator": dict(self.native_locator),
            "aliases": list(self.aliases),
            "content_revision": self.content_revision,
        }


@dataclass
class IdentityRegistry:
    """Deterministic native-identity -> public-ID mapping with alias lookup."""

    _by_public_id: dict[str, IdentityRecord] = field(default_factory=dict)
    _by_canonical: dict[str, str] = field(default_factory=dict)
    _by_alias: dict[str, str] = field(default_factory=dict)
    collision_events: list[dict[str, Any]] = field(default_factory=list)
    alias_events: list[dict[str, Any]] = field(default_factory=list)

    # -- registration -----------------------------------------------------------
    def register(
        self,
        kind: EntityKind,
        identity_fields: Mapping[str, Any],
        *,
        native_locator: Mapping[str, Any],
        aliases: Iterable[str] = (),
        content_revision: str | None = None,
    ) -> IdentityRecord:
        kind = EntityKind.coerce(kind)
        canonical = canonical_identity_string(kind, identity_fields)
        pid = derive_public_id(kind, identity_fields)

        known = self._by_canonical.get(canonical)
        if known is not None:
            self._bind_aliases(known, aliases)
            return self._by_public_id[known]

        existing = self._by_public_id.get(pid)
        if existing is not None and existing.canonical_identity != canonical:
            event = {
                "public_id": pid,
                "kind": kind.value,
                "kept_canonical_identity": existing.canonical_identity,
                "rejected_canonical_identity": canonical,
                "native_locator": dict(native_locator),
            }
            self.collision_events.append(event)
            raise IdentityCollisionError(
                f"public id {pid} already maps a different canonical identity "
                f"({kind.value}); refusing to overwrite"
            )

        # Bind aliases *before* committing the record, so a conflicting alias
        # raises without leaving a half-registered identity behind.
        self._bind_aliases(pid, aliases)

        alias_tuple = tuple(sorted({normalize_text(a) for a in aliases}))
        record = IdentityRecord(
            public_id=pid,
            kind=kind,
            canonical_identity=canonical,
            identity_fields=dict(identity_fields),
            native_locator=dict(native_locator),
            aliases=alias_tuple,
            content_revision=content_revision,
        )
        self._by_public_id[pid] = record
        self._by_canonical[canonical] = pid
        return record

    def _bind_aliases(self, pid: str, aliases: Iterable[str]) -> None:
        """Validate every alias first, then commit; a conflict raises and records."""
        keys = sorted({normalize_alias(a) for a in aliases})
        for key in keys:
            owner = self._by_alias.get(key)
            if owner is not None and owner != pid:
                event = {"alias": key, "normalised": key, "kept": owner, "rejected": pid}
                self.alias_events.append(event)
                raise AliasConflictError(f"alias {key!r} already resolves to {owner}")
        for key in keys:
            self._by_alias[key] = pid

    # -- lookup -----------------------------------------------------------------
    def resolve_alias(self, alias: str) -> str | None:
        return self._by_alias.get(normalize_alias(alias))

    def resolve(self, reference: str) -> str | None:
        """Resolve a public ID or an alias to a public ID."""
        if reference in self._by_public_id:
            return reference
        return self.resolve_alias(reference)

    def get(self, pid: str) -> IdentityRecord:
        return self._by_public_id[pid]

    def native_locator(self, pid: str) -> dict[str, Any]:
        """Round-trip helper: the exact native locator the provider needs."""
        return dict(self._by_public_id[pid].native_locator)

    def records(self) -> list[IdentityRecord]:
        return [self._by_public_id[k] for k in sorted(self._by_public_id)]

    def public_ids(self) -> list[str]:
        return sorted(self._by_public_id)

    # -- serialisation ----------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "identity-registry/1",
            "records": [r.to_dict() for r in self.records()],
            "collision_events": list(self.collision_events),
            "alias_events": list(self.alias_events),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "IdentityRegistry":
        reg = cls()
        for item in payload.get("records", []):
            reg.register(
                item["kind"],
                item["identity_fields"],
                native_locator=item["native_locator"],
                aliases=item.get("aliases", ()),
                content_revision=item.get("content_revision"),
            )
        return reg


def normalize_native_reference(value: str) -> str:
    """Normalise a native reference for alias matching (case-insensitive text)."""
    return normalize_alias(value)


def normalize_native_code(value: str) -> str:
    """Normalise a native code for display/comparison (upper-case)."""
    return normalize_code(value)


__all__ = [
    "UNKNOWN",
    "IdentityRecord",
    "IdentityRegistry",
    "IdentityError",
    "IdentityCollisionError",
    "AliasConflictError",
    "normalize_native_reference",
    "normalize_native_code",
]
