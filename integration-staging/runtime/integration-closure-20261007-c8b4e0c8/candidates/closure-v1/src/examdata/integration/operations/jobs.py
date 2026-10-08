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
free-text value and mapping key through :func:`sanitize_tree`, so absolute
paths and supplied secrets can never reach a response; every projection first
fixes the caller's secret iterable as one reusable tuple
(:func:`materialize_secrets`), so a one-shot iterable cannot be exhausted
half-way through a response.
"""
from __future__ import annotations

import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..runtime.paths import is_within
from ..runtime.redact import redact_text
from .budget import ScanBudget, resolve_scan_budget
from .checkpoints import (
    ByteBudget,
    CheckpointObservation,
    CheckpointReadError,
    CheckpointTooLargeError,
    ReadBudgetExhaustedError,
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

#: Scan bounds: discovery is bounded (directory entries), every attempted file
#: counts against the attempt budget whether or not it succeeds, retained skip
#: records are capped, and reads are bounded per file and cumulatively - every
#: allowance is computed at read time from one validated
#: :class:`~.budget.ScanBudget`. Each bound records its own exhaustion signal
#: in ``ScanResult.exhausted`` (``directory_entries``, ``retained_paths``,
#: ``depth``, ``unreadable_directory``, ``attempted_files``,
#: ``retained_results``, ``read_bytes``), so a huge or hostile tree can
#: neither exhaust memory nor make the read path unbounded. The constants
#: below are the default ``ScanBudget`` values, kept as importable names for
#: callers that still reference them.
MAX_SCAN_FILES = 256
MAX_CHECKPOINT_BYTES = 4 * 1024 * 1024
MAX_SCAN_ENTRIES = 4096
MAX_SKIPPED_RESULTS = 64
MAX_READ_BYTES = 32 * 1024 * 1024
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


def materialize_secrets(secrets: Iterable[str] | None) -> tuple[str, ...]:
    """Fix one caller-supplied secret iterable as a reusable tuple.

    Every public projection calls this exactly once, at its own boundary, so a
    one-shot iterable (for example a generator) cannot be exhausted half-way
    through a response and silently let later leaves escape redaction. A tuple
    argument is returned unchanged, so the common case costs no copy.
    """
    if secrets is None:
        return ()
    if isinstance(secrets, tuple):
        return secrets
    return tuple(secrets)


def sanitize_tree(value: Any, *, secrets: Iterable[str] = (),
                  limit: int = PUBLIC_TEXT_LIMIT) -> Any:
    """Recursively redact every string leaf *and mapping key* of a JSON value.

    Keys go through the same :func:`redact_text` as values, so a dynamic key
    can never carry a secret or an absolute path into a public projection.
    Distinct keys that redact to the same text are disambiguated with a
    deterministic ``#2``/``#3`` suffix (checked against every key emitted so
    far, literal keys included): nothing is dropped or overwritten.

    The caller's secrets are fixed first (:func:`materialize_secrets`), so the
    whole tree is redacted against one reusable tuple.
    """
    secrets = materialize_secrets(secrets)
    if isinstance(value, str):
        return redact_text(value, secrets=secrets, limit=limit)
    if isinstance(value, Mapping):
        projected: dict[str, Any] = {}
        for key, item in value.items():
            emitted = redact_text(str(key), secrets=secrets, limit=limit)
            if emitted in projected:
                suffix = 2
                while f"{emitted}#{suffix}" in projected:
                    suffix += 1
                emitted = f"{emitted}#{suffix}"
            projected[emitted] = sanitize_tree(item, secrets=secrets, limit=limit)
        return projected
    if isinstance(value, (list, tuple)):
        return [sanitize_tree(item, secrets=secrets, limit=limit) for item in value]
    return value


@dataclass
class ScanResult:
    """One bounded, read-only scan of a configured operations root.

    ``attempted`` counts every checkpoint file the scan *tried* to handle
    (skipped files included); ``entries_seen`` is how many directory entries
    discovery accepted; ``entries_consumed`` is how many raw ``os.scandir``
    pulls discovery spent (bounded probes included); ``retained_paths`` is the
    peak number of buffered paths; ``bytes_read`` is the cumulative payload
    bytes the read path actually consumed. ``exhausted`` names every budget
    that ran out, using the signals ``directory_entries``, ``retained_paths``,
    ``depth``, ``unreadable_directory``, ``attempted_files``,
    ``retained_results`` and ``read_bytes``; ``truncated`` is simply whether
    any budget ran out. ``budgets`` carries the effective
    :class:`~.budget.ScanBudget` values this scan ran with.
    """

    root: Path
    observations: list[CheckpointObservation] = field(default_factory=list)
    skipped: list[dict[str, str]] = field(default_factory=list)
    truncated: bool = False
    attempted: int = 0
    entries_seen: int = 0
    entries_consumed: int = 0
    bytes_read: int = 0
    retained_paths: int = 0
    exhausted: tuple[str, ...] = ()
    budgets: dict[str, int] = field(default_factory=dict)

    @property
    def scanned_files(self) -> int:
        return len(self.observations)


def _retain_skip(result: ScanResult, reasons: list[str], *, source: str,
                 reason: str, max_skipped: int) -> bool:
    """Record one skipped file within the retained-result budget.

    Returns ``False`` when the budget is exhausted (the scan must stop); the
    offending record is not retained, but the exhaustion is signalled.
    """
    if len(result.skipped) >= max_skipped:
        reasons.append("retained_results")
        result.truncated = True
        return False
    result.skipped.append({"source": source, "reason": reason})
    return True


def scan_checkpoint_root(root: str | Path, *, observed_at=None,
                         max_files: int | None = None,
                         max_bytes: int | None = None,
                         max_entries: int | None = None,
                         max_skipped: int | None = None,
                         max_read_bytes: int | None = None,
                         max_retained: int | None = None,
                         max_depth: int | None = None,
                         budget: ScanBudget | None = None) -> ScanResult:
    """Read every ``checkpoint.json`` under ``root`` once, within strict bounds.

    Every bound comes from one validated :class:`~.budget.ScanBudget`
    (``budget=``); the keyword arguments stay as per-call overrides where
    ``None`` means "keep the budget's value". The budgets and their
    exhaustion signals in ``ScanResult.exhausted``:

    * ``max_entries``/``max_retained``/``max_depth`` bound discovery itself -
      accepted entries, buffered paths and directory depth
      (``directory_entries``, ``retained_paths``, ``depth``; an unreadable
      directory reports ``unreadable_directory`` instead of raising);
    * ``max_files`` bounds *attempted* files - a skipped file still consumes
      the attempt budget (``attempted_files``);
    * ``max_skipped`` bounds the retained skip records (``retained_results``);
    * ``max_file_bytes`` bounds one file's read while ``max_total_bytes``
      bounds the cumulative payload read: the allowance is computed at read
      time from the shared byte budget and at most ``allowance + 1`` bytes
      are ever pulled (``read_bytes``).

    Files are visited in the walker's documented deterministic order. A file
    that grows past its allowance, cannot be read, is not a regular file, or
    resolves outside the root is recorded in ``skipped`` (``file_too_large``,
    ``unreadable``, ``not_a_regular_file``, ``outside_root``) and is never
    followed; nothing is ever opened for writing.
    """
    settings = resolve_scan_budget(
        budget, max_files=max_files, max_file_bytes=max_bytes,
        max_entries=max_entries, max_skipped=max_skipped,
        max_total_bytes=max_read_bytes, max_retained=max_retained,
        max_depth=max_depth)
    base = Path(root)
    result = ScanResult(root=base, budgets=settings.as_dict())
    reasons: list[str] = []
    walker = iter_checkpoint_paths(base, max_entries=settings.max_entries,
                                   max_retained=settings.max_retained,
                                   max_depth=settings.max_depth)
    byte_budget = ByteBudget(limit=settings.max_total_bytes)
    resolved_root = os.path.realpath(base)
    try:
        for path in walker:
            if result.attempted >= settings.max_files:
                reasons.append("attempted_files")
                break
            remaining = byte_budget.remaining
            if remaining is not None and remaining <= 0:
                reasons.append("read_bytes")
                break
            result.attempted += 1
            label = _relative_label(base, path)
            if not is_within(path, resolved_root):
                if not _retain_skip(result, reasons, source=label,
                                    reason="outside_root",
                                    max_skipped=settings.max_skipped):
                    break
                continue
            try:
                info = os.stat(path, follow_symlinks=False)
            except OSError:
                if not _retain_skip(result, reasons, source=label,
                                    reason="unreadable",
                                    max_skipped=settings.max_skipped):
                    break
                continue
            if not stat.S_ISREG(info.st_mode):
                if not _retain_skip(result, reasons, source=label,
                                    reason="not_a_regular_file",
                                    max_skipped=settings.max_skipped):
                    break
                continue
            try:
                observation = read_checkpoint_bounded(
                    path, source=label, observed_at=observed_at,
                    max_bytes=settings.max_file_bytes, budget=byte_budget)
            except CheckpointTooLargeError:
                if not _retain_skip(result, reasons, source=label,
                                    reason="file_too_large",
                                    max_skipped=settings.max_skipped):
                    break
                continue
            except ReadBudgetExhaustedError:
                reasons.append("read_bytes")
                break
            except CheckpointReadError:
                if not _retain_skip(result, reasons, source=label,
                                    reason="unreadable",
                                    max_skipped=settings.max_skipped):
                    break
                continue
            result.observations.append(observation)
    finally:
        walker.close()
    result.entries_seen = walker.entries_seen
    result.entries_consumed = walker.entries_consumed
    result.retained_paths = walker.peak_retained
    for reason in walker.reasons:
        if reason not in reasons:
            reasons.append(reason)
    result.bytes_read = byte_budget.consumed
    result.exhausted = tuple(reasons)
    result.truncated = bool(reasons)
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
        secrets = materialize_secrets(secrets)
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
        secrets = materialize_secrets(secrets)
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
        secrets = materialize_secrets(secrets)
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
    "MAX_READ_BYTES",
    "MAX_SCAN_ENTRIES",
    "MAX_SCAN_FILES",
    "MAX_SKIPPED_RESULTS",
    "PUBLIC_TEXT_LIMIT",
    "JobView",
    "JobsView",
    "ScanResult",
    "build_jobs",
    "derive_stage",
    "materialize_secrets",
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
