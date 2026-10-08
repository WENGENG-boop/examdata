"""Read-only checkpoint adapters (plan 3.5, packet A13).

Two native checkpoint formats exist in the original project and both keep their
own shape: the CIE batch runner's flat ``checkpoint.json`` (stage, loop stages,
totals, stop detail, resume policy) and the IELTS run checkpoints that declare
``schema_version: "ielts-run-checkpoint/1"`` (fetcher counters and per-source
health). Adapters here only ever *read*: the file bytes are hashed and parsed,
the parsed document is preserved verbatim, and typed views keep every native
value - including ``None`` for values the native file does not provide.

Unknown formats and malformed JSON produce a typed observation with explicit
``problems``, never an exception from a scan and never a value invented from a
plausible default. Every observation records the source label plus two times:
the file's own ``updated_at`` (native) and the read time (``observed_at``), so
downstream views can tell a stale snapshot from a fresh one without guessing.

Nothing here writes, reads the network, a database, a service, or any
timetable/active-material data.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable


class _StrEnum(str, Enum):
    """str-backed enum so values serialise as plain strings."""

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return self.value


class CheckpointFormat(_StrEnum):
    """Native checkpoint dialects this adapter reads."""

    CIE_BATCH = "cie-batch-checkpoint"
    IELTS_RUN = "ielts-run-checkpoint/1"
    UNKNOWN = "unknown"


class CheckpointReadError(OSError):
    """Raised when a checkpoint file cannot be opened for reading."""


class CheckpointTooLargeError(CheckpointReadError):
    """Raised when a bounded read finds the file larger than the allowed budget."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_utc(moment: datetime) -> str:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


def parse_native_timestamp(text: Any) -> datetime | None:
    """Parse a native ``updated_at`` string to aware UTC, or ``None``.

    The two real dialects are ``2026-10-06T08:18:31+0800`` (CIE; no colon in
    the offset) and ``2026-10-04T19:40:15.361Z`` (IELTS). Anything else is
    reported as unknown rather than guessed. A naive value is the one
    exception: it is read as UTC, because the string itself carries no zone.
    """
    if not isinstance(text, str) or not text.strip():
        return None
    probe = text.strip()
    if probe.endswith("Z"):
        probe = probe[:-1] + "+00:00"
    try:
        moment = datetime.fromisoformat(probe)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


@dataclass
class CheckpointObservation:
    """One read-only observation of one checkpoint file.

    ``payload`` is the parsed JSON document exactly as stored (synthetic
    markers and unknown keys included); it is never rewritten. ``problems`` is
    empty for a clean read and lists typed problem codes otherwise.
    """

    source: str
    format: CheckpointFormat
    native_schema: str | None
    native_updated_at: str | None
    payload: Any
    payload_sha256: str
    size_bytes: int
    observed_at: str
    problems: list[str] = field(default_factory=list)

    @property
    def document(self) -> dict[str, Any]:
        """The payload if it is a JSON object, else an empty mapping."""
        return self.payload if isinstance(self.payload, dict) else {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "format": str(self.format),
            "native_schema": self.native_schema,
            "native_updated_at": self.native_updated_at,
            "payload_sha256": self.payload_sha256,
            "size_bytes": self.size_bytes,
            "observed_at": self.observed_at,
            "problems": list(self.problems),
            "payload": self.payload,
        }


def detect_format(document: Any) -> CheckpointFormat:
    """Detect the native dialect from the document itself.

    Detection is structural on purpose: the CIE batch file carries no schema
    version, so it is recognised by its ``totals``/``stage`` pair; the IELTS
    run file is recognised by the version string it declares.
    """
    if not isinstance(document, dict):
        return CheckpointFormat.UNKNOWN
    if document.get("schema_version") == CheckpointFormat.IELTS_RUN.value:
        return CheckpointFormat.IELTS_RUN
    if "totals" in document and "stage" in document:
        return CheckpointFormat.CIE_BATCH
    return CheckpointFormat.UNKNOWN


