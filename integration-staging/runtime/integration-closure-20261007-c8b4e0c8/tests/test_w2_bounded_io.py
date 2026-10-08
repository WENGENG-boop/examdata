"""W2 (C03 + C04 + C07) — truly bounded operations IO.

Three containment defects reproduced by the integration review:

* C03 — discovery was unbounded in practice: ``_CheckpointPathWalk``
  materialised a directory's whole ``os.scandir`` stream before consulting
  any budget, so ``max_entries=1`` against a 40-entry directory pulled all 40
  entries; nothing bounded retained paths or nesting depth.
* C04 — the cumulative byte allowance was checked against ``stat`` sizes
  before the read, so a file that grows after ``stat`` (2 -> 16 bytes) slipped
  a full read past ``max_read_bytes=8``, and a refused oversized file offloaded
  its whole payload first.
* C07 — the expected manifest was loaded with ``Path.read_text`` and parsed
  without structural limits: no byte cap, no scope/declaration/id/text
  bounds, and no typed refusal for an oversized manifest.

Every test here fails on the frozen parent tree (RED: the defects reproduce)
and passes on the repaired closure candidate (GREEN). Candidate-only API is
reached through helpers that fail loudly when it is missing, so the frozen
parent yields per-test failures instead of a collection error. Consumption is
measured from the real world: ``os.scandir`` is wrapped to count every entry
actually pulled (boundary probes included) and ``pathlib.Path.open`` - the
open path both trees use - is wrapped to count the payload bytes actually
read, so the asserted bounds describe observed IO, not the implementation's
own counters.
"""
from __future__ import annotations

import inspect
import json
import os
import pathlib
import stat as stat_mod
from pathlib import Path
from typing import Any

import pytest

import b07r2_common as c  # import first: pins EXAMDATA_INTEGRATION_ROOT + asserts candidate origin
from examdata.integration.api import dataset as dataset_mod

c.assert_origin(dataset_mod, "api.dataset")


# --------------------------------------------------------------------------- #
# Lazy access to the candidate-only API: missing API fails the test, never
# the collection.
# --------------------------------------------------------------------------- #
def _require_param(func: Any, name: str, label: str) -> None:
    try:
        parameters = inspect.signature(func).parameters
    except (TypeError, ValueError):  # pragma: no cover - defensive only
        pytest.fail(f"{label} has no introspectable signature")
    if name not in parameters:
        pytest.fail(f"{label} does not accept a {name!r} keyword")


def _budget_module():
    module = getattr(c.operations_pkg, "budget", None)
    if module is None:
        try:
            from examdata.integration.operations import budget as module
        except ImportError:
            pytest.fail("operations.budget (ScanBudget) is not implemented")
    return module


def scan_budget(**fields: Any):
    cls = getattr(_budget_module(), "ScanBudget", None)
    if cls is None:
        pytest.fail("operations.budget.ScanBudget is not implemented")
    return cls(**fields)


def resolve_budget(budget: Any = None, **overrides: Any):
    func = getattr(_budget_module(), "resolve_scan_budget", None)
    if func is None:
        pytest.fail("operations.budget.resolve_scan_budget is not implemented")
    return func(budget, **overrides)


def byte_budget(limit: Any = None, consumed: int = 0):
    cls = getattr(c.checkpoints_mod, "ByteBudget", None)
    if cls is None:
        pytest.fail("checkpoints.ByteBudget is not implemented")
    return cls(limit=limit, consumed=consumed)


def read_budget_error() -> type:
    cls = getattr(c.checkpoints_mod, "ReadBudgetExhaustedError", None)
    if cls is None:
        pytest.fail("checkpoints.ReadBudgetExhaustedError is not implemented")
    return cls


def bounded_bytes(path: str | Path, **kwargs: Any) -> bytes:
    func = getattr(c.checkpoints_mod, "read_bytes_bounded", None)
    if func is None:
        pytest.fail("checkpoints.read_bytes_bounded is not implemented")
    return func(path, **kwargs)


def parse_manifest(document: Any, **kwargs: Any):
    func = getattr(c.published_mod, "parse_manifest", None)
    if func is None:
        pytest.fail("published.parse_manifest is not implemented")
    for name in kwargs:
        _require_param(func, name, "published.parse_manifest")
    return func(document, **kwargs)


