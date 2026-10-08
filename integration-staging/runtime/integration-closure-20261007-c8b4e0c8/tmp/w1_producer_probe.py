"""W1 probe (private): do the candidate's own producers trip the trust rules?

Builds the fixture snapshot exactly as the API does, then reports the builder's
fatal/visible problems and, per entry, the trust problems and quality state.
Read-only; no original tree is touched.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

root = Path(sys.argv[1]).resolve()
os.environ["EXAMDATA_INTEGRATION_ROOT"] = str(root)
os.environ.pop("EXAMDATA_INTEGRATION_STAGING_ROOT", None)
sys.path.insert(0, str(root / "src"))

from examdata.integration.api.dataset import build_fixture_snapshot, fixture_providers  # noqa: E402
from examdata.integration.contracts import trust  # noqa: E402
from examdata.integration.catalog.model import CatalogSnapshot  # noqa: E402

snapshot = build_fixture_snapshot(fixture_providers())

per_entry = []
for entry in snapshot.entries:
    identity = trust.identity_problems(entry.kind, entry.identity_fields)
    quality = trust.quality_claim_problems(entry)
    per_entry.append({
        "public_id": entry.public_id,
        "kind": str(getattr(entry.kind, "value", entry.kind)),
        "identity_problems": identity,
        "quality_problems": quality,
        "quality_state": trust.quality_state(entry),
    })

# a load/save round trip must stay stable (no silently admitted entry)
round_trip = CatalogSnapshot.from_dict(snapshot.to_dict())

print(json.dumps({
    "candidate": str(root),
    "entry_count": len(snapshot.entries),
    "kind_counts": Counter(e["kind"] for e in per_entry),
    "quality_states": Counter(e["quality_state"] for e in per_entry),
    "identity_problem_entries": sum(1 for e in per_entry if e["identity_problems"]),
    "quality_problem_entries": sum(1 for e in per_entry if e["quality_problems"]),
    "snapshot_problems": snapshot.problems,
    "round_trip_problems_equal": round_trip.problems == snapshot.problems,
    "entries_with_problems": [e for e in per_entry if e["identity_problems"] or e["quality_problems"]],
}, indent=1, ensure_ascii=False, default=str))
