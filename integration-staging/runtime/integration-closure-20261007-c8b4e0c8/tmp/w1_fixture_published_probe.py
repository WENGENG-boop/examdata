"""W1 probe: published rows for the fixture manifest (private run only)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

CANDIDATE = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(CANDIDATE / "src"))

from examdata.integration.api.dataset import build_fixture_snapshot, fixture_providers  # noqa: E402
from examdata.integration.contracts.models import Coverage  # noqa: E402
from examdata.integration.operations.published import (  # noqa: E402
    build_published,
    load_expected_manifest,
)

snapshot = build_fixture_snapshot(fixture_providers())
root = CANDIDATE / "fixtures" / "synthetic" / "operations" / "operations-root"
manifest = load_expected_manifest(root)
assert manifest is not None
view = build_published(snapshot.entries, manifest,
                       dataset_revision=snapshot.dataset_revision)
for row in view.rows:
    print(json.dumps({k: row[k] for k in (
        "public_id", "observed", "expected", "excluded", "unknown", "missing",
        "unmet", "overfilled", "partial", "verified", "derived_status",
        "percentage", "problems")}, sort_keys=True))
    print("   validate:", Coverage.from_dict(row).validate())
print("view problems:", json.dumps(view.problems, sort_keys=True))
print("probe done")