def load_manifest(root: str | Path, **kwargs: Any):
    func = getattr(c.published_mod, "load_expected_manifest", None)
    if func is None:
        pytest.fail("published.load_expected_manifest is not implemented")
    for name in kwargs:
        _require_param(func, name, "published.load_expected_manifest")
    return func(root, **kwargs)


def manifest_too_large_error() -> type:
    cls = getattr(c.published_mod, "ExpectedManifestTooLargeError", None)
    if cls is None:
        pytest.fail("published.ExpectedManifestTooLargeError is not implemented")
    return cls


def operations_view(**kwargs: Any):
    func = dataset_mod.operations_view
    for name in kwargs:
        _require_param(func, name, "api.dataset.operations_view")
    return func(**kwargs)


def view_scan(view: Any):
    scan = getattr(view, "scan", None)
    if scan is None:
        pytest.fail("OperationsDataset.scan is not implemented")
    return scan


def view_diagnostics(view: Any) -> dict[str, Any]:
    method = getattr(view, "scan_diagnostics", None)
    if method is None:
        pytest.fail("OperationsDataset.scan_diagnostics is not implemented")
    return method()


def scan_counter(result: Any, name: str) -> int:
    value = getattr(result, name, None)
    if value is None:
        pytest.fail(f"ScanResult.{name} is not implemented")
    return value


# --------------------------------------------------------------------------- #
# Consumption spies: count what the trees really pull/open, not their counters.
# --------------------------------------------------------------------------- #
def _norm(path: Any) -> str:
    return os.path.normcase(os.path.abspath(str(path)))


def _under(path: Any, root: Any) -> bool:
    child = _norm(path)
    parent = _norm(root)
    return child == parent or child.startswith(parent + os.sep)


class _ScandirSpy:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.pulls = 0
        self.fail_dirs: set[str] = set()


class _PullCounter:
    """Counts entries actually yielded by one ``os.scandir`` iterator."""

    def __init__(self, iterator: Any, spy: _ScandirSpy) -> None:
        self._iterator = iterator
        self._spy = spy

    def __iter__(self) -> "_PullCounter":
        return self

    def __next__(self) -> Any:
        entry = next(self._iterator)
        self._spy.pulls += 1
        return entry

    def close(self) -> None:
        close = getattr(self._iterator, "close", None)
        if close is not None:
            close()

    def __enter__(self) -> "_PullCounter":
        return self

    def __exit__(self, *exc: Any) -> bool:
        self.close()
        return False

    def __getattr__(self, name: str) -> Any:
        return getattr(self._iterator, name)


def patch_scandir(monkeypatch: pytest.MonkeyPatch, root: Path) -> _ScandirSpy:
    spy = _ScandirSpy(root)
    real = os.scandir

    def scanning(path: Any = None, *args: Any, **kwargs: Any):
        if path is not None and _under(path, spy.root) and any(
                _norm(path) == _norm(bad) for bad in spy.fail_dirs):
            raise PermissionError(13, "synthetic unreadable directory")
        iterator = real(path, *args, **kwargs)
        if path is not None and _under(path, spy.root):
            return _PullCounter(iterator, spy)
        return iterator

    monkeypatch.setattr(os, "scandir", scanning)
    return spy


class _OpenSpy:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.bytes_read = 0
        self.opened: list[str] = []
        self.grow: dict[str, bytes] = {}
        self.deny: set[str] = set()


class _CountingReader:
    """Counts the payload bytes one read handle actually yields."""

    def __init__(self, handle: Any, spy: _OpenSpy) -> None:
        self._handle = handle
        self._spy = spy

    def read(self, size: int = -1) -> bytes:
        data = self._handle.read(size)
        self._spy.bytes_read += len(data)
        return data

    def __enter__(self) -> "_CountingReader":
        return self

    def __exit__(self, *exc: Any) -> Any:
        return self._handle.__exit__(*exc)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._handle, name)


