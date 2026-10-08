"""STEP 6 aid: print one candidate's published/coverage projection.

Reads the candidate identified by ``CANDIDATE_ROOT`` (its package via an
explicit ``sys.path`` insertion and its synthetic operations root via
``EXAMDATA_OPERATIONS_ROOT``), prints one JSON document with the root block,
the coverage counts and the published rows, and writes nothing. Used to diff
the v1 and v2 projections against the same frozen fixture root.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

candidate = Path(os.environ["CANDIDATE_ROOT"]).resolve()
os.environ["EXAMDATA_INTEGRATION_ROOT"] = str(candidate)
os.environ["EXAMDATA_OPERATIONS_ROOT"] = str(
    candidate / "fixtures" / "synthetic" / "operations" / "operations-root")
sys.dont_write_bytecode = True
sys.path.insert(0, str(candidate / "src"))

from examdata.integration.api.dataset import default_dataset  # noqa: E402

ds = default_dataset()
ops = ds.operations
public = ops.to_public(secrets=())
rows = public["checkpoints"]["rows"]
published = public["published"]
current = [r for r in rows if r["freshness"] == "current"]
superseded = [r for r in rows if r["freshness"] == "superseded"]

ROW_FIELDS = ("public_id", "scope", "denominator", "denominator_known",
              "observed", "excluded", "unknown", "missing", "partial",
              "verified", "expected", "unmet", "identity_complete",
              "content_complete", "answers_verified", "derived_status",
              "percentage")

out = {
    "candidate": str(candidate),
    "counts": {
        "observations": len(ops.observations),
        "coverage_rows": len(rows),
        "current_rows": len(current),
        "superseded_rows": len(superseded),
        "job_rows": len(public["jobs"]),
        "published_rows": len(published["rows"]) if published else None,
    },
    "root": public["root"],
    "problems": getattr(ops, "problems", None) or public.get("problems"),
    "published_rows": [
        {field: row.get(field) for field in ROW_FIELDS}
        | {"exclusions": row.get("exclusions")}
        for row in (published["rows"] if published else [])
    ],
}
print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
