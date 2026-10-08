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

Every read here is bounded: :func:`read_bytes_bounded` computes its allowance
*at read time* as ``min(max_bytes, budget.remaining)`` and pulls at most one
extra byte as a documented overflow probe, so neither a single runaway file
nor a hostile tree can make the process slurp unbounded bytes. Discovery is
bounded the same way by :class:`_CheckpointPathWalk`, which records budget
exhaustion in ``reasons`` instead of raising.

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
    """Raised when a checkpoint exceeds the bounded-read byte budget.

    ``bytes_read`` records how many bytes the bounded read actually consumed
    before refusing, so callers can account the failed attempt honestly.
    """

    def __init__(self, message: str, *, bytes_read: int | None = None) -> None:
        super().__init__(message)
        self.bytes_read = bytes_read


class ReadBudgetExhaustedError(CheckpointReadError):
    """Raised when a shared byte budget runs out during a bounded read.

    Distinct from :class:`CheckpointTooLargeError`: the file may fit its own
    single-file cap, but the *shared* scan budget was already spent by
    earlier reads. ``bytes_read`` records the true bytes pulled before the
    stop so the scan can account them and report ``read_bytes``.
    """

    def __init__(self, message: str, *, bytes_read: int | None = None) -> None:
        super().__init__(message)
        self.bytes_read = bytes_read


@dataclass
class ByteBudget:
    """Shared consumable byte allowance, consulted at read time.

    ``limit`` is ``None`` for an unlimited budget. ``remaining`` is computed
    on every access (never cached), so a caller that checks it just before
    reading gets the current allowance; ``consume`` records true payload
    bytes actually pulled and returns the new total. Recording never rejects:
    the bounded read's documented ``allowance + 1`` overflow probe is
    consumed honestly before the read refuses.
    """

    limit: int | None = None
    consumed: int = 0

    def __post_init__(self) -> None:
        if self.limit is not None and (isinstance(self.limit, bool)
                                       or not isinstance(self.limit, int)):
            raise ValueError("byte budget limit must be an integer or None")
        if self.limit is not None and self.limit < 0:
            raise ValueError("byte budget limit must not be negative")
        if isinstance(self.consumed, bool) or not isinstance(self.consumed, int):
            raise ValueError("byte budget consumed must be an integer")
        if self.consumed < 0:
            raise ValueError("byte budget consumed must not be negative")

    @property
    def remaining(self) -> int | None:
        """Bytes left (never negative), or ``None`` when unlimited."""
        if self.limit is None:
            return None
        return max(0, self.limit - self.consumed)

    @property
    def exhausted(self) -> bool:
        """True once a finite budget has been fully consumed."""
        return self.limit is not None and self.consumed >= self.limit

    def consume(self, amount: int) -> int:
        """Record ``amount`` true bytes read; returns the new total."""
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
            raise ValueError("byte budget consume() needs a non-negative integer")
        self.consumed += amount
        return self.consumed

    def to_dict(self) -> dict[str, int | None]:
        return {"limit": self.limit, "consumed": self.consumed}


#: Default cap for a single bounded checkpoint read (callers may lower it).
DEFAULT_MAX_CHECKPOINT_BYTES = 4 * 1024 * 1024


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


def read_bytes_bounded(path: str | Path, *, max_bytes: int,
                       budget: ByteBudget | None = None,
                       subject: str = "checkpoint") -> bytes:
    """Read a file's bytes through one allowance, honouring a shared budget.

    The allowance is computed *at read time* as ``min(max_bytes,
    budget.remaining)`` and at most ``allowance + 1`` bytes are ever pulled
    from the handle (the documented overflow probe that detects a too-large
    file without slurping it whole). True bytes pulled are recorded on the
    shared ``budget`` before any refusal, so accounting stays honest:

    * a successful read consumes ``len(data) <= allowance``;
    * a read that pulls ``allowance + 1`` bytes consumes them all and then
      raises :class:`CheckpointTooLargeError` when the per-file cap is the
      binding limit, or :class:`ReadBudgetExhaustedError` when the shared
      budget is; a budget already spent (``remaining == 0``) refuses before
      opening anything.
    """
    target = Path(path)
    remaining = budget.remaining if budget is not None else None
    if remaining == 0:
        raise ReadBudgetExhaustedError(
            f"cannot read {subject} {target.name!r}: the shared read budget is exhausted",
            bytes_read=0)
    allowance = max_bytes if remaining is None else min(max_bytes, remaining)
    try:
        with target.open("rb") as handle:
            data = handle.read(allowance + 1)
    except OSError as exc:
        raise CheckpointReadError(
            f"cannot read {subject} {target.name!r}: {exc.__class__.__name__}") from exc
    if len(data) > allowance:
        if budget is not None:
            budget.consume(len(data))
        if remaining is None or max_bytes <= remaining:
            raise CheckpointTooLargeError(
                f"{subject} {target.name!r} exceeds the {max_bytes} byte read budget",
                bytes_read=len(data))
        raise ReadBudgetExhaustedError(
            f"cannot read {subject} {target.name!r}: the shared read budget is exhausted",
            bytes_read=len(data))
    if budget is not None:
        budget.consume(len(data))
    return data


