"""Read-only operations views (plan 3.5, packet A13).

Public surface:

* `budget`      - one validated scan-budget object (``ScanBudget``, plus
  ``resolve_scan_budget``) from which every bounded discovery/read derives
  its allowance at read time;
* `checkpoints` - read-only adapters for the two native checkpoint formats
  (CIE batch runner, IELTS run checkpoints); nothing is ever written back;
* `coverage`    - derived coverage rows that rank observations by their native
  ``updated_at`` and keep superseded snapshots instead of dropping them.

Nothing in this package reads the network, a database, a service, or any
timetable/active-material data; adapters only open checkpoint files for
reading.
"""
from .budget import ScanBudget, resolve_scan_budget
from .checkpoints import (
    CheckpointFormat,
    CheckpointObservation,
    CheckpointReadError,
    CieBatchState,
    IeltsRunState,
    cie_batch_state,
    detect_format,
    ielts_run_state,
    iter_checkpoint_paths,
    parse_native_timestamp,
    read_checkpoint,
    read_checkpoint_bytes,
    state_of,
)
from .coverage import (
    CoverageRow,
    CoverageState,
    CoverageView,
    build_coverage,
    cie_coverage_state,
    ielts_coverage_state,
)

__all__ = [
    "ScanBudget",
    "resolve_scan_budget",
    "CheckpointFormat",
    "CheckpointObservation",
    "CheckpointReadError",
    "CieBatchState",
    "IeltsRunState",
    "cie_batch_state",
    "detect_format",
    "ielts_run_state",
    "iter_checkpoint_paths",
    "parse_native_timestamp",
    "read_checkpoint",
    "read_checkpoint_bytes",
    "state_of",
    "CoverageRow",
    "CoverageState",
    "CoverageView",
    "build_coverage",
    "cie_coverage_state",
    "ielts_coverage_state",
]