def patch_opens(monkeypatch: pytest.MonkeyPatch, root: Path) -> _OpenSpy:
    """Wrap ``pathlib.Path.open`` under ``root``; count reads, grow/deny on demand."""
    spy = _OpenSpy(root)
    real_open = pathlib.Path.open

    def opening(self: pathlib.Path, mode: str = "r", *args: Any, **kwargs: Any):
        path = pathlib.Path(self)
        if not _under(path, spy.root):
            return real_open(self, mode, *args, **kwargs)
        key = _norm(path)
        if key in spy.deny:
            raise PermissionError(13, "Permission denied (synthetic)")
        payload = spy.grow.pop(key, None)
        if payload is not None:
            with real_open(path, "wb") as handle:
                handle.write(payload)
        if "r" not in mode or "b" not in mode:
            return real_open(self, mode, *args, **kwargs)
        spy.opened.append(key)
        handle = real_open(self, mode, *args, **kwargs)
        return _CountingReader(handle, spy)

    monkeypatch.setattr(pathlib.Path, "open", opening)
    return spy


# --------------------------------------------------------------------------- #
# Fixtures.
# --------------------------------------------------------------------------- #
def _manifest_document(*scopes: dict[str, Any]) -> dict[str, Any]:
    return {"schema": "operations-expected/1", "scopes": list(scopes)}


def _scope(scope_id: str = "cie-questions", **overrides: Any) -> dict[str, Any]:
    scope: dict[str, Any] = {"id": scope_id, "system": "cie", "kind": "question",
                             "expected": 1}
    scope.update(overrides)
    return scope


def _checkpoint_root(tmp_path: Path, name: str) -> Path:
    root = tmp_path / name
    c.write_json(root / "cie" / "checkpoint.json", c.cie_checkpoint_document())
    return root


def _wrap_raises_path_free(message: str) -> None:
    assert "/" not in message, f"message leaks a path separator: {message!r}"
    assert "\\" not in message, f"message leaks a path separator: {message!r}"


# --------------------------------------------------------------------------- #
# C03 — the discovery budget bounds actual ``os.scandir`` consumption.
# --------------------------------------------------------------------------- #
def test_c03_1_wide_directory_stops_within_entry_budget(tmp_path, monkeypatch):
    root = tmp_path / "ops"
    for index in range(40):
        c.write_bytes(root / f"f{index:02d}.txt", b"junk")
    spy = patch_scandir(monkeypatch, root)

    result = c.scan(root, max_entries=1)

    assert result.entries_seen <= 1
    assert scan_counter(result, "entries_consumed") == spy.pulls == 2
    assert spy.pulls <= 1 + 1
    assert "directory_entries" in result.exhausted
    assert result.truncated is True
    assert result.observations == []


def test_c03_2_exact_entry_budget_is_not_truncated(tmp_path, monkeypatch):
    root = tmp_path / "ops"
    for index in range(3):
        c.write_bytes(root / f"f{index:02d}.txt", b"junk")
    spy = patch_scandir(monkeypatch, root)

    result = c.scan(root, max_entries=3)

    assert result.entries_seen == 3
    assert scan_counter(result, "entries_consumed") == spy.pulls == 3
    assert tuple(result.exhausted) == ()
    assert result.truncated is False
    assert result.observations == []


def test_c03_3_zero_entry_budget_probes_once(tmp_path, monkeypatch):
    root = tmp_path / "ops"
    for index in range(3):
        c.write_bytes(root / f"f{index:02d}.txt", b"junk")
    spy = patch_scandir(monkeypatch, root)

    result = c.scan(root, max_entries=0)

    assert result.entries_seen == 0
    assert scan_counter(result, "entries_consumed") == spy.pulls == 1
    assert spy.pulls <= 0 + 1
    assert "directory_entries" in result.exhausted
    assert result.truncated is True
    assert result.observations == []


def test_c03_4_zero_allowance_levels_still_yield_probe_matches(tmp_path, monkeypatch):
    root = tmp_path / "ops"
    c.write_json(root / "00-scope" / "checkpoint.json", c.cie_checkpoint_document())
    spy = patch_scandir(monkeypatch, root)

    result = c.scan(root, max_entries=1)

    assert [obs.source for obs in result.observations] == ["00-scope:checkpoint.json"]
    assert result.attempted == 1
    assert scan_counter(result, "entries_consumed") == spy.pulls == 2
    assert "directory_entries" in result.exhausted
    assert result.truncated is True


