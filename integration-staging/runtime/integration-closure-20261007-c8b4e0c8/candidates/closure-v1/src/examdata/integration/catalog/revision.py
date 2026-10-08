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
* the compare-and-swap check and the pointer swap are serialized across
  processes by an ``O_CREAT|O_EXCL`` lock file next to the pointer: a publisher
  waits up to ``lock_timeout_seconds`` and then reports
  :class:`PublisherBusyError`, and a lock file older than ``LOCK_STALE_SECONDS``
  is reclaimed as a crashed holder's leftover;
* the pointer is re-read immediately after the swap, and a publisher reports
  success only while its own revision is still the published one; two
  publishers may write their immutable revision files concurrently, since only
  the pointer swap needs the lock;
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
import contextlib
import errno
import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Iterator

from ..contracts.canonical import canonical_identity_string, public_id as derive_public_id
from ..contracts.enums import EntityKind
from .model import CatalogSnapshot, compute_revision

POINTER_SCHEMA = "catalog-pointer/1"
CURSOR_SCHEMA = "examdata.cursor/1"
MAX_CURSOR_CHARS = 4096

#: Sentinel: "I did not read a current revision, so do not enforce compare-and-swap".
ANY_CURRENT = object()

#: Bounded retry around ``os.replace``.  On Windows a concurrent reader of the
#: destination makes the rename fail with a sharing violation ("PermissionError:
#: [WinError 5]"); the reader holds the file for microseconds, so a short
#: bounded retry turns the crash into a delay.  Worst case with these defaults:
#: about 1.4s of sleeping across ``REPLACE_RETRY_ATTEMPTS`` attempts.
REPLACE_RETRY_ATTEMPTS = 8
REPLACE_RETRY_BACKOFF_SECONDS = 0.05
REPLACE_RETRY_MAX_BACKOFF_SECONDS = 0.25
_REPLACE_RETRY_WINERRORS = frozenset({5, 32, 33})
_REPLACE_RETRY_ERRNOS = frozenset({errno.EACCES, errno.EPERM, errno.EBUSY, errno.EAGAIN})

#: Bounded retry around the pointer *read* (the same concurrent replace that
#: makes the write fail can make a reader's open fail with "Permission denied").
POINTER_READ_RETRY_ATTEMPTS = 8
POINTER_READ_RETRY_BACKOFF_SECONDS = 0.01
POINTER_READ_RETRY_MAX_BACKOFF_SECONDS = 0.1

#: Publication-lock tuning.  ``LOCK_STALE_SECONDS`` is an age-based heuristic:
#: a live holder keeps the lock only while it swaps the pointer (a few
#: milliseconds), so a lock file older than this is treated as a crashed
#: holder's leftover and reclaimed.  Process liveness is deliberately not
#: probed (no portable, safe check without extra dependencies).
LOCK_POLL_SECONDS = 0.01
LOCK_POLL_MAX_SECONDS = 0.1
LOCK_STALE_SECONDS = 120.0
DEFAULT_LOCK_TIMEOUT_SECONDS = 10.0


class RevisionError(Exception):
    """Base class for revision-publication failures."""


class PublicationRejected(RevisionError):
    """The candidate snapshot is not publishable; the current pointer is untouched."""


class StalePublisherError(RevisionError):
    """Compare-and-swap failed: the current revision changed under this builder."""


class PublisherBusyError(RevisionError):
    """Another publisher holds the publication lock past this one's deadline."""


class AtomicWriteError(RevisionError):
    """A temporary-file write or its atomic replacement failed after retries."""


class PointerUnreadableError(RevisionError):
    """The current pointer exists but could not be read (persistent IO failure)."""


class UnknownRevisionError(RevisionError):
    """A named revision is not retained."""


class InvalidCursorError(RevisionError):
    """The cursor is malformed, tampered with, or too long (HTTP 400)."""


class StaleCursorError(RevisionError):
    """The cursor's revision is no longer published (HTTP 409); restart the listing."""


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _discard(path: Path) -> None:
    """Delete a temporary file, tolerating a missing or still-locked path."""
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
    except OSError:  # pragma: no cover - a leftover temp file is not fatal here
        pass


def _replace_is_retryable(exc: OSError) -> bool:
    """True for the transient sharing/access failures a concurrent reader causes."""
    if isinstance(exc, FileNotFoundError):
        return False
    if isinstance(exc, PermissionError):
        return True
    if getattr(exc, "winerror", None) in _REPLACE_RETRY_WINERRORS:
        return True
    return exc.errno in _REPLACE_RETRY_ERRNOS


