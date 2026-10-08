"""Smoke-import the B07 candidate and print the synthetic operations view.

Private rehearsal aid only: points the explicit integration and operations
roots at the B07 candidate, imports the candidate package through an explicit
``sys.path`` insertion (no PYTHONPATH staging), and prints one JSON document
with the operations view - root status, checkpoint rows, job briefs, and the
published rows - so the rehearsal expectations can be compared line by line.
Exits non-zero when the structural counts (seven observations, seven coverage
rows, five current rows, two superseded rows, four published scopes) differ.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

RUN_DIR = Path(__file__).resolve().parent
CANDIDATE = RUN_DIR / "candidates" / "b07-operations-v1"
OPS_ROOT = CANDIDATE / "fixtures" / "synthetic" / "operations" / "operations-root"


def main() -> int:
    os.environ["EXAMDATA_INTEGRATION_ROOT"] = str(CANDIDATE)
    os.environ["EXAMDATA_OPERATIONS_ROOT"] = str(OPS_ROOT)
    sys.path.insert(0, str(CANDIDATE / "src"))
    from examdata.integration.api.dataset import default_dataset

    ds = default_dataset()
    ops = ds.operations
    public = ops.to_public(secrets=())
    rows = public["checkpoints"]["rows"]
    briefs = public["jobs"]
    published = public["published"]
    current = [r for r in rows if r["freshness"] == "current"]
    superseded = [r for r in rows if r["freshness"] == "superseded"]
    out = {
        "candidate": str(CANDIDATE),
        "operations_root": str(OPS_ROOT),
        "dataset_revision": ds.revision,
        "root": public["root"],
        "counts": {
            "observations": len(ops.observations),
            "coverage_rows": len(rows),
            "current_rows": len(current),
            "superseded_rows": len(superseded),
            "job_rows": len(briefs),
            "published_rows": len(published["rows"]) if published else None,
        },
        "checkpoints": public["checkpoints"],
        "jobs": briefs,
        "published": published,
    }
    ok = (len(ops.observations) == 7 and len(rows) == 7 and len(current) == 5
          and len(superseded) == 2 and len(briefs) == 7
          and published is not None and len(published["rows"]) == 4)
    out["structural_ok"] = ok
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
