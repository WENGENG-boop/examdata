"""W2 C03/C04/C07 reproduction script (private run only).

Runs the three confirmed bounded-IO defect scenarios from the integration
review against a given candidate root and prints a JSON verdict.
``reproduced`` means *the defect is present* in that tree, so the frozen
parent reports ``true`` for every case and the repaired candidate reports
``false``:

* C03 - a flat directory scanned with ``max_entries=1`` must not pull more
  entries from ``os.scandir`` than the allowance plus its single documented
  probe (``max_entries + 1``). The defect materialises the whole directory
  before applying the budget.
* C04 - a checkpoint that grows between ``stat`` and open must not be read
  beyond the read-time allowance plus the one overflow-probe byte. The defect
  reads the whole grown file because the bound came from the stale ``stat``
  size.
* C07 - an oversized expected manifest must stop at the manifest cap plus one
  probe byte and raise the typed too-large error. The defect reads the whole
  file and fails later as a generic JSON error.

Usage:
    python -B w2_reproduce.py <candidate-root> <scratch-root>

The scratch root is created if missing; the ``c03``/``c04``/``c07`` subtrees
are rebuilt from scratch so one scratch root can serve both verdict runs.
The script always exits 0 when it ran; a crash (import error, missing API)
is a script failure, not a verdict.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any


def _prepare(candidate_root: Path) -> None:
    src = candidate_root / "src"
    if not src.is_dir():
        raise SystemExit(f"candidate root has no src/ directory: {candidate_root}")
    sys.path.insert(0, str(src))
    os.environ["EXAMDATA_INTEGRATION_ROOT"] = str(candidate_root)


def _norm(path: str | os.PathLike[str]) -> str:
    return os.path.normcase(os.path.abspath(str(path)))


class _ScandirSpy:
    """Wrap ``os.scandir`` and count successfully yielded entries."""

    def __init__(self) -> None:
        self.pulls = 0
        self._real = os.scandir

    def __call__(self, *args: Any, **kwargs: Any) -> "_ScandirProxy":
        return _ScandirProxy(self._real(*args, **kwargs), self)


class _ScandirProxy:
    def __init__(self, inner: Any, spy: _ScandirSpy) -> None:
        self._inner = inner
        self._spy = spy

    def __iter__(self) -> "_ScandirProxy":
        return self

    def __next__(self) -> Any:
        entry = next(self._inner)
        self._spy.pulls += 1
        return entry

    def close(self) -> None:
        self._inner.close()

    def __enter__(self) -> "_ScandirProxy":
        return self

    def __exit__(self, *exc: Any) -> bool:
        self.close()
        return False

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class _CountingHandle:
    """Proxy one open handle and add every pulled chunk to the spy."""

    def __init__(self, inner: Any, spy: "_OpenSpy") -> None:
        self._inner = inner
        self._spy = spy

    def _count(self, data: Any) -> None:
        if isinstance(data, str):
            self._spy.bytes_read += len(data.encode("utf-8", "replace"))
        elif isinstance(data, (bytes, bytearray)):
            self._spy.bytes_read += len(data)

    def read(self, *args: Any) -> Any:
        data = self._inner.read(*args)
        self._count(data)
        return data

    def read1(self, *args: Any) -> Any:
        data = self._inner.read1(*args)
        self._count(data)
        return data

    def __iter__(self) -> "_CountingHandle":
        return self

    def __next__(self) -> Any:
        chunk = next(self._inner)
        self._count(chunk)
        return chunk

    def __enter__(self) -> "_CountingHandle":
        return self

    def __exit__(self, *exc: Any) -> bool:
        self.close()
        return False

    def close(self) -> None:
        self._inner.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class _OpenSpy:
    """Wrap ``pathlib.Path.open``: count read bytes, optionally grow a file.

    ``count_root`` (when set) restricts counting to paths under that root;
    ``grow_path``/``grow_payload`` rewrite that file with larger content just
    before its first read-mode open, simulating growth after the scan's stat.
    """

    def __init__(self, real: Any) -> None:
        self._real = real
        self.bytes_read = 0
        self.count_root: str | None = None
        self.grow_path: str | None = None
        self.grow_payload: bytes = b""
        self.grew = False

    def open(self, path_self: Path, mode: str = "r", *args: Any,
             **kwargs: Any) -> Any:
        target = _norm(path_self)
        reading = mode == "r" or mode.startswith("r")
        if reading and self.grow_path == target and not self.grew:
            self.grew = True
            with self._real(path_self, "wb") as handle:
                handle.write(self.grow_payload)
        handle = self._real(path_self, mode, *args, **kwargs)
        counting = reading and (
            self.count_root is None
            or target == self.count_root
            or target.startswith(self.count_root + os.sep))
        return _CountingHandle(handle, self) if counting else handle


def _patch_open() -> tuple[_OpenSpy, Any]:
    real_open = Path.open
    spy = _OpenSpy(real_open)

    def _wrapped_open(self_path: Path, *args: Any, **kwargs: Any) -> Any:
        return spy.open(self_path, *args, **kwargs)

    Path.open = _wrapped_open
    return spy, real_open


def _case_c03(scratch: Path, scan_checkpoint_root: Any) -> dict[str, Any]:
    root = scratch / "ops"
    root.mkdir(parents=True)
    for index in range(40):
        (root / f"f{index:02d}.txt").write_bytes(b"junk")
    max_entries = 1

    spy = _ScandirSpy()
    real_scandir = os.scandir
    os.scandir = spy
    result = None
    error: str | None = None
    try:
        try:
            result = scan_checkpoint_root(root, max_entries=max_entries)
        except Exception as exc:  # recorded in the verdict, never swallowed
            error = type(exc).__name__
    finally:
        os.scandir = real_scandir

    probe_allowance = max_entries + 1
    case: dict[str, Any] = {
        "id": "C03",
        "detail": f"40-entry flat tree scanned with max_entries={max_entries}",
        "actual_scandir_pulls": spy.pulls,
        "probe_allowance": probe_allowance,
        "reproduced": spy.pulls > probe_allowance,
    }
    if result is not None:
        case.update(
            entries_seen=result.entries_seen,
            entries_consumed=getattr(result, "entries_consumed", None),
            exhausted=list(result.exhausted),
            truncated=result.truncated,
            observations=len(result.observations),
        )
    if error is not None:
        case["scan_error"] = error
    return case


def _case_c04(scratch: Path, scan_checkpoint_root: Any) -> dict[str, Any]:
    root = scratch / "ops" / "grow"
    root.mkdir(parents=True)
    target = root / "checkpoint.json"
    target.write_bytes(b"{}")  # 2 bytes when the scan stats it
    payload = b"{" + b"x" * 14 + b"}"  # 16 bytes when the scan reads it
    max_read_bytes = 8
    max_bytes = 32

    spy, real_open = _patch_open()
    spy.grow_path = _norm(target)
    spy.grow_payload = payload
    result = None
    error: str | None = None
    try:
        try:
            result = scan_checkpoint_root(root, max_read_bytes=max_read_bytes,
                                          max_bytes=max_bytes)
        except Exception as exc:  # recorded in the verdict, never swallowed
            error = type(exc).__name__
    finally:
        Path.open = real_open

    probe_allowance = max_read_bytes + 1
    case: dict[str, Any] = {
        "id": "C04",
        "detail": (f"2-byte checkpoint grown to {len(payload)} bytes after "
                   f"stat; scan with max_read_bytes={max_read_bytes}, "
                   f"max_bytes={max_bytes}"),
        "actual_bytes_read": spy.bytes_read,
        "probe_allowance": probe_allowance,
        "grew_after_stat": spy.grew,
        "reproduced": spy.bytes_read > probe_allowance,
    }
    if result is not None:
        case.update(
            bytes_read=result.bytes_read,
            exhausted=list(result.exhausted),
            truncated=result.truncated,
            observations=len(result.observations),
        )
    if error is not None:
        case["scan_error"] = error
    return case


def _case_c07(scratch: Path, load_expected_manifest: Any) -> dict[str, Any]:
    root = scratch / "ops"
    root.mkdir(parents=True)
    payload = b"{" + b" " * 199
    (root / "expected-manifest.json").write_bytes(payload)

    budget_api = "present"
    try:
        from examdata.integration.operations.budget import ScanBudget
    except ImportError:
        ScanBudget = None  # noqa: N806 - absent API is the point of the case
        budget_api = "absent"
    try:
        from examdata.integration.operations.published import (
            ExpectedManifestTooLargeError,
        )
    except ImportError:
        ExpectedManifestTooLargeError = None  # noqa: N806

    cap = 64
    spy, real_open = _patch_open()
    spy.count_root = _norm(root)
    outcome = "loaded"
    error_obj: BaseException | None = None
    try:
        try:
            if budget_api == "present":
                load_expected_manifest(
                    root, budget=ScanBudget(max_manifest_bytes=cap))
            else:
                load_expected_manifest(root)
        except Exception as exc:  # recorded in the verdict, never swallowed
            outcome = "raised"
            error_obj = exc
    finally:
        Path.open = real_open

    typed_too_large = (
        ExpectedManifestTooLargeError is not None
        and error_obj is not None
        and isinstance(error_obj, ExpectedManifestTooLargeError))
    case: dict[str, Any] = {
        "id": "C07",
        "detail": (f"{len(payload)}-byte manifest; budget_api={budget_api}; "
                   f"manifest cap {cap} bytes"),
        "actual_bytes_read": spy.bytes_read,
        "probe_allowance": cap + 1,
        "outcome": outcome,
        "error_type": type(error_obj).__name__ if error_obj is not None else None,
        "error_bytes_read": getattr(error_obj, "bytes_read", None),
        "typed_too_large": typed_too_large,
        "reproduced": not (typed_too_large and 0 < spy.bytes_read <= cap + 1),
    }
    return case


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        raise SystemExit(
            "usage: w2_reproduce.py <candidate-root> <scratch-root>")
    candidate_root = Path(argv[1]).resolve()
    scratch_root = Path(argv[2]).resolve()
    _prepare(candidate_root)

    import examdata
    from examdata.integration.operations.jobs import scan_checkpoint_root
    from examdata.integration.operations.published import load_expected_manifest

    for name in ("c03", "c04", "c07"):
        stale = scratch_root / name
        if stale.exists():
            shutil.rmtree(stale)
    scratch_root.mkdir(parents=True, exist_ok=True)

    cases = [
        _case_c03(scratch_root / "c03", scan_checkpoint_root),
        _case_c04(scratch_root / "c04", scan_checkpoint_root),
        _case_c07(scratch_root / "c07", load_expected_manifest),
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
