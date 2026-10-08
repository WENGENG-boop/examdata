"""B07R2 STEP 2 (F3) — scan budgets bound discovery and attempts, not just successes.

Required semantics (so the frozen tree fails RED here):

* ``max_files`` bounds *attempted* checkpoint files: a file that is skipped
  (oversized, unreadable, budget-stopped) still consumes the budget, and
  exhaustion is signalled in ``exhausted``;
* a directory-entry budget bounds discovery itself (no full ``rglob``
  materialisation before the limits apply) with its own exhaustion signal;
* a retained-result budget bounds the ``skipped`` list (memory) with its own
  signal;
* per-file and cumulative byte budgets bound reads, and the consumed byte
  count is reported;
* every exhaustion sets ``truncated=True`` and names the exhausted budget in
  ``exhausted``; traversal order stays deterministic (full-path
  lexicographic, as the frozen walker produced).

All trees are synthetic and portable; boundedness is proven by counted
budgets, never by wall-clock thresholds.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import b07r2_common as c
from examdata.integration.operations.checkpoints import CheckpointReadError


def _oversize_tree(tmp_path: Path) -> Path:
    root = tmp_path / "ops"
    for name in ("a", "b", "c"):
        c.write_bytes(root / name / "checkpoint.json", b"{}")
    return root


def test_f3_review_reproduction_attempt_budget_counts_skipped_files(tmp_path):
    """The review's exact F3 reproduction: three ``{}`` files, max_files=1,
    max_bytes=1. v1 reports 0 observations, 3 skipped, truncated=False."""
    root = _oversize_tree(tmp_path)
    result = c.scan(root, max_files=1, max_bytes=1)
    assert result.truncated is True, (
        f"three checkpoint files with max_files=1 reported "
        f"observations={len(result.observations)} skipped={len(result.skipped)} "
        f"truncated={result.truncated!r}: the budget counted only successes")
    assert len(result.skipped) == 1, (
        f"the attempt budget did not stop the scan: skipped={result.skipped!r}")
    assert getattr(result, "attempted", None) == 1
    assert "attempted_files" in getattr(result, "exhausted", ())
    assert getattr(result, "bytes_read", 0) <= 2  # never an unbounded read


def test_f3_attempt_budget_exact_and_over_limit(tmp_path):
    root = tmp_path / "ops"
    sizes = {}
    for name in ("a", "b", "c"):
        path = c.write_json(root / name / "checkpoint.json",
                            c.cie_checkpoint_document(current_subject=f"subject-{name}"))
        sizes[name] = path.stat().st_size

    over = c.scan(root, max_files=2)
    assert over.truncated is True, (
        f"3 files with max_files=2 reported truncated={over.truncated!r}")
    assert [obs.source for obs in over.observations] == ["a:checkpoint.json",
                                                        "b:checkpoint.json"]
    assert getattr(over, "attempted", None) == 2
    assert "attempted_files" in getattr(over, "exhausted", ())
    assert getattr(over, "bytes_read", None) == sizes["a"] + sizes["b"]

    exact = c.scan(root, max_files=3)
    assert exact.truncated is False
    assert getattr(exact, "exhausted", None) == ()
    assert getattr(exact, "attempted", None) == 3
    assert getattr(exact, "bytes_read", None) == sum(sizes.values())
    assert len(exact.observations) == 3


def test_f3_directory_entry_budget_bounds_discovery(tmp_path):
    root = tmp_path / "ops"
    for index in range(24):
        for junk in ("notes.txt", "raw.log"):
            c.write_bytes(root / f"d{index:02d}" / junk, b"irrelevant")
    c.write_json(root / "zz-scope" / "checkpoint.json", c.cie_checkpoint_document())

    bounded = c.scan(root, max_entries=10)
    assert "directory_entries" in getattr(bounded, "exhausted", ())
    assert bounded.truncated is True
    assert getattr(bounded, "entries_seen", 10 ** 9) <= 10
    assert bounded.observations == []

    full = c.scan(root, max_entries=100000)
    assert full.truncated is False
    assert [obs.source for obs in full.observations] == ["zz-scope:checkpoint.json"]


def test_f3_retained_result_budget_bounds_skips(tmp_path):
    root = tmp_path / "ops"
    for name in ("a", "b", "c", "d", "e"):
        c.write_bytes(root / name / "checkpoint.json", b"{}")
    result = c.scan(root, max_files=100, max_bytes=1, max_skipped=2)
    assert "retained_results" in getattr(result, "exhausted", ())
    assert len(result.skipped) == 2, f"skipped={result.skipped!r}"
    assert result.truncated is True
    assert result.observations == []


def test_f3_oversized_file_is_skipped_and_counts_are_reported(tmp_path):
    root = tmp_path / "ops"
    payload = b"{\"pad\": \"" + b"x" * 64 + b"\"}"
    c.write_bytes(root / "big" / "checkpoint.json", payload)
    result = c.scan(root, max_bytes=8)
    assert result.truncated is False
    assert result.skipped == [{"source": "big:checkpoint.json",
                               "reason": "file_too_large"}]
    assert result.observations == []
    assert getattr(result, "bytes_read", 0) <= 9  # no unbounded read


def test_f3_read_byte_budget_bounds_cumulative_reads(tmp_path):
    root = tmp_path / "ops"
    size_a = c.write_json(root / "a" / "checkpoint.json",
                          c.cie_checkpoint_document()).stat().st_size
    size_b = c.write_json(root / "b" / "checkpoint.json",
                          c.cie_checkpoint_document()).stat().st_size

    bounded = c.scan(root, max_read_bytes=size_a)
    assert getattr(bounded, "bytes_read", None) == size_a
    assert [obs.source for obs in bounded.observations] == ["a:checkpoint.json"]
    assert bounded.truncated is True
    assert "read_bytes" in getattr(bounded, "exhausted", ())

    exact = c.scan(root, max_read_bytes=size_a + size_b)
    assert exact.truncated is False
    assert getattr(exact, "exhausted", None) == ()
    assert getattr(exact, "bytes_read", None) == size_a + size_b
    assert len(exact.observations) == 2


def test_f3_bounded_read_refuses_an_oversized_file(tmp_path):
    """The read path itself must be bounded, not only the pre-read size check."""
    path = c.write_bytes(tmp_path / "big" / "checkpoint.json",
                         b"{" + b"x" * 64 + b"}")
    error_cls = c.bounded_read_error()
    with pytest.raises(error_cls):
        c.bounded_read(path, source="big:checkpoint.json", max_bytes=8)


def test_f3_unreadable_file_is_an_attempted_file(tmp_path, monkeypatch):
    root = tmp_path / "ops"
    c.write_json(root / "a" / "checkpoint.json", c.cie_checkpoint_document())
    c.write_json(root / "b" / "checkpoint.json",
                 c.cie_checkpoint_document(current_subject="other"))
    real = getattr(c.jobs_mod, "read_checkpoint_bounded", None) or c.jobs_mod.read_checkpoint

    def fake(path, **kwargs):
        if Path(path).parent.name == "b":
            raise CheckpointReadError("synthetic: unreadable checkpoint")
        return real(path, **kwargs)

    monkeypatch.setattr(c.jobs_mod, "read_checkpoint", fake)
    monkeypatch.setattr(c.jobs_mod, "read_checkpoint_bounded", fake, raising=False)
    result = c.scan(root)
    assert result.skipped == [{"source": "b:checkpoint.json", "reason": "unreadable"}]
    assert [obs.source for obs in result.observations] == ["a:checkpoint.json"]
    assert result.truncated is False
    assert getattr(result, "attempted", None) == 2


def test_f3_walk_order_is_deterministic_and_lazy(tmp_path):
    root = tmp_path / "ops"
    for rel in ("a-b/checkpoint.json", "a/checkpoint.json",
                "a/inner/checkpoint.json", "b/checkpoint.json",
                "zz/checkpoint.json"):
        c.write_json(root / rel, c.cie_checkpoint_document())
    c.write_bytes(root / "a" / "notes.txt", b"junk")
    expected = sorted(p.relative_to(root).as_posix()
                      for p in root.rglob("checkpoint.json"))
    walked = [Path(p).relative_to(root).as_posix() for p in c.listwalker(root)]
    assert walked == expected

    try:
        iterator = c.checkpoints_mod.iter_checkpoint_paths(root, max_entries=3)
    except TypeError as exc:
        pytest.fail(f"bounded walker API missing: {exc}")
    assert hasattr(iterator, "__next__"), (
        "the walker must be lazy, not a fully materialised list")
    first = next(iterator)
    assert Path(first).name == "checkpoint.json"