def read_checkpoint_bytes(data: bytes, *, source: str,
                          observed_at: datetime | None = None) -> CheckpointObservation:
    """Read one checkpoint from bytes; pure and read-only by construction."""
    digest = hashlib.sha256(data).hexdigest()
    problems: list[str] = []
    payload: Any = None
    parse_failed = False
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        parse_failed = True
        problems.append("json_unreadable")
    document = payload if isinstance(payload, dict) else None
    if not parse_failed and document is None:
        problems.append("payload_not_an_object")
    fmt = detect_format(document) if document is not None else CheckpointFormat.UNKNOWN
    if document is not None and fmt is CheckpointFormat.UNKNOWN:
        problems.append("unrecognised_checkpoint_format")
    native_schema = document.get("schema_version") if document is not None else None
    native_updated = document.get("updated_at") if document is not None else None
    if document is not None and not isinstance(native_updated, str):
        problems.append("missing_updated_at")
    moment = observed_at if observed_at is not None else _utc_now()
    return CheckpointObservation(
        source=source,
        format=fmt,
        native_schema=native_schema if isinstance(native_schema, str) else None,
        native_updated_at=native_updated if isinstance(native_updated, str) else None,
        payload=payload,
        payload_sha256=digest,
        size_bytes=len(data),
        observed_at=_iso_utc(moment),
        problems=problems,
    )


def read_checkpoint(path: str | Path, *, source: str | None = None,
                    observed_at: datetime | None = None) -> CheckpointObservation:
    """Read one checkpoint file; never opens it for writing."""
    target = Path(path)
    try:
        data = target.read_bytes()
    except OSError as exc:
        raise CheckpointReadError(
            f"cannot read checkpoint {target.name!r}: {exc.__class__.__name__}") from exc
    return read_checkpoint_bytes(data, source=source or target.name,
                                 observed_at=observed_at)


def read_checkpoint_bounded(path: str | Path, *, source: str | None = None,
                            observed_at: datetime | None = None,
                            max_bytes: int) -> CheckpointObservation:
    """Read one checkpoint with a hard byte budget (``max_bytes`` + 1 probe).

    The extra byte detects a file that grew past the budget between the scan's
    size check and this read: it is reported as :class:`CheckpointTooLargeError`
    instead of being loaded whole, so a hostile or racing file can never force
    an unbounded read.
    """
    target = Path(path)
    try:
        with target.open("rb") as handle:
            data = handle.read(max_bytes + 1)
    except OSError as exc:
        raise CheckpointReadError(
            f"cannot read checkpoint {target.name!r}: {exc.__class__.__name__}") from exc
    if len(data) > max_bytes:
        raise CheckpointTooLargeError(
            f"checkpoint {target.name!r} is larger than {max_bytes} bytes")
    return read_checkpoint_bytes(data, source=source or target.name,
                                 observed_at=observed_at)


@dataclass
class CieBatchState:
    """Typed view of the CIE batch runner checkpoint; values stay verbatim."""

    observation: CheckpointObservation
    stage: str | None
    loop_stage: str | None
    current_subject: str | None
    current_paper: str | None
    totals: dict[str, Any] | None
    loop_stages: dict[str, Any] | None
    stop_reason: str | None
    stop_detail: dict[str, Any] | None
    stopped_at: str | None
    needs_user_resume: bool | None
    resume_policy: str | None

    @property
    def updated_at(self) -> str | None:
        return self.observation.native_updated_at


@dataclass
class IeltsRunState:
    """Typed view of an IELTS run checkpoint; counters/sources stay verbatim."""

    observation: CheckpointObservation
    run_id: str | None
    updated_at: str | None
    counters: dict[str, Any] | None
    sources: dict[str, Any] | None


def _as_dict(value: Any) -> dict[str, Any] | None:
    return dict(value) if isinstance(value, dict) else None


def _as_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def cie_batch_state(observation: CheckpointObservation) -> CieBatchState | None:
    """Build the CIE batch view, or ``None`` for a non-CIE observation."""
    if observation.format is not CheckpointFormat.CIE_BATCH:
        return None
    doc = observation.document
    needs_resume = doc.get("needs_user_resume")
    return CieBatchState(
        observation=observation,
        stage=_as_str(doc.get("stage")),
        loop_stage=_as_str(doc.get("loop_stage")),
        current_subject=_as_str(doc.get("current_subject")),
        current_paper=_as_str(doc.get("current_paper")),
        totals=_as_dict(doc.get("totals")),
        loop_stages=_as_dict(doc.get("loop_stages")),
        stop_reason=_as_str(doc.get("stop_reason")),
        stop_detail=_as_dict(doc.get("stop_detail")),
        stopped_at=_as_str(doc.get("stopped_at")),
        needs_user_resume=needs_resume if isinstance(needs_resume, bool) else None,
        resume_policy=_as_str(doc.get("resume_policy")),
    )