def read_checkpoint_bounded(path: str | Path, *, source: str | None = None,
                            observed_at: datetime | None = None,
                            max_bytes: int = DEFAULT_MAX_CHECKPOINT_BYTES,
                            budget: ByteBudget | None = None
                            ) -> CheckpointObservation:
    """Read one checkpoint without consuming more than its allowance.

    The file is read through a single ``allowance + 1`` probe where the
    allowance is ``min(max_bytes, budget.remaining)`` computed at read time:
    a file at or under the allowance is parsed exactly like
    :func:`read_checkpoint`; a larger one raises
    :class:`CheckpointTooLargeError` (per-file cap binds) or
    :class:`ReadBudgetExhaustedError` (shared budget binds) after at most
    ``allowance + 1`` bytes, so a runaway or hostile file - or an exhausted
    scan budget - is never slurped whole.
    """
    data = read_bytes_bounded(path, max_bytes=max_bytes, budget=budget,
                              subject="checkpoint")
    return read_checkpoint_bytes(data, source=source or Path(path).name,
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


class _WalkLevel:
    """One directory's bounded progress: buffer, iterator, probe slot."""

    __slots__ = ("path", "depth", "scan", "buffer", "filled", "exhausted",
                 "probe_match")

    def __init__(self, path: Path, depth: int) -> None:
        self.path = path
        self.depth = depth
        self.scan: Any = None
        self.buffer: list[tuple[str, str, str, bool]] = []
        self.filled = False
        self.exhausted = False
        self.probe_match: Path | None = None


class _CheckpointPathWalk:
    """Lazy, budget-bounded, deterministic walk for checkpoint files.

    Traversal rule (documented, deterministic): pre-order depth-first, where
    each directory's entries are ordered per level with the sort key
    ``name + "/"`` for directories and ``name`` for files. That key gives
    exactly full-path lexicographic order for siblings (a directory's own
    descendants sort where its path would), so an unbounded walk yields the
    same order as sorting every full path string, while never materialising
    more than one directory's entries at a time.

    Discovery is bounded by entry budgets: each directory contributes at most
    the remaining ``max_entries``/``max_retained`` slots, pulled lazily from a
    live ``os.scandir`` iterator (never a materialised full tree). When a
    directory may hold more entries than its allowance, exactly one extra
    probe pull decides; if it finds an entry, ``directory_entries`` or
    ``retained_paths`` is recorded in :attr:`reasons`, the sorted prefix
    already enumerated is kept, and legitimately enumerated directories are
    still descended. A probe that finds a matching file is still yielded
    (after the sorted prefix, in native directory order) - the one way a
    zero-allowance directory can contribute its checkpoint. Directories below
    ``max_depth`` are refused (``depth``) and unreadable directories are
    reported (``unreadable_directory``), never raised.

    Counters: :attr:`entries_seen` counts accepted entries (never above a
    cap), :attr:`entries_consumed` counts raw ``os.scandir`` pulls (probes
    included), :attr:`peak_retained` is the high-water mark of buffered
    paths. Per directory the raw cost is at most ``allowance + 1`` pulls; the
    walk as a whole consumes at most its accepted entries plus one probe per
    entered directory. ``max_entries=None`` and ``max_retained=None`` keep
    the walk unlimited but still lazy and deterministic.
    """

    def __init__(self, root: str | Path, names: Iterable[str],
                 max_entries: int | None,
                 max_retained: int | None = None,
                 max_depth: int | None = None) -> None:
        self._names = frozenset(str(name) for name in names)
        self._max_entries = max_entries
        self._max_retained = max_retained
        self._max_depth = max_depth
        self._root = Path(root)
        self._stack: list[_WalkLevel] = []
        self._started = False
        self._closed = False
        self._retained = 0
        self.entries_seen = 0
        self.entries_consumed = 0
        self.peak_retained = 0
        self.reasons: list[str] = []

    def __iter__(self) -> "_CheckpointPathWalk":
        return self

    @property
    def exhausted(self) -> bool:
        """True when any discovery budget ran out (see :attr:`reasons`)."""
        return bool(self.reasons)

    def _note(self, reason: str) -> None:
        if reason not in self.reasons:
            self.reasons.append(reason)

    def _allowance(self) -> int | None:
        gaps: list[int] = []
        if self._max_entries is not None:
            gaps.append(max(0, self._max_entries - self.entries_seen))
        if self._max_retained is not None:
            gaps.append(max(0, self._max_retained - self._retained))
        if not gaps:
            return None
        return min(gaps)

    def _push_level(self, path: Path, depth: int) -> None:
        if self._max_depth is not None and depth > self._max_depth:
            self._note("depth")
            return
        try:
            scan = os.scandir(path)
        except OSError:
            self._note("unreadable_directory")
            return
        level = _WalkLevel(path, depth)
        level.scan = scan
        self._stack.append(level)

    def _pop_level(self) -> None:
        level = self._stack.pop()
        if level.scan is not None:
            try:
                level.scan.close()
            except OSError:  # pragma: no cover - defensive only
                pass

    def _fill(self, level: _WalkLevel) -> None:
        if level.filled:
            return
        level.filled = True
        allowance = self._allowance()
        pulled = 0
        try:
            while allowance is None or pulled < allowance:
                entry = next(level.scan, None)
                if entry is None:
                    level.exhausted = True
                    break
                self.entries_consumed += 1
                try:
                    is_dir = entry.is_dir(follow_symlinks=False)
                except OSError:  # pragma: no cover - defensive only
                    is_dir = False
                key = entry.name + "/" if is_dir else entry.name
                level.buffer.append((key, entry.name, entry.path, is_dir))
                self.entries_seen += 1
                self._retained += 1
                if self._retained > self.peak_retained:
                    self.peak_retained = self._retained
                pulled += 1
        except OSError:
            self._note("unreadable_directory")
            level.exhausted = True
        level.buffer.sort(key=lambda item: item[0])
        if level.exhausted or allowance is None or pulled != allowance:
            return
        # The directory may still hold entries beyond the allowance: exactly
        # one probe pull decides, and is the most this directory ever spends.
        try:
            probe = next(level.scan, None)
        except OSError:
            self._note("unreadable_directory")
            probe = None
        if probe is None:
            return
        self.entries_consumed += 1
        if (self._max_entries is not None
                and self.entries_seen >= self._max_entries):
            self._note("directory_entries")
        elif (self._max_retained is not None
                and self._retained >= self._max_retained):
            self._note("retained_paths")
        else:  # pragma: no cover - one of the caps must bind here
            self._note("directory_entries")
        try:
            probe_is_dir = probe.is_dir(follow_symlinks=False)
        except OSError:  # pragma: no cover - defensive only
            probe_is_dir = False
        if not probe_is_dir and probe.name in self._names:
            level.probe_match = Path(probe.path)

    def __next__(self) -> Path:
        while True:
            if self._closed:
                raise StopIteration
            if not self._started:
                self._started = True
                if self._root.is_dir():
                    self._push_level(self._root, 0)
            if not self._stack:
                self.close()
                raise StopIteration
            level = self._stack[-1]
            self._fill(level)
            if level.buffer:
                _key, name, path, is_dir = level.buffer.pop(0)
                self._retained -= 1
                if is_dir:
                    self._push_level(Path(path), level.depth + 1)
                    continue
                if name in self._names:
                    return Path(path)
                continue
            if level.probe_match is not None:
                match = level.probe_match
                level.probe_match = None
                self._pop_level()
                return match
            self._pop_level()

    def close(self) -> None:
        """Drop every open iterator; the walk is finished either way."""
        self._closed = True
        while self._stack:
            self._pop_level()


def iter_checkpoint_paths(root: str | Path,
                          names: Iterable[str] = ("checkpoint.json",),
                          max_entries: int | None = None,
                          max_retained: int | None = None,
                          max_depth: int | None = None) -> _CheckpointPathWalk:
    """Iterate checkpoint files under ``root``, lazily and in bounded order.

    Returns a :class:`_CheckpointPathWalk`: an iterator (never a materialised
    list) that discovers one bounded directory prefix at a time.
    ``max_entries`` bounds accepted entries, ``max_retained`` bounds buffered
    paths and ``max_depth`` refuses deeper directories; each ``None`` keeps
    that bound unlimited while the walk stays lazy and deterministic.
    """
    return _CheckpointPathWalk(root, names, max_entries, max_retained,
                               max_depth)


__all__ = [
    "ByteBudget",
    "CheckpointFormat",
    "CheckpointObservation",
    "CheckpointReadError",
    "CheckpointTooLargeError",
    "CieBatchState",
    "DEFAULT_MAX_CHECKPOINT_BYTES",
    "IeltsRunState",
    "cie_batch_state",
    "detect_format",
    "ielts_run_state",
    "iter_checkpoint_paths",
    "parse_native_timestamp",
    "read_bytes_bounded",
    "read_checkpoint",
    "read_checkpoint_bounded",
    "read_checkpoint_bytes",
    "ReadBudgetExhaustedError",
    "state_of",
]
