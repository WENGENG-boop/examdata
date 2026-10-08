"""Immutable revision publication, an atomic current pointer, and cursors (plan 7.3, 5.7).

``RevisionPublisher`` implements the plan's publication transaction without ever
needing symbolic-link privileges:

* each revision is written once to ``revisions/<dataset_revision>.json`` through a
  temporary file and an atomic ``os.replace``; an existing revision file is never
  rewritten (a different body for the same revision is refused);
* the current revision is a tiny versioned ``current.json`` pointer, replaced
  atomically;
* publication is compare-and-swap: a builder that read an older current and then
  tries to publish is refused, so a stale builder cannot overwrite a newer
  revision;
* the previous revision is kept, so :meth:`RevisionPublisher.rollback` can restore
  it atomically;
* a failed validation leaves ``current.json`` untouched.

Cursors bind query, sort, revision and last key, carry an integrity tag, are
length-bounded, and are rejected as *invalid* (400) when tampered with or as
*stale* (409) when their revision is no longer published - with restart
instructions.

Stdlib only. Nothing here reads the original project, the network, or a database.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from ..contracts.canonical import canonical_identity_string, public_id as derive_public_id
from ..contracts.enums import EntityKind
from .model import CatalogSnapshot, compute_revision

POINTER_SCHEMA = "catalog-pointer/1"
CURSOR_SCHEMA = "examdata.cursor/1"
MAX_CURSOR_CHARS = 4096

#: Sentinel: "I did not read a current revision, so do not enforce compare-and-swap".
ANY_CURRENT = object()


class RevisionError(Exception):
    """Base class for revision-publication failures."""


class PublicationRejected(RevisionError):
    """The candidate snapshot is not publishable; the current pointer is untouched."""


class StalePublisherError(RevisionError):
    """Compare-and-swap failed: the current revision changed under this builder."""


class UnknownRevisionError(RevisionError):
    """A named revision is not retained."""


class InvalidCursorError(RevisionError):
    """The cursor is malformed, tampered with, or too long (HTTP 400)."""


class StaleCursorError(RevisionError):
    """The cursor's revision is no longer published (HTTP 409); restart the listing."""


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _atomic_write(path: Path, text: str) -> None:
    """Write `text` to `path` atomically (temp file + os.replace, same volume)."""
    tmp = path.with_name(f"{path.name}.tmp-{uuid.uuid4().hex}")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass
class RevisionPublisher:
    """Publishes immutable catalog revisions behind an atomic current pointer."""

    root: Path
    pointer_name: str = "current.json"
    revisions_dirname: str = "revisions"

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        (self.root / self.revisions_dirname).mkdir(parents=True, exist_ok=True)

    # -- locations --------------------------------------------------------------
    @property
    def pointer_path(self) -> Path:
        return self.root / self.pointer_name

    @property
    def revisions_dir(self) -> Path:
        return self.root / self.revisions_dirname

    def revision_path(self, dataset_revision: str) -> Path:
        return self.revisions_dir / f"{dataset_revision}.json"

    # -- read -------------------------------------------------------------------
    def current(self) -> dict[str, Any] | None:
        if not self.pointer_path.is_file():
            return None
        return json.loads(self.pointer_path.read_text(encoding="utf-8"))

    def current_revision(self) -> str | None:
        cur = self.current()
        return cur.get("dataset_revision") if cur else None

    def available_revisions(self) -> list[str]:
        return sorted(p.stem for p in self.revisions_dir.glob("*.json"))

    def retain(self, dataset_revision: str) -> bool:
        return self.revision_path(dataset_revision).is_file()

    def load_revision(self, dataset_revision: str) -> CatalogSnapshot:
        path = self.revision_path(dataset_revision)
        if not path.is_file():
            raise UnknownRevisionError(f"revision {dataset_revision!r} is not retained")
        return CatalogSnapshot.from_dict(json.loads(path.read_text(encoding="utf-8")))

    # -- publish ----------------------------------------------------------------
    def publish(self, snapshot: CatalogSnapshot | None, *,
                expected_current: Any = ANY_CURRENT,
                now: str | None = None) -> dict[str, Any]:
        """Validate then publish `snapshot`; on any failure the pointer is unchanged."""
        if snapshot is None:
            raise PublicationRejected("no snapshot to publish: the build did not pass validation")
        revision = snapshot.dataset_revision
        if not revision:
            raise PublicationRejected("snapshot has no dataset_revision")
        if revision != compute_revision(snapshot.entries):
            raise PublicationRejected(
                f"snapshot revision {revision!r} does not match its entries; refusing to publish "
                f"a non-reproducible revision")
        self._validate_identities(snapshot)

        current = self.current()
        current_revision = current.get("dataset_revision") if current else None
        if expected_current is not ANY_CURRENT and expected_current != current_revision:
            raise StalePublisherError(
                f"current revision is {current_revision!r}, but this builder expected "
                f"{expected_current!r}; refresh and rebuild")
        if current_revision == revision:
            return current

        body = _canonical_json(snapshot.to_dict())
        path = self.revision_path(revision)
        if path.is_file():
            if path.read_text(encoding="utf-8").strip() != body:
                raise PublicationRejected(
                    f"revision {revision!r} already exists with different content")
        else:
            _atomic_write(path, body + "\n")

        pointer = {
            "schema": POINTER_SCHEMA,
            "dataset_revision": revision,
            "published_at": now or _now(),
            "previous": current_revision,
        }
        _atomic_write(self.pointer_path, json.dumps(pointer, ensure_ascii=False, indent=2) + "\n")
        return pointer

    def _validate_identities(self, snapshot: CatalogSnapshot) -> None:
        """Round-trip every entry's identity and locator; reject on any mismatch."""
        seen: set[str] = set()
        for entry in snapshot.entries:
            try:
                kind = EntityKind.coerce(entry.kind)
                canonical_identity_string(kind, entry.identity_fields)
                derived = derive_public_id(kind, entry.identity_fields)
            except (ValueError, KeyError, TypeError) as exc:
                raise PublicationRejected(f"{entry.public_id}: invalid identity ({exc})") from exc
            if derived != entry.public_id:
                raise PublicationRejected(
                    f"{entry.public_id}: public id does not round-trip its identity "
                    f"(derived {derived})")
            if entry.public_id in seen:
                raise PublicationRejected(f"{entry.public_id}: duplicated entry")
            seen.add(entry.public_id)
            if not entry.native_locator:
                raise PublicationRejected(f"{entry.public_id}: empty native locator")

    # -- rollback ---------------------------------------------------------------
    def rollback(self, *, now: str | None = None) -> dict[str, Any]:
        """Point current back at the retained previous revision (atomically)."""
        current = self.current()
        if current is None:
            raise RevisionError("no current revision to roll back")
        previous = current.get("previous")
        if not previous:
            raise RevisionError("no previous revision recorded; nothing to roll back to")
        if not self.retain(previous):
            raise UnknownRevisionError(f"previous revision {previous!r} is not retained")
        pointer = {
            "schema": POINTER_SCHEMA,
            "dataset_revision": previous,
            "published_at": now or _now(),
            "previous": current.get("dataset_revision"),
        }
        _atomic_write(self.pointer_path, json.dumps(pointer, ensure_ascii=False, indent=2) + "\n")
        return pointer