def _replace_with_retry(tmp: Path, path: Path) -> None:
    """``os.replace`` with a bounded retry loop for transient sharing failures."""
    delay = REPLACE_RETRY_BACKOFF_SECONDS
    for attempt in range(1, REPLACE_RETRY_ATTEMPTS + 1):
        try:
            os.replace(tmp, path)
        except OSError as exc:
            if attempt >= REPLACE_RETRY_ATTEMPTS or not _replace_is_retryable(exc):
                raise AtomicWriteError(
                    f"could not replace {path.name!r} after {attempt} attempt(s): {exc}"
                ) from exc
            time.sleep(delay)
            delay = min(delay * 2, REPLACE_RETRY_MAX_BACKOFF_SECONDS)
        else:
            return


def _atomic_write(path: Path, text: str) -> None:
    """Write `text` to `path` atomically (temp file + os.replace, same volume).

    The temporary file of *this call* never survives a failed write, so a
    contended publication leaves no ``.tmp-*`` orphan behind, and a persistent
    failure is reported as :class:`AtomicWriteError` rather than a raw OS error.
    """
    path = Path(path)
    tmp = path.with_name(f"{path.name}.tmp-{uuid.uuid4().hex}")
    try:
        tmp.write_text(text, encoding="utf-8", newline="\n")
    except OSError as exc:
        _discard(tmp)
        raise AtomicWriteError(
            f"could not write the temporary file for {path.name!r}: {exc}") from exc
    try:
        _replace_with_retry(tmp, path)
    except BaseException:
        _discard(tmp)
        raise


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass
class RevisionPublisher:
    """Publishes immutable catalog revisions behind an atomic current pointer."""

    root: Path
    pointer_name: str = "current.json"
    revisions_dirname: str = "revisions"
    lock_timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        timeout = self.lock_timeout_seconds
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout < 0:
            raise ValueError(
                f"lock_timeout_seconds must be a non-negative number of seconds, not {timeout!r}")
        self.lock_timeout_seconds = float(timeout)
        (self.root / self.revisions_dirname).mkdir(parents=True, exist_ok=True)

    # -- locations --------------------------------------------------------------
    @property
    def pointer_path(self) -> Path:
        return self.root / self.pointer_name

    @property
    def lock_path(self) -> Path:
        return self.pointer_path.with_name(self.pointer_path.name + ".lock")

    @property
    def revisions_dir(self) -> Path:
        return self.root / self.revisions_dirname

    def revision_path(self, dataset_revision: str) -> Path:
        return self.revisions_dir / f"{dataset_revision}.json"

    # -- read -------------------------------------------------------------------
    def current(self) -> dict[str, Any] | None:
        """Read the current pointer; retry transient sharing failures.

        A concurrent ``os.replace`` can make the reader's open fail with a
        Windows sharing violation; that reader holds the file for microseconds,
        so a short bounded retry is enough.  A persistent failure is reported as
        :class:`PointerUnreadableError` instead of leaking a raw OS error.
        """
        if not self.pointer_path.is_file():
            return None
        last: OSError | None = None
        delay = POINTER_READ_RETRY_BACKOFF_SECONDS
        for attempt in range(1, POINTER_READ_RETRY_ATTEMPTS + 1):
            try:
                return json.loads(self.pointer_path.read_text(encoding="utf-8"))
            except FileNotFoundError:
                return None
            except OSError as exc:
                last = exc
                if attempt >= POINTER_READ_RETRY_ATTEMPTS:
                    break
                time.sleep(delay)
                delay = min(delay * 2, POINTER_READ_RETRY_MAX_BACKOFF_SECONDS)
        raise PointerUnreadableError(
            f"the current pointer could not be read after "
            f"{POINTER_READ_RETRY_ATTEMPTS} attempt(s): {last}") from last

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

    # -- publication lock and pointer swap ---------------------------------------
    @contextlib.contextmanager
    def _publication_lock(self) -> Iterator[None]:
        """Serialize the compare-and-swap check and the pointer swap across processes.

        The lock is a file created with ``O_CREAT|O_EXCL`` next to the pointer; a
        holder that dies without cleaning up is reclaimed once its lock file is
        older than ``LOCK_STALE_SECONDS``.
        """
        lock_path = self.lock_path
        deadline = time.monotonic() + float(self.lock_timeout_seconds)
        delay = LOCK_POLL_SECONDS
        while True:
            try:
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                self._reclaim_stale_lock(lock_path)
                if time.monotonic() >= deadline:
                    raise PublisherBusyError(
                        f"another publisher holds {lock_path.name!r}; gave up after "
                        f"{self.lock_timeout_seconds}s - retry the publication")
                time.sleep(delay)
                delay = min(delay * 2, LOCK_POLL_MAX_SECONDS)
            except OSError as exc:
                raise PublisherBusyError(
                    f"could not acquire the publication lock {lock_path.name!r}: {exc}") from exc
            else:
                break
        try:
            os.write(fd, f"{os.getpid()} {time.time():.3f}\n".encode("ascii"))
        except OSError:  # pragma: no cover - the lock content is informational only
            pass
        finally:
            os.close(fd)
        try:
            yield
        finally:
            _discard(lock_path)

    def _reclaim_stale_lock(self, lock_path: Path) -> None:
        """Drop a lock file left behind by a crashed holder (pure age heuristic)."""
        try:
            age = time.time() - lock_path.stat().st_mtime
        except OSError:
            return
        if age > LOCK_STALE_SECONDS:
            _discard(lock_path)

    def _swap_pointer(self, pointer: dict[str, Any], observed_revision: str | None) -> None:
        """Install `pointer` atomically and confirm it actually landed.

        Must be called while :meth:`_publication_lock` is held.  A failed replace
        is turned into a verdict: if the pointer moved underneath us the player
        that lost is stale, otherwise the write merely contended.
        """
        text = json.dumps(pointer, ensure_ascii=False, indent=2) + "\n"
        try:
            _atomic_write(self.pointer_path, text)
        except AtomicWriteError as exc:
            latest = self.current_revision()
            if latest != observed_revision:
                raise StalePublisherError(
                    f"current revision is {latest!r}, but this publisher expected "
                    f"{observed_revision!r}; refresh and rebuild") from exc
            raise PublicationRejected("pointer write contended; retry") from exc
        landed = self.current_revision()
        if landed != pointer["dataset_revision"]:
            raise RevisionError(
                f"the current pointer names {landed!r} after an exclusive swap, not "
                f"{pointer['dataset_revision']!r}; the store is inconsistent")

    # -- publish ----------------------------------------------------------------
    def publish(self, snapshot: CatalogSnapshot | None, *,
                expected_current: Any = ANY_CURRENT,
                now: str | None = None) -> dict[str, Any]:
        """Validate then publish `snapshot`; on any failure the pointer is unchanged.

        The compare-and-swap verdict is re-checked while holding the publication
        lock, so two builders that read the same current cannot both succeed:
        the slower one gets :class:`StalePublisherError` instead of silently
        overwriting the faster one's revision.
        """
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

        # Cheap pre-check outside the lock: identical verdicts for the common
        # failure path (the authoritative check runs again under the lock).
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
            try:
                _atomic_write(path, body + "\n")
            except AtomicWriteError as exc:
                # A concurrent publisher may have written the identical revision
                # meanwhile; that is fine, a different body is not.
                if not path.is_file() or path.read_text(encoding="utf-8").strip() != body:
                    raise PublicationRejected(
                        f"revision {revision!r} could not be written; "
                        f"the pointer is unchanged") from exc

        with self._publication_lock():
            # Authoritative compare-and-swap: re-read the pointer under the lock.
            current = self.current()
            current_revision = current.get("dataset_revision") if current else None
            if expected_current is not ANY_CURRENT and expected_current != current_revision:
                raise StalePublisherError(
                    f"current revision is {current_revision!r}, but this builder expected "
                    f"{expected_current!r}; refresh and rebuild")
            if current_revision == revision:
                return current
            pointer = {
                "schema": POINTER_SCHEMA,
                "dataset_revision": revision,
                "published_at": now or _now(),
                "previous": current_revision,
            }
            self._swap_pointer(pointer, current_revision)
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
    def _rollback_pointer(self, now: str | None) -> tuple[dict[str, Any], str | None]:
        """Build the pointer that restores the retained previous revision."""
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
        return pointer, current.get("dataset_revision")

    def rollback(self, *, now: str | None = None) -> dict[str, Any]:
        """Point current back at the retained previous revision (atomically)."""
        # Fast-path validation outside the lock keeps the refusal messages intact.
        self._rollback_pointer(now)
        with self._publication_lock():
            pointer, observed = self._rollback_pointer(now)
            self._swap_pointer(pointer, observed)
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
    "PublisherBusyError",
    "AtomicWriteError",
    "PointerUnreadableError",
    "UnknownRevisionError",
    "InvalidCursorError",
    "StaleCursorError",
    "RevisionPublisher",
    "make_cursor",
    "parse_cursor",
    "resolve_cursor",
]
