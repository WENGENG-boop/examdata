"""W3 C05/C06 reproduction script (private run only).

Runs the two confirmed integration-review defect scenarios against a given
candidate root and prints a JSON verdict. ``reproduced`` means *the defect is
present* in that tree, so the frozen parent reports ``true`` for both cases
and the repaired closure candidate reports ``false``:

* C05 - a one-shot secret iterable (generator) passed to a public projection
  must produce the same fully redacted output as the equivalent tuple. The
  defect consults the caller's iterable once per string leaf, so the generator
  is exhausted by the first leaf and every later leaf leaks the marker.
* C06 - the operations view must be a bounded TTL observation: within the
  declared TTL a cached observation is served, after it a fresh scan replaces
  it with a new ``observation_revision``, and a failing refresh past the TTL
  serves the last good observation flagged ``stale`` instead of raising. The
  frozen parent has no ``OperationsObservationService`` at all, which is
  itself the reproduced defect (``api: absent``).

Usage:
    python -B w3_reproduce.py <candidate-root> <scratch-root>

The scratch root is created if missing; both subtrees are rebuilt from
scratch so one scratch root can serve both verdict runs. The script always
exits 0 when it ran; a crash (import error, unexpected exception outside a
case) is a script failure, not a verdict.
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MARKER = "SYNTHSECRET-ALPHA-W3"


class _FakeClock:
    """A deterministic, monotonic test clock: tests drive it, never sleep."""

    def __init__(self, start: datetime) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        from datetime import timedelta
        self.now = self.now + timedelta(seconds=seconds)


def _prepare(candidate_root: Path) -> None:
    src = candidate_root / "src"
    if not src.is_dir():
        raise SystemExit(f"candidate root has no src/ directory: {candidate_root}")
    sys.path.insert(0, str(src))
    import os
    os.environ["EXAMDATA_INTEGRATION_ROOT"] = str(candidate_root)


def _write_json(path: Path, document: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return path


def _running_document() -> dict[str, Any]:
    return {
        "stage": "running",
        "loop_stage": "idle",
        "current_subject": "synth-w3",
        "totals": {"done": 1},
        "updated_at": "2026-10-06T08:18:31+0800",
    }


def _stopped_document() -> dict[str, Any]:
    return {
        "stage": "stopped",
        "loop_stage": "idle",
        "current_subject": "synth-w3",
        "totals": {"done": 2},
        "stop_reason": "halted by the operator",
        "needs_user_resume": True,
        "resume_policy": "manual",
        "updated_at": "2026-10-07T02:10:00+0000",
    }


def _marker_document() -> dict[str, Any]:
    """One CIE checkpoint carrying the marker in keys and values alike."""
    return {
        "stage": "stopped",
        "loop_stage": "idle",
        "current_subject": "synth-w3",
        "totals": {f"count-{MARKER}": 1, "done": 1},
        "stop_reason": f"halted at {MARKER}",
        "stop_detail": {f"log {MARKER}": f"see {MARKER}",
                        "nested": {"deep": f"value {MARKER}"}},
        "needs_user_resume": True,
        "resume_policy": MARKER,
        "updated_at": "2026-10-06T08:18:31+0800",
    }


def _fresh_root(scratch: Path) -> Path:
    root = scratch / "ops"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    return root


def _blob(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _case_c05(scratch: Path, dataset_mod: Any) -> dict[str, Any]:
    root = _fresh_root(scratch)
    _write_json(root / "cie" / "checkpoint.json", _marker_document())

    view = dataset_mod.operations_view(entries=[], root=root,
                                       dataset_revision="rev-w3-repro")
    case: dict[str, Any] = {
        "id": "C05",
        "detail": ("one marker-bearing CIE checkpoint; public projection with "
                   "secrets=(marker,) vs secrets=<one-shot generator over the "
                   "same marker> must be byte-identical and marker-free"),
        "marker": MARKER,
    }
    if view is None:
        case["reproduced"] = True
        case["error"] = "operations_view returned None for a configured root"
        return case

    blob_tuple = _blob(view.to_public(secrets=(MARKER,)))
    blob_generator = _blob(view.to_public(secrets=(x for x in (MARKER,))))

    tuple_count = blob_tuple.count(MARKER)
    generator_count = blob_generator.count(MARKER)
    case.update({
        "tuple_marker_count": tuple_count,
        "generator_marker_count": generator_count,
        "outputs_identical": blob_tuple == blob_generator,
        "placeholder_present_in_tuple_output": "<secret>" in blob_tuple,
        "reproduced": (generator_count > 0
                       or tuple_count > 0
                       or blob_tuple != blob_generator),
    })
    return case


def _stage_of(view: Any) -> str | None:
    briefs = view.jobs.briefs()
    if len(briefs) != 1:
        return None
    return briefs[0].get("stage")


def _case_c06(scratch: Path, dataset_mod: Any) -> dict[str, Any]:
    service_cls = getattr(dataset_mod, "OperationsObservationService", None)
    if service_cls is None:
        return {
            "id": "C06",
            "detail": ("the frozen tree has no ObservationService at all: an "
                       "operations view is built once and never observed "
                       "again"),
            "api": "absent",
            "reproduced": True,
        }

    root = _fresh_root(scratch)
    _write_json(root / "cie" / "checkpoint.json", _running_document())

    clock = _FakeClock(datetime(2026, 10, 7, 0, 0, 0, tzinfo=timezone.utc))
    service = service_cls(root, ttl_seconds=30.0, clock=clock,
                          dataset_revision="rev-w3-repro")
    checks: dict[str, bool] = {}

    first = service.observe()
    checks["first_stage_running"] = _stage_of(first) == "running"
    checks["first_staleness_current"] = first.staleness == "current"
    checks["first_age_zero"] = first.age_seconds == 0.0
    checks["first_observed_at"] = isinstance(first.observed_at, str) and bool(first.observed_at)
    checks["revision_distinct_from_dataset_revision"] = (
        isinstance(first.observation_revision, str)
        and first.observation_revision != "rev-w3-repro")
    checks["ttl_declared"] = first.ttl_seconds == 30.0

    # Within the TTL the cache is served even though the file changed.
    clock.advance(10.0)
    _write_json(root / "cie" / "checkpoint.json", _stopped_document())
    second = service.observe()
    checks["within_ttl_cached_stage"] = _stage_of(second) == "running"
    checks["within_ttl_revision_stable"] = (
        second.observation_revision == first.observation_revision)
    checks["within_ttl_age_reported"] = second.age_seconds == 10.0

    # Past the TTL the observation is refreshed.
    clock.advance(25.0)  # 35 > 30
    third = service.observe()
    checks["after_ttl_revision_bumped"] = (
        third.observation_revision != first.observation_revision)
    checks["after_ttl_age_zero"] = third.age_seconds == 0.0
    checks["after_ttl_stage_refreshed"] = _stage_of(third) == "stopped_requires_resume"

    # A failing refresh past the TTL serves the last good observation, stale.
    real_view = dataset_mod.operations_view

    def _boom(**_kwargs: Any) -> Any:
        raise RuntimeError("synthetic refresh failure C:/private/w3.log")

    dataset_mod.operations_view = _boom
    clock.advance(31.0)
    try:
        fourth = service.observe()
    finally:
        dataset_mod.operations_view = real_view

    checks["stale_flag"] = fourth.staleness == "stale"
    checks["stale_problem_recorded"] = (
        list(fourth.observation_problems) == ["observation_refresh_failed"])
    checks["stale_age_honest"] = fourth.age_seconds == 31.0
    checks["stale_keeps_last_good_revision"] = (
        fourth.observation_revision == third.observation_revision)
    public_text = _blob(fourth.to_public())
    checks["stale_public_has_no_exception_text"] = (
        "synthetic refresh failure" not in public_text
        and "C:/private" not in public_text)

    case: dict[str, Any] = {
        "id": "C06",
        "detail": ("running->stopped transition under a frozen clock through "
                   "one observation service: cached within the 30s TTL, "
                   "refreshed past it, stale last-good on refresh failure"),
        "api": "present",
        "checks": checks,
        "first_revision": first.observation_revision,
        "second_revision": second.observation_revision,
        "third_revision": third.observation_revision,
        "fourth_staleness": fourth.staleness,
        "reproduced": not all(checks.values()),
    }
    return case


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        raise SystemExit("usage: w3_reproduce.py <candidate-root> <scratch-root>")
    candidate_root = Path(argv[1]).resolve()
    scratch_root = Path(argv[2]).resolve()
    _prepare(candidate_root)

    import examdata
    import examdata.integration.api.dataset as dataset_mod

    scratch_root.mkdir(parents=True, exist_ok=True)
    cases = [
        _case_c05(scratch_root / "c05", dataset_mod),
        _case_c06(scratch_root / "c06", dataset_mod),
    ]
    verdict = {
        "candidate": str(candidate_root),
        "examdata": str(Path(examdata.__file__).resolve()),
        "cases": cases,
    }
    print(json.dumps(verdict, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
