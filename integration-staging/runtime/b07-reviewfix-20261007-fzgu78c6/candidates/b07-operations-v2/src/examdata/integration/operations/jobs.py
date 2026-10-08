"""Read-only job views and bounded checkpoint scanning (plan 10.1, packet B07).

A job here is *derived*, never stored: one view per observed checkpoint scope,
built on top of the A13 coverage rows. The plan 10.1 job vocabulary
(``queued -> running -> succeeded / partial / stopped_requires_resume / ...``)
is used wherever the native fields support it, and nowhere else:

* a stop whose native file sets ``needs_user_resume`` to true becomes
  ``stopped_requires_resume``; a stop whose native file explicitly does *not*
  require a user resume stays ``stopped`` - it is never relabelled as a resume
  requirement it denies, and never upgraded to a success;
* an all-sources-blocked run stays ``blocked`` - the native file declares no
  terminal failure, so none is invented;
* the native stop reason, stop detail, resume policy and counters are carried
  verbatim (only the public projection applies redaction).

Nothing in this module writes, resumes, starts, cancels or enqueues anything:
the only file access is a bounded, read-only scan for files named
``checkpoint.json``. Public projections drop the raw payload and run every
free-text value through :func:`sanitize_tree`, so absolute paths and supplied
secrets can never reach a response.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..runtime.redact import redact_text
from .checkpoints import (
    CheckpointObservation,
    CheckpointReadError,
    CheckpointTooLargeError,
    iter_checkpoint_paths,
    read_checkpoint,
    read_checkpoint_bounded,
)
from .coverage import CoverageRow, CoverageView

#: Stage vocabulary for the derived views (plan 10.1, extended with the two
#: native-faithful words ``stopped`` and ``blocked`` documented above).
STAGE_QUEUED = "queued"
STAGE_RUNNING = "running"
STAGE_SUCCEEDED = "succeeded"
STAGE_PARTIAL = "partial"
STAGE_STOPPED_REQUIRES_RESUME = "stopped_requires_resume"
STAGE_STOPPED = "stopped"
STAGE_BLOCKED = "blocked"
STAGE_UNKNOWN = "unknown"

#: Scan bounds. The walk is deterministic (sorted) and every budget has its
#: own exhaustion signal, recorded in ``ScanResult.exhausted`` together with
#: ``truncated=True``: ``max_entries`` bounds discovered directory entries
#: (``directory_entries``) before any listing is materialised, ``max_files``
#: bounds attempted checkpoint files - files skipped as oversized or
#: unreadable still count (``attempted_files``) - ``max_skipped`` bounds the
#: retained skip records (``retained_results``), ``max_bytes`` bounds one
#: checkpoint file and ``max_read_bytes`` bounds the cumulative bytes read
#: per scan (``read_bytes``).
MAX_SCAN_FILES = 256
MAX_SCAN_ENTRIES = 4096
MAX_SCAN_SKIPPED = 64
MAX_CHECKPOINT_BYTES = 4 * 1024 * 1024
MAX_SCAN_READ_BYTES = 32 * 1024 * 1024
#: Free text in public projections is bounded to this many characters.
PUBLIC_TEXT_LIMIT = 500


def source_label(relative_path: str) -> str:
    """A path-free, unique source label for one checkpoint file.

    ``cie-location-batch/checkpoint.json`` becomes
    ``cie-location-batch:checkpoint.json``: still unique and readable, but it
    contains no slash or backslash, so the public-surface redactor can never
    mistake it for a filesystem path.
    """
    return relative_path.replace("\\", "/").lstrip("/").replace("/", ":")


def sanitize_tree(value: Any, *, secrets: Iterable[str] = (),
                  limit: int = PUBLIC_TEXT_LIMIT) -> Any:
    """Recursively redact every string leaf *and dynamic mapping key*.

    Keys are projected, not trusted: each mapping key is rendered through
    :func:`redact_text` exactly like a value, and when two projected keys
    collide, the later one gets a deterministic ``#2`` (then ``#3``, ...)
    suffix so a colliding key can never drop its entry. Fixed schema keys
    carry no secret and no path-like token, so they survive unchanged.
    """
    if isinstance(value, str):
        return redact_text(value, secrets=secrets, limit=limit)
    if isinstance(value, Mapping):
        projected: dict[str, Any] = {}
        for key, item in value.items():
            candidate = redact_text(str(key), secrets=secrets, limit=limit)
            unique, index = candidate, 2
            while unique in projected:
                unique = f"{candidate}#{index}"
                index += 1
            projected[unique] = sanitize_tree(item, secrets=secrets, limit=limit)
        return projected
    if isinstance(value, (list, tuple)):
        return [sanitize_tree(item, secrets=secrets, limit=limit) for item in value]
    return value


@dataclass
class ScanResult:
    """One bounded, read-only scan of a configured operations root.

    The counters report the scan's real work: ``attempted`` files (skipped
    ones included), ``entries_seen`` directory entries the walker discovered,
    ``bytes_read`` checkpoint bytes loaded, and ``exhausted`` naming every
    budget that ran out (empty when nothing was truncated).
    """

    root: Path
    observations: list[CheckpointObservation] = field(default_factory=list)
    skipped: list[dict[str, str]] = field(default_factory=list)
    truncated: bool = False
    attempted: int = 0
    entries_seen: int = 0
    bytes_read: int = 0
    exhausted: tuple[str, ...] = ()

    @property
    def scanned_files(self) -> int:
        return len(self.observations)


def scan_checkpoint_root(root: str | Path, *, observed_at=None,
                         max_files: int = MAX_SCAN_FILES,
                         max_bytes: int = MAX_CHECKPOINT_BYTES,
                         max_entries: int = MAX_SCAN_ENTRIES,
                         max_skipped: int = MAX_SCAN_SKIPPED,
                         max_read_bytes: int = MAX_SCAN_READ_BYTES) -> ScanResult:
    """Read every ``checkpoint.json`` under ``root`` once, within strict bounds.

    Every budget bounds *work*, not only success:

    * ``max_entries`` caps the directory entries the walker may discover
      (``directory_entries``), so an unbounded tree is never materialised;
    * ``max_files`` counts every *attempted* checkpoint file - skipped
      (oversized, unreadable) files consume the budget like read ones
      (``attempted_files``);
    * ``max_skipped`` caps the retained skip records (``retained_results``);
    * ``max_bytes`` caps one checkpoint file and ``max_read_bytes`` caps the
      cumulative bytes this scan loads (``read_bytes``).

    An exhausted budget sets ``truncated=True`` and its name is recorded in
    ``exhausted``. Files are visited in the walker's deterministic full-path
    lexicographic order and are never opened for writing.
    """
    base = Path(root)
    result = ScanResult(root=base)
    exhausted: list[str] = []

    def stop(name: str) -> None:
        exhausted.append(name)
        result.truncated = True

    def retain_skip(source: str, reason: str) -> bool:
        if len(result.skipped) >= max_skipped:
            stop("retained_results")
            return False
        result.skipped.append({"source": source, "reason": reason})
        return True

    walk = iter_checkpoint_paths(base, max_entries=max_entries)
    for path in walk:
        if result.attempted >= max_files:
            stop("attempted_files")
            break
        label = _relative_label(base, path)
        try:
            size = path.stat().st_size
        except OSError:
            result.attempted += 1
            if not retain_skip(label, "unreadable"):
                break
            continue
        if size > max_bytes:
            result.attempted += 1
            if not retain_skip(label, "file_too_large"):
                break
            continue
        if result.bytes_read + size > max_read_bytes:
            stop("read_bytes")
            break
        result.attempted += 1
        try:
            observation = read_checkpoint_bounded(
                path, source=label, observed_at=observed_at, max_bytes=max_bytes)
        except CheckpointTooLargeError:
            if not retain_skip(label, "file_too_large"):
                break
            continue
        except CheckpointReadError:
            if not retain_skip(label, "unreadable"):
                break
            continue
        result.bytes_read += observation.size_bytes
        result.observations.append(observation)
    if walk.exhausted is not None:
        stop("directory_entries")
    result.entries_seen = walk.entries_seen
    result.exhausted = tuple(exhausted)
    return result


def _relative_label(base: Path, path: Path) -> str:
    try:
        rel = path.relative_to(base).as_posix()
    except ValueError:  # pragma: no cover - defensive only
        rel = path.name
    return source_label(rel)


def derive_stage(row: CoverageRow,
                 observation: CheckpointObservation | None = None) -> str:
    """Map one native-derived coverage row into the job stage vocabulary."""
    state = row.state
    if state in ("complete", "ok"):
        return STAGE_SUCCEEDED
    if state == "in_progress":
        document = observation.document if observation is not None else {}
        if document.get("stage") == "queued" or document.get("loop_stage") == "queued":
            return STAGE_QUEUED
        return STAGE_RUNNING
    if state == "partial_failure":
        return STAGE_PARTIAL
    if state == "stopped":
        needs_resume = (row.resume or {}).get("needs_user_resume")
        return (STAGE_STOPPED_REQUIRES_RESUME if needs_resume is True
                else STAGE_STOPPED)
    if state == "blocked":
        return STAGE_BLOCKED
    return STAGE_UNKNOWN


@dataclass
class JobView:
    """One checkpoint observation as a read-only job view."""

    system: str
    scope_id: str
    scope_kind: str
    stage: str
    freshness: str
    counters: dict[str, Any] | None
    sources: dict[str, Any] | None
    stop: dict[str, Any] | None
    resume: dict[str, Any] | None
    source: str
    observed_at: str
    native_updated_at: str | None
    payload_sha256: str
    problems: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return f"job:{self.system}:{self.scope_id}"

    @property
    def resume_required(self) -> bool:
        """True only when the native file itself requires a user resume."""
        return bool((self.resume or {}).get("needs_user_resume") is True)

    @property
    def stop_reason(self) -> str | None:
        reason = (self.stop or {}).get("reason")
        return reason if isinstance(reason, str) else None

    def to_public(self, *, secrets: Iterable[str] = ()) -> dict[str, Any]:
        """The sanitized public projection (no raw payload, no paths, no secrets).

        The projection keeps the ``job-status/1`` contract fields
        (``public_id``, ``scope``, ``input_revision``, ``stage``, ``counters``,
        ``stop_reason``, ``resume_required``, ``output_refs``,
        ``evidence_refs``) plus the read-only observation metadata.
        """
        problems = list(self.problems)
        if self.resume_required and not self.stop_reason:
            problems.append("resume_required_without_stop_reason")
        return {
            "public_id": self.id,
            "scope": f"{self.system}:{self.scope_kind}",
            "input_revision": None,
            "stage": self.stage,
            "counters": sanitize_tree(self.counters, secrets=secrets),
            "stop_reason": (redact_text(self.stop_reason, secrets=secrets)
                            if self.stop_reason is not None else None),
            "resume_required": self.resume_required,
            "output_refs": [],
            "evidence_refs": [self.source],
            "freshness": self.freshness,
            "system": self.system,
            "scope_id": self.scope_id,
            "scope_kind": self.scope_kind,
            "source": self.source,
            "observed_at": self.observed_at,
            "native_updated_at": self.native_updated_at,
            "payload_sha256": self.payload_sha256,
            "stop": sanitize_tree(self.stop, secrets=secrets),
            "resume": sanitize_tree(self.resume, secrets=secrets),
            "sources": sanitize_tree(self.sources, secrets=secrets),
            "problems": problems,
        }

    def brief(self, *, secrets: Iterable[str] = ()) -> dict[str, Any]:
        """The one-line summary used in list-shaped blocks."""
        return {
            "public_id": self.id,
            "system": self.system,
            "scope_id": self.scope_id,
            "scope_kind": self.scope_kind,
            "stage": self.stage,
            "freshness": self.freshness,
            "resume_required": self.resume_required,
            "stop_reason": (redact_text(self.stop_reason, secrets=secrets)
                            if self.stop_reason is not None else None),
            "native_updated_at": self.native_updated_at,
            "source": self.source,
        }

    def to_dict(self) -> dict[str, Any]:
        """The raw (unsanitized) view; the payload stays out of it."""
        return {
            "public_id": self.id,
            "system": self.system,
            "scope_id": self.scope_id,
            "scope_kind": self.scope_kind,
            "stage": self.stage,
            "freshness": self.freshness,
            "counters": self.counters,
            "sources": self.sources,
            "stop": self.stop,
            "resume": self.resume,
            "source": self.source,
            "observed_at": self.observed_at,
            "native_updated_at": self.native_updated_at,
            "payload_sha256": self.payload_sha256,
            "problems": list(self.problems),
        }


@dataclass
class JobsView:
    """Every observation as a job row plus current-id lookup."""

    rows: list[JobView] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)

    @property
    def current(self) -> list[JobView]:
        return [row for row in self.rows if row.freshness == "current"]

    def by_id(self) -> dict[str, JobView]:
        """Current rows keyed by job id; a conflict-only scope resolves to none."""
        return {row.id: row for row in self.current}

    def for_scope(self, system: str, scope_id: str) -> list[JobView]:
        return [row for row in self.rows
                if row.system == system and row.scope_id == scope_id]

    def superseded_for(self, system: str, scope_id: str) -> list[JobView]:
        return [row for row in self.for_scope(system, scope_id)
                if row.freshness == "superseded"]

    def conflicts_for(self, system: str, scope_id: str) -> list[dict[str, Any]]:
        return [dict(conflict) for conflict in self.conflicts
                if conflict.get("system") == system
                and conflict.get("scope_id") == scope_id]

    def briefs(self, *, secrets: Iterable[str] = ()) -> list[dict[str, Any]]:
        return [row.brief(secrets=secrets) for row in self.rows]


def build_jobs(view: CoverageView,
               observations: Iterable[CheckpointObservation]) -> JobsView:
    """Derive the job rows from the A13 coverage rows, one row per observation."""
    by_sha: dict[str, CheckpointObservation] = {}
    for observation in observations:
        by_sha.setdefault(observation.payload_sha256, observation)
    jobs = JobsView(conflicts=[dict(conflict) for conflict in view.conflicts])
    for row in view.rows:
        observation = by_sha.get(row.payload_sha256)
        jobs.rows.append(JobView(
            system=row.system,
            scope_id=row.scope_id,
            scope_kind=row.scope_kind,
            stage=derive_stage(row, observation),
            freshness=row.freshness,
            counters=row.counters,
            sources=row.sources,
            stop=row.stop,
            resume=row.resume,
            source=row.source,
            observed_at=row.observed_at,
            native_updated_at=row.native_updated_at,
            payload_sha256=row.payload_sha256,
            problems=list(row.problems),
        ))
    return jobs


__all__ = [
    "MAX_CHECKPOINT_BYTES",
    "MAX_SCAN_ENTRIES",
    "MAX_SCAN_FILES",
    "MAX_SCAN_READ_BYTES",
    "MAX_SCAN_SKIPPED",
    "PUBLIC_TEXT_LIMIT",
    "JobView",
    "JobsView",
    "ScanResult",
    "build_jobs",
    "derive_stage",
    "sanitize_tree",
    "scan_checkpoint_root",
    "source_label",
    "STAGE_BLOCKED",
    "STAGE_PARTIAL",
    "STAGE_QUEUED",
    "STAGE_RUNNING",
    "STAGE_STOPPED",
    "STAGE_STOPPED_REQUIRES_RESUME",
    "STAGE_SUCCEEDED",
    "STAGE_UNKNOWN",
]