def test_c03_5_depth_budget_refuses_deeper_directories(tmp_path, monkeypatch):
    root = tmp_path / "ops"
    deep = root
    for index in range(9):
        deep = deep / f"d{index}"
    c.write_json(deep / "checkpoint.json", c.cie_checkpoint_document())
    spy = patch_scandir(monkeypatch, root)

    result = c.scan(root, max_depth=8)

    assert result.observations == []
    assert tuple(result.exhausted) == ("depth",)
    assert result.truncated is True
    assert scan_counter(result, "entries_consumed") == spy.pulls == 9
    assert spy.pulls <= 10


def test_c03_6_retained_budget_bounds_buffered_paths(tmp_path, monkeypatch):
    root = tmp_path / "ops"
    for index in range(10):
        c.write_bytes(root / f"f{index:02d}.txt", b"junk")
    spy = patch_scandir(monkeypatch, root)

    result = c.scan(root, max_entries=100, max_retained=2)

    assert scan_counter(result, "retained_paths") == 2
    assert scan_counter(result, "entries_consumed") == spy.pulls == 3
    assert "retained_paths" in result.exhausted
    assert result.truncated is True
    assert result.observations == []


def test_c03_7_skip_budget_bounds_retained_results(tmp_path, monkeypatch):
    root = tmp_path / "ops"
    for index in range(5):
        c.write_bytes(root / f"f{index:02d}" / "checkpoint.json", b"x" * 64)
    spy = patch_opens(monkeypatch, root)

    result = c.scan(root, max_bytes=8, max_skipped=3)

    assert result.skipped == [
        {"source": f"f{index:02d}:checkpoint.json", "reason": "file_too_large"}
        for index in range(3)]
    assert "retained_results" in result.exhausted
    assert result.attempted == 4
    assert result.bytes_read == spy.bytes_read == 36
    assert result.truncated is True
    assert result.observations == []


def test_c03_8_budget_validation_is_strict():
    fields = ("max_entries", "max_files", "max_retained", "max_skipped",
              "max_file_bytes", "max_total_bytes", "max_depth",
              "max_manifest_bytes", "max_scopes", "max_declarations",
              "max_total_declarations", "max_id_len", "max_text_len",
              "max_public_diagnostics")
    for name in fields:
        for bad in (-1, True, "8", None):
            with pytest.raises(ValueError):
                scan_budget(**{name: bad})

    defaults = scan_budget()
    assert set(defaults.as_dict()) == set(fields)
    assert defaults.as_dict()["max_file_bytes"] == 4 * 1024 * 1024
    assert defaults.as_dict()["max_depth"] == 32

    assert scan_budget(max_entries=5).as_dict()["max_entries"] == 5
    assert scan_budget().with_overrides(max_entries=5).max_entries == 5
    with pytest.raises(TypeError):
        scan_budget().with_overrides(no_such_field=3)

    assert resolve_budget(scan_budget(max_entries=5), max_entries=None).max_entries == 5
    assert resolve_budget(None, max_entries=7).max_entries == 7
    assert resolve_budget(scan_budget(max_entries=5), max_files=9).max_files == 9
    with pytest.raises(TypeError):
        resolve_budget("not a budget")


# --------------------------------------------------------------------------- #
# C04 — the cumulative byte allowance is enforced at the actual read.
# --------------------------------------------------------------------------- #
def test_c04_1_growth_after_stat_is_bounded_by_read_time_allowance(tmp_path, monkeypatch):
    root = tmp_path / "ops"
    target = c.write_bytes(root / "grow" / "checkpoint.json", b"{}")
    assert target.stat().st_size == 2
    spy = patch_opens(monkeypatch, root)
    spy.grow[_norm(target)] = b"{" + b"x" * 14 + b"}"

    result = c.scan(root, max_read_bytes=8, max_bytes=32)

    assert spy.bytes_read <= 8 + 1
    assert result.bytes_read == spy.bytes_read == 9
    assert tuple(result.exhausted) == ("read_bytes",)
    assert result.truncated is True
    assert result.observations == []


