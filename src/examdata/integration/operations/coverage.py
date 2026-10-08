"""Derived coverage views over checkpoint observations (plan 3.5, packet A13).

A coverage view is computed, never stored: observations are grouped by
``(system, scope)``, ranked by their native ``updated_at`` (tie-broken by the
observation time) and *all* of them are kept - superseded snapshots stay in
the view as ``superseded`` rows, so a stale summary can never masquerade as the
latest state. A same-instant disagreement between two snapshots becomes an
explicit ``conflict`` instead of a silent pick.

States are derived only from native fields and never overwrite them; counters
(``totals`` for a CIE batch, ``fetcher.counters`` for an IELTS run) and the
per-source health map are carried verbatim, and a counter the native file does
not provide stays ``None`` - it is never rendered as zero. Unknown checkpoints
are carried as ``unknown`` rows with their problems, not dropped.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

from .checkpoints import (
    CheckpointFormat,
    CheckpointObservation,
    CieBatchState,
    IeltsRunState,
    _StrEnum,
    cie_batch_state,
    ielts_run_state,
    parse_native_timestamp,
)

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


class CoverageState(_StrEnum):
    """Derived state vocabulary; native fields remain the authority."""

    OK = "ok"
    COMPLETE = "complete"
    IN_PROGRESS = "in_progress"
    PARTIAL_FAILURE = "partial_failure"
    STOPPED = "stopped"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


def cie_coverage_state(state: CieBatchState) -> CoverageState:
    """Derive the CIE batch state from native fields only (never overwritten)."""
    if state.stop_reason:
        return CoverageState.STOPPED
    totals = state.totals or {}
    if totals.get("complete") is True:
        return CoverageState.COMPLETE
    if state.stage in {"running", "resuming"} or state.loop_stage in {"running", "queued"}:
        return CoverageState.IN_PROGRESS
    return CoverageState.UNKNOWN


def ielts_coverage_state(state: IeltsRunState) -> CoverageState:
    """Derive the IELTS run state from native fields only (never overwritten)."""
    sources = state.sources or {}
    blocked = [s for s in sources.values() if isinstance(s, dict) and s.get("blocked")]
    errors = (state.counters or {}).get("errors")
    if state.counters is None and state.sources is None:
        return CoverageState.UNKNOWN
    if sources and len(blocked) == len(sources):
        return CoverageState.BLOCKED
    if blocked or (isinstance(errors, int) and errors > 0):
        return CoverageState.PARTIAL_FAILURE
    return CoverageState.OK


@dataclass
class CoverageRow:
    """One observation as a coverage row; native values stay verbatim."""

    system: str
    scope_id: str
    scope_kind: str
    state: str
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "system": self.system,
            "scope_id": self.scope_id,
            "scope_kind": self.scope_kind,
            "state": self.state,
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
class CoverageView:
    """Derived rows plus explicit conflicts and surfaced problems."""

    rows: list[CoverageRow] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)

    @property
    def current_rows(self) -> list[CoverageRow]:
        return [row for row in self.rows if row.freshness == "current"]

    @property
    def problems(self) -> list[dict[str, Any]]:
        return [{"source": row.source, "problems": list(row.problems)}
                for row in self.rows if row.problems]

    def rows_for(self, system: str, scope_id: str | None = None,
                 freshness: str | None = None) -> list[CoverageRow]:
        """Deterministic row filter used by tests and future views."""
        return [row for row in self.rows
                if row.system == system
                and (scope_id is None or row.scope_id == scope_id)
                and (freshness is None or row.freshness == freshness)]

    def to_dict(self) -> dict[str, Any]:
        return {
            "rows": [row.to_dict() for row in self.rows],
            "conflicts": [dict(conflict) for conflict in self.conflicts],
            "problems": self.problems,
        }


def _scope_keys(observation: CheckpointObservation) -> tuple[str, str, str]:
    """(system, scope_id, scope_kind); native ids first, source label last."""
    if observation.format is CheckpointFormat.CIE_BATCH:
        state = cie_batch_state(observation)
        subject = (state.current_subject if state else None) or "unknown-subject"
        return ("cie", f"cie-batch:{subject}", "batch")
    if observation.format is CheckpointFormat.IELTS_RUN:
        state = ielts_run_state(observation)
        run_id = (state.run_id if state else None) or f"run@{observation.source}"
        return ("ielts", run_id, "run")
    return ("unknown", f"unknown:{observation.source}", "unknown")


def _recency(observation: CheckpointObservation) -> tuple[datetime, datetime]:
    """Native ``updated_at`` first (missing reads as oldest), observed time second."""
    native = parse_native_timestamp(observation.native_updated_at)
    observed = parse_native_timestamp(observation.observed_at)
    return (native if native is not None else _EPOCH,
            observed if observed is not None else _EPOCH)


def _sort_key(observation: CheckpointObservation) -> tuple[float, float, str]:
    native, observed = _recency(observation)
    return (-native.timestamp(), -observed.timestamp(), observation.source)


def _row(observation: CheckpointObservation, system: str, scope_id: str,
         scope_kind: str, freshness: str) -> CoverageRow:
    if observation.format is CheckpointFormat.CIE_BATCH:
        state = cie_batch_state(observation)
        row_state = cie_coverage_state(state).value
        counters = state.totals
        sources = None
        stop = None
        if state.stop_reason or state.stop_detail:
            stop = {"reason": state.stop_reason, "detail": state.stop_detail,
                    "stopped_at": state.stopped_at}
        resume = None
        if state.needs_user_resume is not None or state.resume_policy:
            resume = {"needs_user_resume": state.needs_user_resume,
                      "resume_policy": state.resume_policy}
    elif observation.format is CheckpointFormat.IELTS_RUN:
        state = ielts_run_state(observation)
        row_state = ielts_coverage_state(state).value
        counters = state.counters
        sources = state.sources
        stop = None
        resume = None
    else:
        row_state = CoverageState.UNKNOWN.value
        counters = None
        sources = None
        stop = None
        resume = None
    return CoverageRow(
        system=system,
        scope_id=scope_id,
        scope_kind=scope_kind,
        state=row_state,
        freshness=freshness,
        counters=counters,
        sources=sources,
        stop=stop,
        resume=resume,
        source=observation.source,
        observed_at=observation.observed_at,
        native_updated_at=observation.native_updated_at,
        payload_sha256=observation.payload_sha256,
        problems=list(observation.problems),
    )


def build_coverage(observations: Iterable[CheckpointObservation]) -> CoverageView:
    """Group, rank and retain every observation as a coverage row."""
    groups: dict[tuple[str, str, str], list[CheckpointObservation]] = {}
    for observation in observations:
        groups.setdefault(_scope_keys(observation), []).append(observation)
    view = CoverageView()
    for system, scope_id, scope_kind in sorted(groups):
        ordered = sorted(groups[(system, scope_id, scope_kind)], key=_sort_key)
        top_native = _recency(ordered[0])[0]
        tied = [obs for obs in ordered if _recency(obs)[0] == top_native]
        if len(tied) > 1 and len({obs.payload_sha256 for obs in tied}) > 1:
            for observation in tied:
                view.rows.append(_row(observation, system, scope_id, scope_kind, "conflict"))
            view.conflicts.append({
                "system": system,
                "scope_id": scope_id,
                "native_updated_at": tied[0].native_updated_at,
                "sources": [obs.source for obs in tied],
                "payload_sha256": [obs.payload_sha256 for obs in tied],
            })
            for observation in ordered[len(tied):]:
                view.rows.append(_row(observation, system, scope_id, scope_kind, "superseded"))
        else:
            for index, observation in enumerate(ordered):
                freshness = "current" if index == 0 else "superseded"
                view.rows.append(_row(observation, system, scope_id, scope_kind, freshness))
    return view


__all__ = [
    "CoverageState",
    "CoverageRow",
    "CoverageView",
    "build_coverage",
    "cie_coverage_state",
    "ielts_coverage_state",
]
