"""Proposed legacy v1 compatibility adapters (plan 5.5, packet A12).

Static-only proposal layer: nothing here imports an original module, and no
function reads a live database, a service or an upstream source. The payload
contracts reproduced by `translate.py` were recorded by AST inspection of the
legacy handlers (`docs/integration/execution/evidence/A12/legacy_shape_extract.json`)
and the migration decisions per route live in `registry.json` (+ `decisions.py`).

Rules that bind every translator:

* keys are exactly the legacy keys - nothing invented, nothing dropped;
* numeric echoes (limit/offset) are returned unchanged; range validation stays
  with the legacy validation layer (`Query(ge=..., le=...)`);
* quality/verification tokens pass through untouched;
* a missing answer slot or a preserved conflict never becomes a positive claim.

These are proposals for Phase B: they are rebased onto the final tree and gated
by the shape-parity harness in `parity.py` before any legacy route changes.
"""
from __future__ import annotations

from . import bridge, decisions, parity, translate

__all__ = ["bridge", "decisions", "parity", "translate"]