def test_c04_2_cumulative_budget_crossed_by_one_byte(tmp_path, monkeypatch):
    root = tmp_path / "ops"
    c.write_bytes(root / "a" / "checkpoint.json", b"{}")
    c.write_bytes(root / "b" / "checkpoint.json", b"{}")
    spy = patch_opens(monkeypatch, root)

    result = c.scan(root, max_read_bytes=3, max_bytes=32)

    assert spy.bytes_read == 4
    assert result.bytes_read == spy.bytes_read
    assert result.bytes_read <= 3 + 1
    assert tuple(result.exhausted) == ("read_bytes",)
    assert [obs.source for obs in result.observations] == ["a:checkpoint.json"]
    assert result.truncated is True


def test_c04_3_cumulative_budget_exactly_met(tmp_path, monkeypatch):
    root = tmp_path / "ops"
    c.write_bytes(root / "a" / "checkpoint.json", b"{}")
    c.write_bytes(root / "b" / "checkpoint.json", b"{}")
    spy = patch_opens(monkeypatch, root)

    result = c.scan(root, max_read_bytes=4, max_bytes=32)

    assert spy.bytes_read == 4
    assert result.bytes_read == 4
    assert [obs.source for obs in result.observations] == [
        "a:checkpoint.json", "b:checkpoint.json"]
    assert "read_bytes" not in result.exhausted
    assert result.truncated is False


def test_c04_4_byte_budget_unit_behaviour():
    unlimited = byte_budget()
    assert unlimited.limit is None
    assert unlimited.remaining is None
    assert unlimited.exhausted is False
    assert unlimited.consume(5) == 5
    assert unlimited.remaining is None

    budget = byte_budget(limit=5)
    assert budget.remaining == 5
    assert budget.exhausted is False
    assert budget.consume(3) == 3
    assert budget.remaining == 2
    budget.consume(4)
    assert budget.remaining == 0
    assert budget.exhausted is True
    assert budget.to_dict() == {"limit": 5, "consumed": 7}

    for bad_limit in (-1, True, "8"):
        with pytest.raises(ValueError):
            byte_budget(limit=bad_limit)
    with pytest.raises(ValueError):
        byte_budget(limit=3, consumed=-1)
    with pytest.raises(ValueError):
        byte_budget(limit=3, consumed=True)
    for bad_amount in (-1, True, "1"):
        with pytest.raises(ValueError):
            byte_budget(limit=5).consume(bad_amount)


def test_c04_5_shared_budget_refuses_later_and_spent_reads(tmp_path, monkeypatch):
    root = tmp_path / "ops"
    first = c.write_bytes(root / "a.bin", b"abcd")
    second = c.write_bytes(root / "b.bin", b"xy")

    shared = byte_budget(limit=5)
    assert bounded_bytes(first, max_bytes=100, budget=shared) == b"abcd"
    assert shared.consumed == 4
    with pytest.raises(read_budget_error()) as info:
        bounded_bytes(second, max_bytes=100, budget=shared)
    assert shared.consumed == 6
    assert info.value.bytes_read == 2

    spy = patch_opens(monkeypatch, root)
    spent = byte_budget(limit=3, consumed=3)
    with pytest.raises(read_budget_error()):
        bounded_bytes(second, max_bytes=100, budget=spent)
    assert spy.opened == []
    assert spent.consumed == 3


# --------------------------------------------------------------------------- #
# C07 — bounded manifest loading and structure.
# --------------------------------------------------------------------------- #
def test_c07_1_custom_scan_budget_parses_a_document():
    document = _manifest_document(_scope("a"), _scope("b"))
    manifest = parse_manifest(document, budget=scan_budget(max_scopes=2))
    assert [scope.id for scope in manifest.scopes] == ["a", "b"]


def test_c07_2_scope_count_limit_is_enforced():
    document = _manifest_document(_scope("a"), _scope("b"))
    with pytest.raises(ValueError) as info:
        parse_manifest(document, budget=scan_budget(max_scopes=1))
    _wrap_raises_path_free(str(info.value))


def test_c07_3_per_scope_declaration_limit_is_enforced():
    scope = _scope("a", exclusions=[
        {"public_id": "p1", "reason": "r"},
        {"public_id": "p2", "reason": "r"}])
    with pytest.raises(ValueError) as info:
        parse_manifest(_manifest_document(scope),
                       budget=scan_budget(max_declarations=1))
    _wrap_raises_path_free(str(info.value))