def ielts_run_state(observation: CheckpointObservation) -> IeltsRunState | None:
    """Build the IELTS run view, or ``None`` for a non-IELTS observation."""
    if observation.format is not CheckpointFormat.IELTS_RUN:
        return None
    doc = observation.document
    fetcher = _as_dict(doc.get("fetcher")) or {}
    return IeltsRunState(
        observation=observation,
        run_id=_as_str(doc.get("run_id")),
        updated_at=observation.native_updated_at,
        counters=_as_dict(fetcher.get("counters")),
        sources=_as_dict(fetcher.get("sources")),
    )


def state_of(observation: CheckpointObservation) -> CieBatchState | IeltsRunState | None:
    """Return the typed view for an observation, or ``None`` when unknown."""
    if observation.format is CheckpointFormat.CIE_BATCH:
        return cie_batch_state(observation)
    if observation.format is CheckpointFormat.IELTS_RUN:
        return ielts_run_state(observation)
    return None


class _CheckpointPathWalk:
    """Lazy deterministic directory walk with an optional entry budget (private).

    One directory is listed at a time - never the whole tree - and each
    listing is sorted by ``name + "/"`` per level, so the yielded files keep
    the full-path lexicographic order the previous sorted listing produced.
    ``entries_seen`` counts every directory entry discovered; when it reaches
    ``max_entries`` (not ``None``) the walk stops and reports the exhausted
    budget via ``exhausted == "directory_entries"``.
    """

    def __init__(self, base: Path, wanted: frozenset[str],
                 max_entries: int | None) -> None:
        self._base = base
        self._wanted = wanted
        self._max_entries = max_entries
        self._stack: list[Any] = []
        self._started = False
        self._done = False
        self.entries_seen = 0
        self.exhausted: str | None = None

    def _listing(self, directory: Path) -> list[tuple[Path, bool]]:
        """One directory's entries, sorted; unreadable directories list empty."""
        try:
            with os.scandir(directory) as scan:
                entries = list(scan)
        except OSError:
            return []
        listed: list[tuple[Path, bool]] = []
        for entry in entries:
            try:
                is_dir = entry.is_dir()
            except OSError:  # pragma: no cover - defensive only
                is_dir = False
            listed.append((Path(entry.path), is_dir))
        listed.sort(key=lambda item: item[0].name + ("/" if item[1] else ""))
        return listed

    def __iter__(self) -> _CheckpointPathWalk:
        return self

    def __next__(self) -> Path:
        if self._done:
            raise StopIteration
        if not self._started:
            self._started = True
            self._stack.append(iter(self._listing(self._base)))
        while True:
            if not self._stack:
                self._done = True
                raise StopIteration
            iterator = self._stack[-1]
            try:
                path, is_dir = next(iterator)
            except StopIteration:
                self._stack.pop()
                continue
            if (self._max_entries is not None
                    and self.entries_seen >= self._max_entries):
                self._done = True
                self.exhausted = "directory_entries"
                raise StopIteration
            self.entries_seen += 1
            if is_dir:
                self._stack.append(iter(self._listing(path)))
                continue
            if path.name in self._wanted:
                return path


def iter_checkpoint_paths(root: str | Path, *,
                          names: Iterable[str] = ("checkpoint.json",),
                          max_entries: int | None = None) -> _CheckpointPathWalk:
    """Walk checkpoint files under ``root``: lazy, sorted, budget-bounded.

    The walk lists one directory at a time in deterministic full-path
    lexicographic order (``name + "/"`` per directory level) and never
    materialises the tree. ``max_entries`` bounds the directory entries the
    walk may discover before it stops; on exhaustion the returned walker
    reports ``exhausted == "directory_entries"`` with ``entries_seen``
    counting every entry discovered before the stop.
    """
    return _CheckpointPathWalk(Path(root), frozenset(names), max_entries)


__all__ = [
    "CheckpointFormat",
    "CheckpointObservation",
    "CheckpointReadError",
    "CheckpointTooLargeError",
    "CieBatchState",
    "IeltsRunState",
    "cie_batch_state",
    "detect_format",
    "ielts_run_state",
    "iter_checkpoint_paths",
    "parse_native_timestamp",
    "read_checkpoint",
    "read_checkpoint_bounded",
    "read_checkpoint_bytes",
    "state_of",
]