# --------------------------------------------------------------------------- #
# cursors (plan 5.7): bind query, sort, revision and last key; validate integrity
# --------------------------------------------------------------------------- #
def make_cursor(*, dataset_revision: str, query: dict[str, Any] | None = None,
                sort: str | None = None, last_key: Any = None,
                limit: int | None = None) -> str:
    """Build a length-bounded, integrity-tagged cursor bound to a revision."""
    payload = {
        "schema": CURSOR_SCHEMA,
        "dataset_revision": dataset_revision,
        "query": dict(query or {}),
        "sort": sort,
        "last_key": last_key,
        "limit": limit,
    }
    raw = _canonical_json(payload).encode("utf-8")
    body = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    tag = hashlib.sha256(raw).hexdigest()[:16]
    cursor = f"{body}.{tag}"
    if len(cursor) > MAX_CURSOR_CHARS:
        raise InvalidCursorError("cursor payload exceeds the maximum length")
    return cursor


def parse_cursor(cursor: str) -> dict[str, Any]:
    """Decode and integrity-check a cursor; raise :class:`InvalidCursorError` (400)."""
    if not isinstance(cursor, str) or not cursor:
        raise InvalidCursorError("cursor is missing or empty")
    if len(cursor) > MAX_CURSOR_CHARS:
        raise InvalidCursorError("cursor exceeds the maximum length")
    body, sep, tag = cursor.rpartition(".")
    if not sep:
        raise InvalidCursorError("cursor has no integrity tag")
    padded = body + "=" * (-len(body) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    except Exception as exc:  # noqa: BLE001 - any decode failure is an invalid cursor
        raise InvalidCursorError("cursor payload is not valid base64url") from exc
    if hashlib.sha256(raw).hexdigest()[:16] != tag:
        raise InvalidCursorError("cursor integrity tag does not match")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise InvalidCursorError("cursor payload is not valid JSON") from exc
    if not isinstance(payload, dict) or payload.get("schema") != CURSOR_SCHEMA:
        raise InvalidCursorError("unknown cursor schema")
    if not payload.get("dataset_revision"):
        raise InvalidCursorError("cursor is not bound to a dataset revision")
    return payload


def resolve_cursor(cursor: str, available_revisions: Iterable[str]) -> dict[str, Any]:
    """Validate a cursor and confirm its revision is still published (else 409)."""
    payload = parse_cursor(cursor)
    revision = payload["dataset_revision"]
    if revision not in set(available_revisions):
        raise StaleCursorError(
            f"the revision {revision!r} bound to this cursor is no longer published; "
            f"restart the listing from the first page")
    return payload


__all__ = [
    "POINTER_SCHEMA",
    "CURSOR_SCHEMA",
    "MAX_CURSOR_CHARS",
    "ANY_CURRENT",
    "RevisionError",
    "PublicationRejected",
    "StalePublisherError",
    "UnknownRevisionError",
    "InvalidCursorError",
    "StaleCursorError",
    "RevisionPublisher",
    "make_cursor",
    "parse_cursor",
    "resolve_cursor",
]