def test_c07_4_total_declaration_limit_is_enforced():
    scope_a = _scope("a", exclusions=[{"public_id": "p1", "reason": "r"}])
    scope_b = _scope("b", exclusions=[{"public_id": "p2", "reason": "r"}])
    with pytest.raises(ValueError) as info:
        parse_manifest(_manifest_document(scope_a, scope_b),
                       budget=scan_budget(max_total_declarations=1))
    _wrap_raises_path_free(str(info.value))


def test_c07_5_id_length_limit_is_enforced():
    with pytest.raises(ValueError) as info:
        parse_manifest(_manifest_document(_scope("scope-1")),
                       budget=scan_budget(max_id_len=4))
    _wrap_raises_path_free(str(info.value))


def test_c07_6_text_length_limit_is_enforced():
    scope = _scope("a", note="0123456789")
    with pytest.raises(ValueError) as info:
        parse_manifest(_manifest_document(scope), budget=scan_budget(max_text_len=5))
    _wrap_raises_path_free(str(info.value))


def test_c07_7_document_depth_limit_is_enforced():
    scope = _scope("a", extras={"a": {"b": {"c": 1}}})
    with pytest.raises(ValueError) as info:
        parse_manifest(_manifest_document(scope), budget=scan_budget(max_depth=3))
    _wrap_raises_path_free(str(info.value))


def test_c07_8_oversized_manifest_stops_at_cap_plus_one(tmp_path, monkeypatch):
    root = tmp_path / "ops"
    payload = b"{" + b" " * 199
    assert len(payload) == 200
    c.write_bytes(root / c.MANIFEST_NAME, payload)
    spy = patch_opens(monkeypatch, root)

    with pytest.raises(manifest_too_large_error()) as info:
        load_manifest(root, max_bytes=64)

    assert info.value.bytes_read == 65
    assert spy.bytes_read == 65
    assert isinstance(info.value, OSError) is False
    assert isinstance(info.value, ValueError) is False


def test_c07_9_missing_manifest_is_none(tmp_path, monkeypatch):
    root = tmp_path / "ops"
    root.mkdir(parents=True)
    spy = patch_opens(monkeypatch, root)

    assert load_manifest(root, budget=scan_budget()) is None
    assert spy.opened == []


def test_c07_10_valid_manifest_loads_without_read_text(tmp_path, monkeypatch):
    root = tmp_path / "ops"
    c.write_json(root / c.MANIFEST_NAME, _manifest_document(_scope()))

    def forbidden_read_text(self, *args, **kwargs):
        raise AssertionError("load_expected_manifest must not use Path.read_text")

    monkeypatch.setattr(pathlib.Path, "read_text", forbidden_read_text)

    manifest = load_manifest(root)
    assert [scope.id for scope in manifest.scopes] == ["cie-questions"]
    assert manifest.source_label == c.MANIFEST_NAME

    manifest = load_manifest(root, budget=scan_budget())
    assert [scope.id for scope in manifest.scopes] == ["cie-questions"]


def test_c07_11_manifest_open_failure_is_oserror(tmp_path, monkeypatch):
    root = tmp_path / "ops"
    manifest_path = c.write_json(root / c.MANIFEST_NAME, _manifest_document(_scope()))
    spy = patch_opens(monkeypatch, root)
    spy.deny.add(_norm(manifest_path))

    with pytest.raises(OSError) as info:
        load_manifest(root)

    assert not isinstance(info.value, manifest_too_large_error())
    assert spy.bytes_read == 0


# --------------------------------------------------------------------------- #
# Operations view — diagnostics and the sanitized public projection.
# --------------------------------------------------------------------------- #
def test_view_1_missing_root_reported_not_raised(tmp_path):
    view = operations_view(entries=[], root=tmp_path / "nope")
    assert view.root_kind == "missing"
    assert [problem["code"] for problem in view.problems] == ["operations_root_missing"]
    assert getattr(view, "scan", None) is None


