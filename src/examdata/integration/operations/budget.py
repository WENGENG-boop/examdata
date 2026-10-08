"""One validated configuration object for bounded operations reads (C03/C04/C07).

Every bound the operations adapters apply - discovery entries, retained
paths, file count, single-file and cumulative byte caps, manifest caps, and
the structural limits of manifest parsing - lives on :class:`ScanBudget`, a
frozen, validated dataclass. Callers build one object (or take the defaults)
and every bounded read derives its allowance from it *at read time*, so
operators see the effective bounds in ``checkpoints["scan"]["budgets"]``
instead of guessing which constant won.

Validation is strict and path-free: a bound must be a plain non-negative
``int`` (booleans and ``None`` are rejected), so a misconfigured budget fails
loudly at construction with a message that carries no filesystem detail.
Nothing here reads or writes; the object is inert data.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, replace

_BUDGET_FIELDS = (
    "max_entries",
    "max_files",
    "max_retained",
    "max_skipped",
    "max_file_bytes",
    "max_total_bytes",
    "max_depth",
    "max_manifest_bytes",
    "max_scopes",
    "max_declarations",
    "max_total_declarations",
    "max_id_len",
    "max_text_len",
    "max_public_diagnostics",
)


@dataclass(frozen=True)
class ScanBudget:
    """Validated, immutable bounds for one operations scan.

    Defaults are the production posture: entries 4096, retained paths 4096,
    files 256, skipped results 64, 4 MiB per file, 32 MiB per scan, depth 32,
    1 MiB manifest, 512 scopes / 4096 declarations per scope / 8192 total,
    256-char ids, 1024-char text fields, 64 public diagnostics.
    """

    max_entries: int = 4096
    max_files: int = 256
    max_retained: int = 4096
    max_skipped: int = 64
    max_file_bytes: int = 4 * 1024 * 1024
    max_total_bytes: int = 32 * 1024 * 1024
    max_depth: int = 32
    max_manifest_bytes: int = 1024 * 1024
    max_scopes: int = 512
    max_declarations: int = 4096
    max_total_declarations: int = 8192
    max_id_len: int = 256
    max_text_len: int = 1024
    max_public_diagnostics: int = 64

    def __post_init__(self) -> None:
        for name in _BUDGET_FIELDS:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(
                    f"scan budget field {name!r} must be an integer")
            if value < 0:
                raise ValueError(
                    f"scan budget field {name!r} must not be negative")

    def as_dict(self) -> dict[str, int]:
        """The effective bounds, ready for a serialised scan report."""
        return {name: getattr(self, name) for name in _BUDGET_FIELDS}

    def with_overrides(self, **overrides: int) -> "ScanBudget":
        """A copy with the named fields replaced; unknown names raise."""
        if not overrides:
            return self
        unknown = sorted(set(overrides) - set(_BUDGET_FIELDS))
        if unknown:
            raise TypeError(
                f"unknown scan budget field(s): {', '.join(unknown)}")
        return replace(self, **overrides)


def resolve_scan_budget(budget: ScanBudget | None = None,
                        **overrides: int | None) -> ScanBudget:
    """One effective :class:`ScanBudget` from an optional base plus overrides.

    ``budget=None`` starts from the production defaults. An override of
    ``None`` keeps the base value (the unset sentinel used by the adapter
    keyword arguments); an explicit value wins over the base; an unknown
    field name raises :class:`TypeError` so typos never silently relax a
    bound.
    """
    if budget is None:
        base = ScanBudget()
    elif isinstance(budget, ScanBudget):
        base = budget
    else:
        raise TypeError("budget must be a ScanBudget instance or None")
    clean = {
        name: value for name, value in overrides.items() if value is not None
    }
    return base.with_overrides(**clean)