def test_view_2_truncated_scan_diagnostics_and_projection(tmp_path, monkeypatch):
    root = tmp_path / "ops"
    for index in range(40):
        c.write_bytes(root / f"f{index:02d}.txt", b"junk")
    spy = patch_scandir(monkeypatch, root)

    view = operations_view(entries=[], root=root, budget=scan_budget(max_entries=1))
    scan = view_scan(view)
    diagnostics = view_diagnostics(view)

    assert diagnostics["truncation_reason"] == "directory_entries"
    assert diagnostics["truncated"] is True
    assert diagnostics["snapshot_complete"] is False
    assert diagnostics["entries_consumed"] == spy.pulls == 2
    assert diagnostics["entries_consumed"] <= 1 + 1
    assert diagnostics["budgets"]["max_entries"] == 1
    assert scan.entries_consumed == diagnostics["entries_consumed"]

    public = view.to_public()
    block = public["checkpoints"]["scan"]
    assert block["truncation_reason"] == "directory_entries"
    assert block["truncated"] is True
    assert block["snapshot_complete"] is False
    text = json.dumps(public)
    assert str(root) not in text
    assert root.as_posix() not in text
    assert json.dumps(str(root))[1:-1] not in text


def test_view_3_manifest_failures_map_to_problem_codes(tmp_path):
    missing_root = _checkpoint_root(tmp_path, "missing")
    view = operations_view(entries=[], root=missing_root)
    assert view.root_kind == "configured"
    assert [p["code"] for p in view.problems] == ["expected_manifest_missing"]
    assert view.published is None

    invalid_root = _checkpoint_root(tmp_path, "invalid")
    c.write_bytes(invalid_root / c.MANIFEST_NAME, b"{od")
    view = operations_view(entries=[], root=invalid_root)
    assert [p["code"] for p in view.problems] == ["expected_manifest_invalid"]
    assert view.published is None

    large_root = _checkpoint_root(tmp_path, "large")
    c.write_bytes(large_root / c.MANIFEST_NAME, b"{" + b" " * 199)
    view = operations_view(entries=[], root=large_root,
                           budget=scan_budget(max_manifest_bytes=64))
    assert [p["code"] for p in view.problems] == ["expected_manifest_too_large"]
    assert view.published is None


def test_view_4_complete_snapshot_without_overrides(tmp_path):
    root = _checkpoint_root(tmp_path, "clean")

    view = operations_view(entries=[], root=root)
    view_scan(view)
    diagnostics = view_diagnostics(view)

    assert diagnostics["truncated"] is False
    assert diagnostics["truncation_reason"] is None
    assert diagnostics["snapshot_complete"] is True
    assert diagnostics["exhausted"] == []
    assert diagnostics["bytes_read"] > 0
    assert diagnostics["budgets"]["max_entries"] == 4096
    assert diagnostics["budgets"]["max_manifest_bytes"] == 1024 * 1024


def test_view_5_budget_overrides_reach_the_scan_result(tmp_path):
    root = _checkpoint_root(tmp_path, "budgeted")
    budget = scan_budget(max_entries=7, max_files=3, max_skipped=2,
                         max_total_bytes=100, max_file_bytes=50,
                         max_retained=9, max_depth=4)

    result = c.scan(root, budget=budget)

    assert result.budgets["max_entries"] == 7
    assert result.budgets["max_files"] == 3
    assert result.budgets["max_skipped"] == 2
    assert result.budgets["max_total_bytes"] == 100
    assert result.budgets["max_file_bytes"] == 50
    assert result.budgets["max_retained"] == 9
    assert result.budgets["max_depth"] == 4

    overridden = c.scan(root, budget=budget, max_entries=5)
    assert overridden.budgets["max_entries"] == 5
    assert overridden.budgets["max_files"] == 3


# --------------------------------------------------------------------------- #
# Containment — reads stay inside the root, on regular files, without raising.
# --------------------------------------------------------------------------- #
def test_containment_1_non_regular_file_refused_before_open(tmp_path, monkeypatch):
    root = tmp_path / "ops"
    c.write_bytes(root / "dev" / "checkpoint.json", b"{}")
    c.write_json(root / "ok" / "checkpoint.json", c.cie_checkpoint_document())
    spy = patch_opens(monkeypatch, root)

    real_stat = os.stat

    def fake_stat(path, *args, **kwargs):
        info = real_stat(path, *args, **kwargs)
        candidate_path = pathlib.Path(str(path))
        if (candidate_path.name == "checkpoint.json"
                and candidate_path.parent.name == "dev"
                and _under(candidate_path, root)):
            fields = list(info)
            fields[0] = stat_mod.S_IFCHR | 0o666
            return os.stat_result(fields)
        return info

    monkeypatch.setattr(os, "stat", fake_stat)

    result = c.scan(root)

    assert result.skipped == [
        {"source": "dev:checkpoint.json", "reason": "not_a_regular_file"}]
    assert [obs.source for obs in result.observations] == ["ok:checkpoint.json"]
    assert not any(pathlib.Path(opened).parent.name == "dev" for opened in spy.opened)


def test_containment_2_native_symlink_escape_is_refused(tmp_path, monkeypatch):
    root = tmp_path / "ops"
    (root / "escape").mkdir(parents=True)
    outside = c.write_json(tmp_path / "outside-checkpoint.json",
                           c.cie_checkpoint_document())
    target = root / "escape" / "checkpoint.json"
    try:
        os.symlink(outside, target)
    except OSError as exc:
        pytest.skip(f"native symlink creation blocked ({exc.__class__.__name__}: {exc}); "
                    "the unit-level resolver seam test covers containment")
    spy = patch_opens(monkeypatch, root)

    result = c.scan(root)

    assert result.skipped == [
        {"source": "escape:checkpoint.json", "reason": "outside_root"}]
    assert result.observations == []
    assert spy.opened == []


def test_containment_3_resolver_seam_refuses_root_escape(tmp_path, monkeypatch):
    real_is_within = getattr(c.jobs_mod, "is_within", None)
    if real_is_within is None:
        pytest.fail("jobs.is_within containment hook is not implemented")
    root = tmp_path / "ops"
    c.write_json(root / "escape" / "checkpoint.json", c.cie_checkpoint_document())
    spy = patch_opens(monkeypatch, root)

    def fake_is_within(path, base):
        if pathlib.Path(str(path)).parent.name == "escape":
            return False
        return real_is_within(path, base)

    monkeypatch.setattr(c.jobs_mod, "is_within", fake_is_within, raising=False)

    result = c.scan(root)

    assert result.skipped == [
        {"source": "escape:checkpoint.json", "reason": "outside_root"}]
    assert result.observations == []
    assert spy.opened == []


def test_containment_4_bad_json_is_an_observation_not_a_skip(tmp_path):
    root = tmp_path / "ops"
    c.write_bytes(root / "bad" / "checkpoint.json", b"{od")

    result = c.scan(root)

    assert len(result.observations) == 1
    assert "json_unreadable" in result.observations[0].problems
    assert result.skipped == []
    assert result.truncated is False


def test_containment_5_open_failure_is_an_unreadable_skip(tmp_path, monkeypatch):
    root = tmp_path / "ops"
    target = c.write_json(root / "perm" / "checkpoint.json",
                          c.cie_checkpoint_document())
    spy = patch_opens(monkeypatch, root)
    spy.deny.add(_norm(target))

    result = c.scan(root)

    assert result.skipped == [{"source": "perm:checkpoint.json", "reason": "unreadable"}]
    assert result.observations == []
    assert result.truncated is False
    assert spy.bytes_read == 0


def test_containment_6_unreadable_directory_is_reported_not_dropped(tmp_path, monkeypatch):
    root = tmp_path / "ops"
    locked = root / "locked"
    (locked / "inner").mkdir(parents=True)
    c.write_json(locked / "inner" / "checkpoint.json", c.cie_checkpoint_document())
    c.write_json(root / "ok" / "checkpoint.json", c.cie_checkpoint_document())
    spy = patch_scandir(monkeypatch, root)
    spy.fail_dirs.add(str(locked))

    result = c.scan(root)

    assert "unreadable_directory" in result.exhausted
    assert result.truncated is True
    assert [obs.source for obs in result.observations] == ["ok:checkpoint.json"]


def test_containment_7_missing_root_scans_to_an_empty_result(tmp_path):
    result = c.scan(tmp_path / "does-not-exist")

    assert result.observations == []
    assert result.skipped == []
    assert result.truncated is False
    assert tuple(result.exhausted) == ()
